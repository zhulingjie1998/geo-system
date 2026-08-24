"""客户知识库业务层（Phase 1）。

支持：
- CRUD（customer_knowledge）
- 全文检索 + 标签/状态/类型筛选
- 批量导入：CSV、粘贴大段文本按标题拆分、URL 抓取（复用 Firecrawl）

表 `customer_knowledge` 已由 phase1_schema.sql 建好，
同时支持 account_id=NULL 的系统级模板库。
"""
from __future__ import annotations

import csv
import io
import json
import logging
import re
from typing import Any

import db

logger = logging.getLogger("knowledge_service")


KB_TYPES = {"basic", "product", "case", "news", "faq",
            "competitor", "brand_story", "custom"}
SOURCE_TYPES = {"manual", "url", "import", "generated"}
STATUSES = {"active", "archived", "draft"}


# ══════════════════════════════════════════════
# 业务校验
# ══════════════════════════════════════════════

class NotPaidAccountError(ValueError):
    """知识库仅付费客户可用。"""


def _assert_paid_account(account_id: int | None) -> None:
    """account_id=None 允许（系统模板，管理员场景）；
    若指定客户必须是「正式客户」：user_type=paid 且 is_temp=0。
    临时账号（外部邀请 / 临时查词生成）也是 user_type=paid 但 is_temp=1，
    业务上不视为"正式客户"，不允许搭建知识库。"""
    if account_id is None:
        return
    conn = db.get_conn()
    row = db._fetchone(conn, "SELECT id, user_type, is_temp FROM account WHERE id=%s", (account_id,))
    if not row:
        raise NotPaidAccountError(f"客户不存在（id={account_id}）")
    user_type = (row.get("user_type") or "paid").strip().lower()
    if user_type != "paid":
        raise NotPaidAccountError("仅正式客户可搭建知识库（当前客户为报价客户）")
    if int(row.get("is_temp") or 0):
        raise NotPaidAccountError("仅正式客户可搭建知识库（当前为临时/外部邀请生成账号）")


# ══════════════════════════════════════════════
# 工具
# ══════════════════════════════════════════════

def _tags_in(tags) -> str | None:
    if tags is None:
        return None
    if isinstance(tags, str):
        tags = [t.strip() for t in tags.split(",") if t.strip()]
    if isinstance(tags, list):
        return json.dumps(tags, ensure_ascii=False)
    return None


def _row_to_dict(row: dict | None) -> dict | None:
    if not row:
        return None
    d = dict(row)
    raw_tags = d.get("tags")
    if isinstance(raw_tags, str):
        try:
            d["tags"] = json.loads(raw_tags)
        except (json.JSONDecodeError, TypeError):
            d["tags"] = []
    elif raw_tags is None:
        d["tags"] = []
    for k in ("created_at", "updated_at"):
        if d.get(k):
            d[k] = d[k].strftime("%Y-%m-%d %H:%M:%S")
    return d


# ══════════════════════════════════════════════
# CRUD
# ══════════════════════════════════════════════

def create_knowledge(data: dict, user_id: int | None = None) -> dict:
    title = (data.get("title") or "").strip()
    content = data.get("content") or ""
    if not title:
        raise ValueError("title 必填")
    if not content:
        raise ValueError("content 必填")

    account_id = data.get("account_id")
    if account_id in ("", 0):
        account_id = None

    kb_type = (data.get("kb_type") or "basic").strip()
    if kb_type not in KB_TYPES:
        kb_type = "custom"

    source_type = (data.get("source_type") or "manual").strip()
    if source_type not in SOURCE_TYPES:
        source_type = "manual"

    status = (data.get("status") or "active").strip()
    if status not in STATUSES:
        status = "active"

    _assert_paid_account(account_id)

    with db.transaction() as conn:
        cur = db._exec(conn, """
            INSERT INTO customer_knowledge
              (account_id, kb_type, title, content, summary, tags,
               source_type, source_url, source_ref, priority, status, created_by)
            VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)
        """, (
            account_id,
            kb_type,
            title,
            content,
            (data.get("summary") or None),
            _tags_in(data.get("tags")),
            source_type,
            (data.get("source_url") or None),
            (data.get("source_ref") or None),
            int(data.get("priority") or 0),
            status,
            user_id,
        ))
        new_id = cur.lastrowid
    return get_knowledge(new_id)


