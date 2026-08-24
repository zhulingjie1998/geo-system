"""知识库审核业务层。

一次审核 = 绑定某客户的某个知识库版本(customer_knowledge_kb)。
审核产出:
- 正文段落级批注(kb_review_annotation):每条 = 分类(数值/出入/宣传口径) + 选中原文 + 理由
  批注用 quote + occurrence 锚定到不可变版本正文,前端按文字片段查找高亮,
  绕开 Markdown→HTML 坐标转换。
- "建议客户提供的资料"清单(kb_review.material_suggestions JSON)。
定稿后生成 share_token(48 位),分享页只读展示。仅付费客户。
"""
from __future__ import annotations

import json
import logging
import re
import secrets
from datetime import datetime
from typing import Any

import db
from knowledge_service import NotPaidAccountError, _assert_paid_account  # noqa: F401

logger = logging.getLogger("knowledge_review_service")

# 批注三分类:与前端中文标签一一对应
CATEGORIES = {"numeric", "discrepancy", "promotion"}
CATEGORY_LABELS = {
    "numeric": "数值类",
    "discrepancy": "出入类",
    "promotion": "宣传口径",
}

# LLM 生成 KB 时在正文嵌入的「待客户确认」行格式:
#   > ⚠️ **待客户确认-数值类**：具体描述...
#   > ⚠️ **待客户确认-A**：具体描述...     (LLM 自起字母编号)
#   > ⚠ 待客户确认 出入类：...              (无 ** / 全角冒号 / 空格分隔)
# 子标签捕获放宽:任意 ≤40 字、不含冒号/星号/换行;后续靠 _classify 归三档。
_WARN_LINE_RE = re.compile(
    r"^\s*>\s*⚠️?\s*\*{0,2}\s*待客户确认\s*[-—–]?\s*([^*\n:：]{0,40}?)\s*\*{0,2}\s*[:：]\s*(.+?)\s*$",
    re.MULTILINE,
)


def _classify(tag: str, desc: str) -> str:
    """把 LLM 子标签 + 描述,落到 numeric / discrepancy / promotion 三档。
    默认 discrepancy(出入类),最中性,适合"需客户核对"语义。"""
    t = (tag or "").strip()
    if "数值" in t or "数据" in t:
        return "numeric"
    if "出入" in t or "差异" in t or "冲突" in t or "矛盾" in t:
        return "discrepancy"
    if "宣传" in t or "口径" in t or "合规" in t or "承诺" in t:
        return "promotion"
    text = desc or ""
    if any(k in text for k in (
        "数值", "数据", "未明确", "未提供", "未明", "编号", "证书", "数字", "百分比",
        "销量", "规模", "市场份额", "市场占有", "金额", "价格", "数量", "万元", "万件", "亿",
    )):
        return "numeric"
    if any(k in text for k in (
        "宣传", "口径", "广告", "对外", "承诺", "合规", "保证", "措辞", "表述", "宣称", "口号",
    )):
        return "promotion"
    return "discrepancy"


def _now() -> str:
    return datetime.now().strftime("%Y-%m-%d %H:%M:%S")


def _get_version(conn, kb_version_id: int) -> dict | None:
    return db._fetchone(
        conn,
        "SELECT id, account_id, version, content FROM customer_knowledge_kb WHERE id=%s",
        (kb_version_id,),
    )


def get_current_version(account_id: int) -> dict | None:
    """拿该客户当前生效的知识库版本(is_current=1)。"""
    conn = db.get_conn()
    return db._fetchone(
        conn,
        "SELECT id, account_id, version, content FROM customer_knowledge_kb "
        "WHERE account_id=%s AND is_current=1 ORDER BY version DESC LIMIT 1",
        (account_id,),
    )


def _review_to_dict(row: dict | None) -> dict | None:
    if not row:
        return None
    d = dict(row)
    ms = d.get("material_suggestions")
    if isinstance(ms, str):
        try:
            d["material_suggestions"] = json.loads(ms)
        except (json.JSONDecodeError, TypeError):
            d["material_suggestions"] = []
    elif ms is None:
        d["material_suggestions"] = []
    return d


# ══════════════════════════════════════════════
# 审核主体
# ══════════════════════════════════════════════