def update_knowledge(kb_id: int, data: dict) -> dict | None:
    fields = []
    args = []

    if "account_id" in data:
        val = data["account_id"]
        if val in ("", 0):
            val = None
        _assert_paid_account(val)
        fields.append("account_id=%s"); args.append(val)
    if "kb_type" in data:
        v = (data["kb_type"] or "basic").strip()
        fields.append("kb_type=%s"); args.append(v if v in KB_TYPES else "custom")
    if "title" in data:
        fields.append("title=%s"); args.append((data["title"] or "").strip())
    if "content" in data:
        fields.append("content=%s"); args.append(data["content"] or "")
    if "summary" in data:
        fields.append("summary=%s"); args.append(data["summary"] or None)
    if "tags" in data:
        fields.append("tags=%s"); args.append(_tags_in(data["tags"]))
    if "source_type" in data:
        v = (data["source_type"] or "manual").strip()
        fields.append("source_type=%s"); args.append(v if v in SOURCE_TYPES else "manual")
    if "source_url" in data:
        fields.append("source_url=%s"); args.append(data["source_url"] or None)
    if "source_ref" in data:
        fields.append("source_ref=%s"); args.append(data["source_ref"] or None)
    if "priority" in data:
        fields.append("priority=%s"); args.append(int(data["priority"] or 0))
    if "status" in data:
        v = (data["status"] or "active").strip()
        fields.append("status=%s"); args.append(v if v in STATUSES else "active")

    if not fields:
        return get_knowledge(kb_id)

    args.append(kb_id)
    with db.transaction() as conn:
        db._exec(conn, f"UPDATE customer_knowledge SET {', '.join(fields)} WHERE id=%s", args)
    return get_knowledge(kb_id)


def delete_knowledge(kb_id: int) -> bool:
    with db.transaction() as conn:
        cur = db._exec(conn, "DELETE FROM customer_knowledge WHERE id=%s", (kb_id,))
        return cur.rowcount > 0


def get_knowledge(kb_id: int) -> dict | None:
    conn = db.get_conn()
    row = db._fetchone(conn, "SELECT * FROM customer_knowledge WHERE id=%s", (kb_id,))
    return _row_to_dict(row)


def list_knowledge(
    account_id: int | None = None,
    include_template: bool = True,
    kb_type: str | None = None,
    status: str | None = None,
    q: str = "",
    tags: list[str] | None = None,
    limit: int = 50,
    offset: int = 0,
) -> dict:
    """
    列表查询。
    - account_id=None  -> 仅系统模板库（account_id IS NULL）
    - account_id=<id>  -> 该客户 + 可选叠加系统模板
    - include_template=True 时，查询客户自有 + 系统级模板
    - q 走 FULLTEXT（title, content），非空时忽略其他文本搜索
    """
    conn = db.get_conn()
    where = []
    args: list[Any] = []

    if account_id is None:
        where.append("account_id IS NULL")
    elif include_template:
        where.append("(account_id=%s OR account_id IS NULL)")
        args.append(account_id)
    else:
        where.append("account_id=%s")
        args.append(account_id)

    if kb_type:
        where.append("kb_type=%s")
        args.append(kb_type)

    if status:
        where.append("status=%s")
        args.append(status)

    if q:
        where.append("MATCH(title, content) AGAINST (%s IN NATURAL LANGUAGE MODE)")
        args.append(q)

    if tags:
        # 任一匹配
        ors = []
        for t in tags:
            ors.append("JSON_CONTAINS(tags, %s)")
            args.append(json.dumps(t, ensure_ascii=False))
        if ors:
            where.append("(" + " OR ".join(ors) + ")")

    sql_where = " WHERE " + " AND ".join(where) if where else ""
    total_row = db._fetchone(conn, f"SELECT COUNT(*) AS c FROM customer_knowledge{sql_where}", args)
    total = int((total_row or {}).get("c", 0))

    # 排序：有 q 时按相关性，其次优先级+时间倒序
    if q:
        order = "ORDER BY priority DESC, updated_at DESC"
    else:
        order = "ORDER BY priority DESC, updated_at DESC"

    rows = db._fetchall(
        conn,
        f"SELECT * FROM customer_knowledge{sql_where} {order} LIMIT %s OFFSET %s",
        args + [limit, offset],
    )
    return {
        "total": total,
        "items": [_row_to_dict(r) for r in rows],
        "limit": limit,
        "offset": offset,
    }


def list_paid_accounts(only_formal: bool = False) -> list[dict]:
    """付费客户列表。排除报价客户(user_type!=paid)、临时账号(is_temp=1)、软删(deleted_at)。

    only_formal=True 仅返回正式客户(status='formal')，用于智能生文/内容库等运营功能；
    知识库下拉传 False(默认)，要含初始客户(draft)——因为初始客户正是要在知识库建知识库。"""
    conn = db.get_conn()
    extra = " AND status='formal'" if only_formal else ""
    rows = db._fetchall(conn, f"""
        SELECT id, company_name, company_brand, user_type, status, created_at, updated_at
        FROM account
        WHERE user_type=%s AND COALESCE(is_temp,0)=0 AND deleted_at IS NULL{extra}
        ORDER BY updated_at DESC, id DESC
    """, ("paid",))
    return [{
        "id": r["id"],
        "companyName": r["company_name"],
        "companyBrand": r["company_brand"],
        "userType": r["user_type"],
        "status": r.get("status", "formal") or "formal",
        "createdAt": r.get("created_at"),
        "updatedAt": r.get("updated_at"),
    } for r in rows]