def get_or_create_review(account_id: int, kb_version_id: int,
                         reviewer_id: int | None = None) -> dict | None:
    """取该 (客户, 版本) 的审核;不存在则建一份 draft。一版一审,可反复编辑。
    首次创建时自动扫 KB 正文里 LLM 已写好的「⚠ 待客户确认-XX」行,
    种为初始 annotation,避免审核人员重复劳动。
    """
    _assert_paid_account(account_id)
    conn = db.get_conn()
    ver = _get_version(conn, kb_version_id)
    if not ver or int(ver["account_id"]) != int(account_id):
        raise ValueError("知识库版本不存在或不属于该客户")
    existing = db._fetchone(
        conn, "SELECT id FROM kb_review WHERE account_id=%s AND kb_version_id=%s",
        (account_id, kb_version_id),
    )
    if existing:
        rid = int(existing["id"])
        # 兼容旧 review:首次打开但 annotations 仍为 0 → 补 seed 一次(不覆盖人工已加的)
        cnt = db._fetchone(
            conn, "SELECT COUNT(*) AS c FROM kb_review_annotation WHERE review_id=%s", (rid,),
        )
        if cnt and int(cnt.get("c") or 0) == 0:
            try:
                seeded = _auto_seed_annotations(rid, ver.get("content") or "")
                if seeded:
                    logger.info("review %s (existing): lazy-seeded %s annotation(s)", rid, seeded)
            except Exception as e:
                logger.warning("review %s: lazy-seed failed: %s", rid, e)
        return get_review(rid)
    with db.transaction() as conn:
        cur = db._exec(
            conn,
            "INSERT INTO kb_review (account_id, kb_version_id, status, reviewer_id, created_at) "
            "VALUES (%s,%s,'draft',%s,%s)",
            (account_id, kb_version_id, reviewer_id, _now()),
        )
        rid = cur.lastrowid
    try:
        seeded = _auto_seed_annotations(rid, ver.get("content") or "")
        if seeded:
            logger.info("review %s: auto-seeded %s annotation(s) from KB warnings", rid, seeded)
    except Exception as e:
        logger.warning("review %s: auto-seed failed: %s", rid, e)
    return get_review(rid)


def _auto_seed_annotations(review_id: int, content: str) -> int:
    """从 KB 正文里扫 LLM 的「待客户确认」行,逐条种为 annotation。
    quote 用 LLM 写的描述(便于前端按文本锚定高亮),reason 同 quote。
    occurrence 按相同 quote 在本次 seed 中的序号递增,避免重复 quote 锚到同一处。"""
    if not content:
        return 0
    n = 0
    occ_counter: dict[str, int] = {}
    for m in _WARN_LINE_RE.finditer(content):
        tag = m.group(1)
        desc = (m.group(2) or "").strip()
        if not desc:
            continue
        cat_en = _classify(tag, desc)
        quote = desc[:200]
        occ = occ_counter.get(quote, 0)
        occ_counter[quote] = occ + 1
        try:
            add_annotation(
                review_id,
                category=cat_en,
                quote=quote,
                occurrence=occ,
                reason=desc,
            )
            n += 1
        except Exception as e:
            logger.warning("seed annotation skipped (%s): %s", desc[:40], e)
    return n


def account_of_review(review_id: int) -> int | None:
    """审核归属的 account_id(供路由层做归属校验);不存在返回 None。"""
    r = db._fetchone(db.get_conn(),
                     "SELECT account_id FROM kb_review WHERE id=%s", (review_id,))
    return int(r["account_id"]) if r and r.get("account_id") else None


def account_of_annotation(anno_id: int) -> int | None:
    """批注所属审核的 account_id;不存在返回 None。"""
    r = db._fetchone(db.get_conn(),
                     "SELECT r.account_id FROM kb_review_annotation a "
                     "JOIN kb_review r ON r.id=a.review_id WHERE a.id=%s", (anno_id,))
    return int(r["account_id"]) if r and r.get("account_id") else None


def get_review(review_id: int) -> dict | None:
    """审核详情:含批注列表 + 资料建议 + 绑定版本的正文(供编辑器高亮)。"""
    conn = db.get_conn()
    r = db._fetchone(conn, "SELECT * FROM kb_review WHERE id=%s", (review_id,))
    if not r:
        return None
    d = _review_to_dict(r)
    annos = db._fetchall(
        conn,
        "SELECT id, category, quote, occurrence, reason, order_index "
        "FROM kb_review_annotation WHERE review_id=%s ORDER BY order_index, id",
        (review_id,),
    )
    d["annotations"] = [dict(a) for a in annos]
    ver = _get_version(conn, r["kb_version_id"])
    d["version"] = (
        {"id": ver["id"], "version": ver["version"], "content": ver["content"]}
        if ver else None
    )
    return d


# ══════════════════════════════════════════════
# 批注
# ══════════════════════════════════════════════