def count_by_account(account_id: int) -> dict:
    conn = db.get_conn()
    rows = db._fetchall(conn, """
        SELECT kb_type, status, COUNT(*) AS c FROM customer_knowledge
        WHERE account_id=%s
        GROUP BY kb_type, status
    """, (account_id,))
    by_type: dict[str, int] = {}
    by_status: dict[str, int] = {}
    total = 0
    for r in rows:
        c = int(r["c"])
        total += c
        by_type[r["kb_type"]] = by_type.get(r["kb_type"], 0) + c
        by_status[r["status"]] = by_status.get(r["status"], 0) + c
    return {"total": total, "by_type": by_type, "by_status": by_status}


# ══════════════════════════════════════════════
# 批量导入
# ══════════════════════════════════════════════

def import_from_csv(
    account_id: int | None,
    csv_text: str,
    default_kb_type: str = "basic",
    user_id: int | None = None,
) -> dict:
    """
    CSV 列：title, content, summary, kb_type, tags, priority, status
    只有 title/content 是必填。tags 用 `|` 或 `,` 分隔。
    """
    reader = csv.DictReader(io.StringIO(csv_text))
    ok, fail, errors = 0, 0, []
    for idx, row in enumerate(reader, start=2):  # 行号含表头
        try:
            title = (row.get("title") or "").strip()
            content = (row.get("content") or "").strip()
            if not title or not content:
                raise ValueError("title/content 必填")
            tags_raw = (row.get("tags") or "").strip()
            tags = [t.strip() for t in re.split(r"[|,]", tags_raw) if t.strip()]
            create_knowledge({
                "account_id": account_id,
                "kb_type": (row.get("kb_type") or default_kb_type).strip(),
                "title": title,
                "content": content,
                "summary": (row.get("summary") or "").strip() or None,
                "tags": tags,
                "source_type": "import",
                "priority": int(row.get("priority") or 0),
                "status": (row.get("status") or "active").strip(),
            }, user_id=user_id)
            ok += 1
        except Exception as e:  # noqa: BLE001
            fail += 1
            errors.append({"line": idx, "error": str(e)})
    return {"ok": ok, "fail": fail, "errors": errors[:50]}


_HEADING_RE = re.compile(r"^(#{1,6})\s+(.+)$", re.MULTILINE)


def import_from_text(
    account_id: int | None,
    text: str,
    default_kb_type: str = "basic",
    user_id: int | None = None,
    split_mode: str = "heading",
) -> dict:
    """
    支持两种拆分：
    - heading：Markdown 标题 (#/##/...) 切段
    - blank  ：按空行切段，每段首行为标题
    """
    text = (text or "").strip()
    if not text:
        return {"ok": 0, "fail": 0, "errors": []}

    entries: list[tuple[str, str]] = []

    if split_mode == "heading":
        matches = list(_HEADING_RE.finditer(text))
        if matches:
            for i, m in enumerate(matches):
                title = m.group(2).strip()
                start = m.end()
                end = matches[i + 1].start() if i + 1 < len(matches) else len(text)
                body = text[start:end].strip()
                if title and body:
                    entries.append((title, body))
        else:
            # 回退：按空行拆
            split_mode = "blank"

    if split_mode == "blank":
        chunks = re.split(r"\n\s*\n", text)
        for chunk in chunks:
            chunk = chunk.strip()
            if not chunk:
                continue
            lines = chunk.split("\n", 1)
            title = lines[0].strip().lstrip("#").strip()
            body = lines[1].strip() if len(lines) > 1 else title
            entries.append((title, body))

    ok, fail, errors = 0, 0, []
    for idx, (title, body) in enumerate(entries, start=1):
        try:
            create_knowledge({
                "account_id": account_id,
                "kb_type": default_kb_type,
                "title": title[:500],
                "content": body,
                "source_type": "import",
            }, user_id=user_id)
            ok += 1
        except Exception as e:  # noqa: BLE001
            fail += 1
            errors.append({"index": idx, "error": str(e)})
    return {"ok": ok, "fail": fail, "errors": errors[:50]}


def import_from_url(
    account_id: int | None,
    url: str,
    kb_type: str = "basic",
    user_id: int | None = None,
) -> dict:
    """
    复用 Firecrawl（系统设置里的 api_key）抓取 URL 生成一条知识条目。
    """
    url = (url or "").strip()
    if not url.startswith("http"):
        raise ValueError("URL 必须以 http(s) 开头")

    settings = db.get_all_settings() or {}
    api_key = (settings.get("firecrawl_api_key") or "").strip()
    api_url = (settings.get("firecrawl_api_url") or "").strip()
    if not api_key or not api_url:
        raise ValueError("系统设置中的 Firecrawl 未配置")

    import scraper
    resp = scraper.firecrawl_scrape(url, api_key, api_url, timeout=60)
    if not resp.get("success"):
        raise RuntimeError("Firecrawl 抓取失败")

    data = resp.get("data") or {}
    markdown = data.get("markdown") or ""
    meta = (data.get("metadata") or {})
    title = (meta.get("title") or url).strip()[:500]
    if not markdown:
        raise RuntimeError("抓取内容为空")

    return create_knowledge({
        "account_id": account_id,
        "kb_type": kb_type,
        "title": title,
        "content": markdown,
        "summary": (meta.get("description") or "")[:1000] or None,
        "source_type": "url",
        "source_url": url,
    }, user_id=user_id)