def add_annotation(review_id: int, category: str, quote: str,
                   occurrence: int = 0, reason: str = "",
                   order_index: int | None = None) -> dict:
    if category not in CATEGORIES:
        raise ValueError(f"category 非法:{category}")
    if not (quote or "").strip():
        raise ValueError("quote(选中原文) 必填")
    with db.transaction() as conn:
        if order_index is None:
            nx = db._fetchone(
                conn,
                "SELECT COALESCE(MAX(order_index),-1)+1 AS nx "
                "FROM kb_review_annotation WHERE review_id=%s",
                (review_id,),
            )
            order_index = int(nx["nx"]) if nx else 0
        cur = db._exec(
            conn,
            "INSERT INTO kb_review_annotation "
            "(review_id, category, quote, occurrence, reason, order_index, created_at) "
            "VALUES (%s,%s,%s,%s,%s,%s,%s)",
            (review_id, category, quote, int(occurrence or 0),
             reason or "", order_index, _now()),
        )
        aid = cur.lastrowid
        db._exec(conn, "UPDATE kb_review SET updated_at=%s WHERE id=%s", (_now(), review_id))
    conn2 = db.get_conn()
    return dict(db._fetchone(conn2, "SELECT * FROM kb_review_annotation WHERE id=%s", (aid,)))


def update_annotation(anno_id: int, data: dict) -> dict | None:
    fields: list[str] = []
    args: list[Any] = []
    if "category" in data:
        if data["category"] not in CATEGORIES:
            raise ValueError(f"category 非法:{data['category']}")
        fields.append("category=%s"); args.append(data["category"])
    if "reason" in data:
        fields.append("reason=%s"); args.append(data["reason"] or "")
    if "quote" in data:
        fields.append("quote=%s"); args.append(data["quote"] or "")
    if "occurrence" in data:
        fields.append("occurrence=%s"); args.append(int(data["occurrence"] or 0))
    if "order_index" in data:
        fields.append("order_index=%s"); args.append(int(data["order_index"] or 0))
    if not fields:
        return None
    args.append(anno_id)
    with db.transaction() as conn:
        db._exec(conn, f"UPDATE kb_review_annotation SET {','.join(fields)} WHERE id=%s", tuple(args))
    conn2 = db.get_conn()
    row = db._fetchone(conn2, "SELECT * FROM kb_review_annotation WHERE id=%s", (anno_id,))
    return dict(row) if row else None


def delete_annotation(anno_id: int) -> bool:
    with db.transaction() as conn:
        db._exec(conn, "DELETE FROM kb_review_annotation WHERE id=%s", (anno_id,))
    return True


# ══════════════════════════════════════════════
# 资料建议清单 + 定稿 + 分享
# ══════════════════════════════════════════════

def update_materials(review_id: int, materials: list) -> dict | None:
    """materials: [{name, note}, ...]。覆盖式更新。"""
    clean: list[dict] = []
    for m in (materials or []):
        if isinstance(m, dict):
            name = (m.get("name") or "").strip()
            note = (m.get("note") or "").strip()
        else:
            name, note = str(m).strip(), ""
        if name:
            clean.append({"name": name, "note": note})
    with db.transaction() as conn:
        db._exec(
            conn,
            "UPDATE kb_review SET material_suggestions=%s, updated_at=%s WHERE id=%s",
            (json.dumps(clean, ensure_ascii=False), _now(), review_id),
        )
    return get_review(review_id)


def finalize_review(review_id: int) -> dict | None:
    """定稿:置 finalized + 生成 share_token(已存在则复用)。"""
    conn = db.get_conn()
    r = db._fetchone(conn, "SELECT * FROM kb_review WHERE id=%s", (review_id,))
    if not r:
        return None
    token = r.get("share_token") or secrets.token_hex(24)
    with db.transaction() as conn:
        db._exec(
            conn,
            "UPDATE kb_review SET status='finalized', share_token=%s, "
            "finalized_at=%s, updated_at=%s WHERE id=%s",
            (token, _now(), _now(), review_id),
        )
    return get_review(review_id)


def verify_share_token(review_id: int, token: str) -> bool:
    if not token:
        return False
    conn = db.get_conn()
    r = db._fetchone(
        conn,
        "SELECT 1 FROM kb_review WHERE id=%s AND share_token=%s AND status='finalized'",
        (review_id, token),
    )
    return bool(r)


def get_share_data(account_id: int, review_id: int) -> dict | None:
    """分享只读数据(token 校验在 route 层)。未定稿不返回。"""
    conn = db.get_conn()
    r = db._fetchone(
        conn, "SELECT * FROM kb_review WHERE id=%s AND account_id=%s",
        (review_id, account_id),
    )
    if not r or r.get("status") != "finalized":
        return None
    d = _review_to_dict(r)
    annos = db._fetchall(
        conn,
        "SELECT id, category, quote, occurrence, reason, order_index "
        "FROM kb_review_annotation WHERE review_id=%s ORDER BY order_index, id",
        (review_id,),
    )
    d["annotations"] = [dict(a) for a in annos]
    ver = _get_version(conn, r["kb_version_id"])
    d["version"] = (
        {"version": ver["version"], "content": ver["content"]} if ver else None
    )
    acct = db._fetchone(conn, "SELECT company_name FROM account WHERE id=%s", (account_id,))
    d["company_name"] = (acct or {}).get("company_name") or ""
    d["category_labels"] = CATEGORY_LABELS
    return d
