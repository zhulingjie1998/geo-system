"""kb_service.py — 客户知识库 service

功能：
  1. 文件上传后异步解析（PDF/Word/Excel/TXT/Markdown/图片）
     - 图片提取基本元数据（当前模型不支持图片输入，不通过 API 传图片）
  2. LLM 生成知识库（首次 + refine 二次迭代）
  3. 版本管理（每次保存/AI 生成都新建一版）

Schema:
  customer_knowledge_source : 资料原文 + 解析后的纯文本
  customer_knowledge_kb     : 知识库版本（markdown）
"""

from __future__ import annotations

import json
import logging
import threading
import io
import os
from datetime import datetime
from pathlib import Path
from typing import Optional

import db
import httpx
import llm_claude
import llm_qwen
from geo_common import upload_dir, now_str

logger = logging.getLogger("kb_service")

# 资料文件存储根目录
KB_UPLOAD_ROOT = upload_dir("kb_source")

# 支持的文件类型 → 解析器映射
SUPPORTED_EXT = {
    ".pdf": "pdf",
    ".docx": "docx",
    ".doc": "doc",
    ".xlsx": "xlsx",
    ".xls": "xls",
    ".pptx": "pptx",
    ".ppt": "ppt",
    ".txt": "text",
    ".md": "text",
    ".csv": "text",
    ".png": "image", ".jpg": "image", ".jpeg": "image",
    ".gif": "image", ".webp": "image", ".bmp": "image",
}

MAX_FILE_SIZE = 30 * 1024 * 1024  # 30MB
KB_MAX_OUTPUT_TOKENS = 32768

# ════════════════════════════════════════════════════════
# 文件解析
# ════════════════════════════════════════════════════════

def _parse_pdf(path: Path) -> str:
    import pdfplumber
    parts = []
    with pdfplumber.open(path) as pdf:
        for i, page in enumerate(pdf.pages, 1):
            txt = (page.extract_text() or "").strip()
            if txt:
                parts.append(f"--- 第 {i} 页 ---\n{txt}")
            # 表格
            for tbl in (page.extract_tables() or []):
                if not tbl:
                    continue
                parts.append("[表格]")
                for row in tbl:
                    cells = [str(c).strip() if c else "" for c in row]
                    parts.append(" | ".join(cells))
    return "\n\n".join(parts).strip()


def _parse_docx(path: Path) -> str:
    import docx
    doc = docx.Document(path)
    parts = []
    for p in doc.paragraphs:
        t = (p.text or "").strip()
        if t:
            parts.append(t)
    for table in doc.tables:
        parts.append("[表格]")
        for row in table.rows:
            parts.append(" | ".join(c.text.strip() for c in row.cells))
    return "\n\n".join(parts).strip()


def _parse_xlsx(path: Path) -> str:
    import openpyxl
    wb = openpyxl.load_workbook(path, data_only=True, read_only=True)
    parts = []
    for sheet in wb.worksheets:
        parts.append(f"=== Sheet: {sheet.title} ===")
        for row in sheet.iter_rows(values_only=True):
            cells = [str(c) if c is not None else "" for c in row]
            if any(c.strip() for c in cells):
                parts.append(" | ".join(cells))
    return "\n".join(parts).strip()


def _parse_pptx(path: Path) -> str:
    from pptx import Presentation

    prs = Presentation(path)
    parts = []
    for idx, slide in enumerate(prs.slides, 1):
        slide_parts = []
        for shape in slide.shapes:
            if hasattr(shape, "text") and shape.text:
                txt = shape.text.strip()
                if txt:
                    slide_parts.append(txt)
        if slide_parts:
            parts.append(f"=== Slide {idx} ===")
            parts.extend(slide_parts)
    return "\n".join(parts).strip()


def _parse_ppt_legacy(path: Path) -> str:
    raise NotImplementedError("老版 .ppt 暂不支持直接解析，请另存为 .pptx 后重新上传")


def _parse_text(path: Path) -> str:
    for enc in ("utf-8", "gbk", "gb18030", "latin-1"):
        try:
            return path.read_text(encoding=enc).strip()
        except UnicodeDecodeError:
            continue
    return path.read_bytes().decode("utf-8", "replace").strip()


def _parse_image_via_qwen_vl(path: Path) -> str:
    """图片解析：当前配置的模型（glm-5.2）不支持图片输入，不通过 API 传图片。

    使用 PIL 提取图片基本元数据（尺寸、格式、文件大小），
    返回元信息文本，不调用多模态 API。
    """
    from PIL import Image

    try:
        img = Image.open(path)
        width, height = img.size
        fmt = (img.format or path.suffix.lstrip(".")).upper()
        mode = img.mode or "unknown"
    except Exception as e:
        logger.warning("[kb-img] 无法读取图片 %s: %s", path.name, e)
        return (
            f"[图片文件] {path.name}\n"
            f"文件大小: {path.stat().st_size // 1024} KB\n"
            f"注意: 图片内容无法自动识别（当前模型不支持图片输入）。\n"
            f"建议: 将图片中的文字内容手动整理为文本文件后上传。"
        )

    file_size_kb = path.stat().st_size // 1024
    return (
        f"[图片文件] {path.name}\n"
        f"格式: {fmt} | 尺寸: {width}×{height} | 色彩模式: {mode} | 文件大小: {file_size_kb} KB\n"
        f"注意: 当前配置的模型不支持图片识别，图片内容未自动提取。\n"
        f"建议: 将图片中的文字内容手动整理为文本文件后上传，或配置支持视觉的模型。"
    )


def _parse_doc_legacy(path: Path) -> str:
    """老版 .doc 不支持原生解析，提示用户转 .docx"""
    raise NotImplementedError(".doc 老版格式暂不支持，请另存为 .docx 后重新上传")


def _parse_xls_legacy(path: Path) -> str:
    """老版 .xls 不支持原生解析，提示用户转 .xlsx"""
    raise NotImplementedError(".xls 老版格式暂不支持，请另存为 .xlsx 后重新上传")


PARSER_MAP = {
    "pdf": _parse_pdf,
    "docx": _parse_docx,
    "xlsx": _parse_xlsx,
    "pptx": _parse_pptx,
    "ppt": _parse_ppt_legacy,
    "text": _parse_text,
    "image": _parse_image_via_qwen_vl,
    "doc": _parse_doc_legacy,
    "xls": _parse_xls_legacy,
}


# ════════════════════════════════════════════════════════
# 资料 CRUD
# ════════════════════════════════════════════════════════

def save_uploaded_file(account_id: int, kb_version_id: Optional[int],
                        file_name: str, file_bytes: bytes) -> dict:
    """保存上传文件 + 入库 + 起后台解析。返回 row dict。"""
    if len(file_bytes) > MAX_FILE_SIZE:
        raise ValueError(f"文件过大（>{MAX_FILE_SIZE//1024//1024}MB）")
    ext = Path(file_name).suffix.lower()
    if ext not in SUPPORTED_EXT:
        raise ValueError(f"不支持的文件类型: {ext}")

    file_type = SUPPORTED_EXT[ext]
    # 落盘到 uploads/kb_source/{account_id}/
    acct_dir = KB_UPLOAD_ROOT / str(account_id)
    acct_dir.mkdir(parents=True, exist_ok=True)
    safe_name = f"{int(datetime.now().timestamp()*1000)}_{file_name}"
    dst = acct_dir / safe_name
    dst.write_bytes(file_bytes)

    # 入库 status=pending
    conn = db.get_conn()
    cur = db._exec(conn,
        """INSERT INTO customer_knowledge_source
           (account_id, kb_version_id, file_name, file_type, file_size,
            parser_status, raw_file_path, created_at)
           VALUES (%s, %s, %s, %s, %s, 'pending', %s, %s)""",
        (account_id, kb_version_id, file_name, file_type, len(file_bytes),
         str(dst), now_str()),
    )
    conn.commit()
    src_id = cur.lastrowid

    # 后台解析
    threading.Thread(target=_parse_async, args=(src_id, file_type, dst), daemon=True).start()

    return {
        "id": src_id,
        "account_id": account_id,
        "kb_version_id": kb_version_id,
        "file_name": file_name,
        "file_type": file_type,
        "file_size": len(file_bytes),
        "parser_status": "pending",
        "created_at": now_str(),
    }


def _parse_async(src_id: int, file_type: str, path: Path) -> None:
    """后台解析单个文件，写 parsed_text + status。"""
    try:
        db._exec(db.get_conn(),
            "UPDATE customer_knowledge_source SET parser_status='parsing' WHERE id=%s",
            (src_id,))
        db.get_conn().commit()
        parser = PARSER_MAP.get(file_type)
        if not parser:
            raise ValueError(f"无解析器: {file_type}")
        text = parser(path)
        if not text:
            raise ValueError("解析后文本为空")
        db._exec(db.get_conn(),
            "UPDATE customer_knowledge_source SET parser_status='done', parsed_text=%s, parser_error='' WHERE id=%s",
            (text[:5_000_000], src_id))  # 5MB 上限
        db.get_conn().commit()
        logger.info("[kb] parsed src=%s type=%s len=%d", src_id, file_type, len(text))
    except Exception as exc:
        logger.exception("[kb] parse failed src=%s", src_id)
        try:
            db._exec(db.get_conn(),
                "UPDATE customer_knowledge_source SET parser_status='failed', parser_error=%s WHERE id=%s",
                (str(exc)[:500], src_id))
            db.get_conn().commit()
        except Exception:
            pass


def _is_base_source(kb_version_id) -> bool:
    """判断一条资料是否属于"基础资料"而非某个知识库版本附属资料。"""
    if kb_version_id is None:
        return True
    if isinstance(kb_version_id, str):
        value = kb_version_id.strip()
        if not value or value.lower() in {"null", "none"}:
            return True
    try:
        return int(kb_version_id) <= 0
    except (TypeError, ValueError):
        return False


def list_sources(account_id: int, kb_version_id: Optional[int] = None) -> list[dict]:
    conn = db.get_conn()
    rows = db._fetchall(conn,
        "SELECT id, account_id, kb_version_id, file_name, file_type, file_size, "
        "parser_status, parser_error, LENGTH(parsed_text) AS text_len, "
        "ai_status, LENGTH(ai_text) AS ai_text_len, created_at "
        "FROM customer_knowledge_source WHERE account_id=%s ORDER BY id DESC",
        (account_id,))
    if kb_version_id is None:
        # 只返回真正的基础资料（kb_version_id 为 NULL/空/0）
        return [row for row in rows if _is_base_source(row.get("kb_version_id"))]
    return [row for row in rows if row.get("kb_version_id") == kb_version_id]


def get_source_text(src_id: int) -> Optional[dict]:
    conn = db.get_conn()
    row = db._fetchone(conn,
        "SELECT id, account_id, file_name, file_type, parsed_text, parser_status, parser_error, "
        "ai_text, ai_status "
        "FROM customer_knowledge_source WHERE id=%s",
        (src_id,))
    return row


def delete_source(src_id: int) -> bool:
    conn = db.get_conn()
    row = db._fetchone(conn,
        "SELECT raw_file_path FROM customer_knowledge_source WHERE id=%s", (src_id,))
    if not row:
        return False
    db._exec(conn, "DELETE FROM customer_knowledge_source WHERE id=%s", (src_id,))
    conn.commit()
    try:
        if row.get("raw_file_path"):
            os.unlink(row["raw_file_path"])
    except Exception:
        pass
    return True


def reparse_source(src_id: int) -> dict:
    """重新解析已有基础资料。"""
    conn = db.get_conn()
    row = db._fetchone(conn,
        "SELECT id, file_type, raw_file_path FROM customer_knowledge_source WHERE id=%s",
        (src_id,))
    if not row:
        raise ValueError("资料不存在")
    raw_path = row.get("raw_file_path") or ""
    if not raw_path or not Path(raw_path).is_file():
        raise ValueError("原始文件不存在，无法重新解析")
    file_type = row.get("file_type") or "text"
    db._exec(conn,
        "UPDATE customer_knowledge_source SET parser_status='pending', parser_error='', parsed_text='' WHERE id=%s",
        (src_id,))
    conn.commit()
    _parse_async(int(src_id), file_type, Path(raw_path))
    return {"ok": True, "id": src_id, "parser_status": "pending"}


# ════════════════════════════════════════════════════════
# 智能识别（Qwen3.7）
# ════════════════════════════════════════════════════════

import re as _re

def _clean_ai_output(text: str) -> str:
    """清理 AI 模型输出的头尾套话，只保留纯净内容。"""
    lines = text.strip().split('\n')
    
    # 需要移除的开头模式
    start_patterns = [
        r'^以下是.*[识别|整理|结果]',
        r'^以下是对.*',
        r'^根据.*原文档',
        r'^\[.*识别.*\]',
        r'^---+\s*$',
        r'^\*\*来源[：:]\*\*',
        r'^\*\*（来源[：:].*\）\*\*',
        r'^\*（来源[：:].*\）\*',
        r'^欢迎随时提出',
        r'^如需进一步生成',
    ]
    
    # 需要移除的结尾模式
    end_patterns = [
        r'^欢迎随时提出',
        r'^如需进一步生成',
        r'^以上是.*识别',
        r'^希望.*对您有帮助',
        r'^---+\s*$',
        r'^\[.*结束.*\]',
    ]
    
    # 移除开头套话
    while lines:
        stripped = lines[0].strip()
        if not stripped:
            lines.pop(0)
            continue
        matched = any(_re.match(p, stripped, _re.IGNORECASE) for p in start_patterns)
        if matched:
            lines.pop(0)
        else:
            break
    
    # 移除结尾套话
    while len(lines) > 1:
        stripped = lines[-1].strip()
        if not stripped:
            lines.pop()
            continue
        matched = any(_re.match(p, stripped, _re.IGNORECASE) for p in end_patterns)
        if matched:
            lines.pop()
        else:
            break
    
    result = '\n'.join(lines).strip()
    return result

_RECOGNIZE_SYSTEM_PROMPT = (
    "你是一个专业的文档智能识别助手。请对用户提供的原始文本进行结构化识别和整理。\n"
    "要求：\n"
    "1. 直接输出识别整理后的正文内容，不要添加任何开头、结尾说明或总结性文字\n"
    "2. 识别并提取文本中的所有关键信息，包括但不限于：公司名称、品牌、产品、数据、时间、地点、人物等\n"
    "3. 保持原文的核心语义，不要编造或添加原文中没有的信息\n"
    "4. 对杂乱或格式不规范的文本进行整理，使其结构清晰（可使用标题、列表等）\n"
    "5. 如果原文包含表格数据，用 markdown 表格格式输出\n"
    "6. 如果原文包含数值数据，保留精确数值\n"
    "7. 用中文输出\n"
    "8. 严禁输出「以下是对...」、「欢迎随时提出」等套话，只输出纯净内容\n"
)

_RECOGNIZE_USER_TEMPLATE = (
    "{raw_text}"
)


def recognize_source(src_id: int) -> dict:
    """使用 Qwen3.7 对资料的 parsed_text 进行智能识别，结果存入 ai_text。

    前置条件：parser_status='done' 且 parsed_text 非空。
    返回 {"ok": True, "id": src_id, "ai_status": "running"} 。
    """
    conn = db.get_conn()
    row = db._fetchone(conn,
        "SELECT id, file_name, file_type, parsed_text, parser_status "
        "FROM customer_knowledge_source WHERE id=%s",
        (src_id,))
    if not row:
        raise ValueError("资料不存在")
    if row.get("parser_status") != "done":
        raise ValueError(f"资料尚未解析完成（当前状态: {row.get('parser_status')}），请等待解析完成后再识别")
    raw_text = row.get("parsed_text") or ""
    if not raw_text.strip():
        raise ValueError("资料解析文本为空，无法识别")

    # 标记为识别中
    db._exec(conn,
        "UPDATE customer_knowledge_source SET ai_status='running' WHERE id=%s",
        (src_id,))
    conn.commit()

    # 后台线程调 Qwen
    threading.Thread(
        target=_recognize_async,
        args=(src_id, raw_text, row.get("file_name") or ""),
        daemon=True,
    ).start()
    return {"ok": True, "id": src_id, "ai_status": "running"}


def _recognize_async(src_id: int, raw_text: str, file_name: str) -> None:
    """后台调用 Qwen3.7 识别文本，写 ai_text + ai_status。"""
    try:
        settings = db.get_all_settings()
        qwen_model = settings.get("qwen_model_name") or "qwen3.7-plus"

        # 截断超长文本（Qwen 上下文限制）
        max_input = 120_000
        truncated = raw_text[:max_input]
        if len(raw_text) > max_input:
            truncated += f"\n\n[注意：原始文本过长，已截取前 {max_input} 字符进行识别]"

        user_prompt = _RECOGNIZE_USER_TEMPLATE.format(raw_text=truncated)
        ai_text = llm_qwen.call_qwen(
            settings,
            user_prompt=user_prompt,
            system_prompt=_RECOGNIZE_SYSTEM_PROMPT,
            max_tokens=16384,
            timeout=600,
            model=qwen_model,
            temperature=0.3,
        )
        if not ai_text.strip():
            raise RuntimeError("Qwen 返回空文本")

        # 清理 AI 输出的头尾套话
        ai_text = _clean_ai_output(ai_text)

        conn = db.get_conn()
        db._exec(conn,
            "UPDATE customer_knowledge_source SET ai_status='done', ai_text=%s WHERE id=%s",
            (ai_text[:5_000_000], src_id))
        conn.commit()
        logger.info("[kb] recognize done src=%s model=%s len=%d", src_id, qwen_model, len(ai_text))
    except Exception as exc:
        logger.exception("[kb] recognize failed src=%s", src_id)
        try:
            conn = db.get_conn()
            db._exec(conn,
                "UPDATE customer_knowledge_source SET ai_status='failed', ai_text=%s WHERE id=%s",
                (f"识别失败: {exc}", src_id))
            conn.commit()
        except Exception:
            pass


def get_source_ai_text(src_id: int) -> Optional[dict]:
    """获取资料的 AI 识别文本。"""
    conn = db.get_conn()
    return db._fetchone(conn,
        "SELECT id, file_name, ai_text, ai_status "
        "FROM customer_knowledge_source WHERE id=%s",
        (src_id,))


# ════════════════════════════════════════════════════════
# 知识库版本
# ════════════════════════════════════════════════════════

def list_versions(account_id: int) -> list[dict]:
    conn = db.get_conn()
    return db._fetchall(conn,
        "SELECT id, account_id, version, LEFT(content, 200) AS preview, "
        "LENGTH(content) AS content_len, instruction, source_ids, parent_id, "
        "is_current, created_by, llm_model, llm_used_tokens, created_at "
        "FROM customer_knowledge_kb WHERE account_id=%s ORDER BY version DESC",
        (account_id,))


def get_version(kb_id: int) -> Optional[dict]:
    conn = db.get_conn()
    row = db._fetchone(conn,
        "SELECT * FROM customer_knowledge_kb WHERE id=%s", (kb_id,))
    if row and row.get("content"):
        row["modules"] = _split_into_modules(row["content"])
    return row


_PROOFREAD_PROMPT = """你是 GEO 内容合规校对员。下面给你一个客户「知识库」的全文,以及该客户「写作规则库」里的若干条规则。
请逐条检查:知识库内容是否与规则冲突 / 违反规则(例如规则禁止某措辞而知识库里出现了、规则要求某口径而知识库写法不一致)。

# 写作规则库(逐条,编号从 1 开始)
{rules_block}

# 知识库全文
{kb_content}

# 输出要求
只输出一个 JSON 对象(不要任何额外文字、不要 markdown 代码块),结构:
{{
  "findings": [
    {{
      "rule_index": <对应规则编号,整数>,
      "rule": "<规则原文摘要>",
      "verdict": "conflict" 或 "ok",
      "evidence": "<若 conflict,引用知识库中冲突的原句片段;ok 则空字符串>",
      "suggestion": "<若 conflict,给出修改建议;ok 则空字符串>"
    }}
  ],
  "summary": "<一句话总体结论,如:共 N 条规则,M 条存在冲突>"
}}
只针对真正存在冲突的规则给出 verdict=conflict;无冲突的规则也要返回但 verdict=ok。"""


def _parse_json_loose(text: str):
    """LLM 输出 JSON 解析:strict → json_repair 兜底。"""
    s = (text or "").strip()
    if s.startswith("```"):
        s = _re.sub(r"^```[a-zA-Z]*\n?|\n?```$", "", s).strip()
    try:
        return json.loads(s)
    except (json.JSONDecodeError, TypeError):
        try:
            import json_repair
            return json_repair.loads(s)
        except Exception:
            logger.exception("[kb-proofread] JSON 解析失败")
            return None


def proofread_against_rules(kb_id: int) -> dict:
    """用最新「规则库」(account_writing_lesson)校对某个知识库版本,返回逐条冲突结果。
    返回 {ok, rules_count, conflict_count, findings:[...], summary}。"""
    version = get_version(kb_id)
    if not version:
        raise ValueError("知识库版本不存在")
    account_id = version.get("account_id")
    content = version.get("content") or ""
    if not content.strip():
        raise ValueError("该知识库版本没有内容")

    lessons = db.list_writing_lessons(account_id, limit=100) or []
    if not lessons:
        return {"ok": True, "rules_count": 0, "conflict_count": 0,
                "findings": [], "summary": "该客户还没有规则库,无需校对。"}

    # 规则库列表 DESC(最新在前),翻正为编号 1..N 与提示词对应
    lessons = list(reversed(lessons))
    rules_lines = []
    for i, ls in enumerate(lessons, 1):
        scene = (ls.get("scene") or "").strip()
        txt = (ls.get("lesson_text") or "").strip()
        rules_lines.append(f"{i}. {('[' + scene + '] ') if scene else ''}{txt}")
    rules_block = "\n".join(rules_lines)

    prompt = _PROOFREAD_PROMPT.format(rules_block=rules_block, kb_content=content)
    settings = db.get_all_settings()
    # 使用通义千问进行合规校对
    raw = call_llm_by_settings(
        settings,
        user_prompt=prompt,
        max_tokens=8000,
        timeout=300,
        mode="qwen",
        model=settings.get("qwen_model_name") or "qwen-plus",
    )
    parsed = _parse_json_loose(raw) or {}

    findings = []
    for f in (parsed.get("findings") or []):
        verdict = "conflict" if str(f.get("verdict")) == "conflict" else "ok"
        try:
            idx = int(f.get("rule_index"))
        except (TypeError, ValueError):
            idx = None
        findings.append({
            "rule_index": idx,
            "rule": (f.get("rule") or "").strip(),
            "verdict": verdict,
            "evidence": (f.get("evidence") or "").strip(),
            "suggestion": (f.get("suggestion") or "").strip(),
        })
    conflicts = [f for f in findings if f["verdict"] == "conflict"]
    summary = (parsed.get("summary") or "").strip() or \
        f"共校对 {len(lessons)} 条规则,{len(conflicts)} 条存在冲突。"
    return {
        "ok": True,
        "kb_version": version.get("version"),
        "rules_count": len(lessons),
        "conflict_count": len(conflicts),
        "findings": findings,
        "summary": summary,
    }


# ════════════════════════════════════════════════════════
# 模块拆分（KB markdown → M01-M10 数组）
# ════════════════════════════════════════════════════════

import re as _re

# 匹配 ## 【M01】xxx 或 ## M01 xxx 或 ## 【M01-M10】xxx 等容错
_MOD_HEAD_RE = _re.compile(
    r'^\s*##\s*[【\[]?\s*(M\d{2})\s*[】\]]?\s*[:：·]?\s*(.*?)\s*$',
    _re.MULTILINE,
)
# 「⚠ 待客户确认」/ 「⚠️ 待客户确认」/ 「待客户确认」开头
_WARN_RE = _re.compile(r'⚠️?\s*待客户确认|【待客户确认】|❓|<!--\s*TODO', _re.IGNORECASE)


def _strip_kb_preamble(content: str) -> str:
    """去掉首个模块标题前的 LLM 元叙述/前言（如"我注意到任务要求…"），从第一个 `## 【MXX】` 开始。"""
    if not content:
        return content
    m = _MOD_HEAD_RE.search(content)
    if m and m.start() > 0:
        return content[m.start():].lstrip()
    return content


def _split_into_modules(content: str) -> list[dict]:
    """把 KB markdown 拆成 M01-M10 模块列表。
    若没匹配到任何模块标题，返回单个 'all' 模块（兼容老格式）。
    """
    if not content:
        return []
    matches = list(_MOD_HEAD_RE.finditer(content))
    if not matches:
        return [{
            "key": "all", "title": "完整内容",
            "content": content,
            "warning_count": len(_WARN_RE.findall(content)),
            "has_warning": bool(_WARN_RE.search(content)),
        }]

    # 不再把 M01 之前的前言(仅标题 + 版本行,页头已展示)切成「封面/引言」标签 —— 直接从 M01 开始。
    out: list[dict] = []

    # 模块间 LLM 常用 --- 作分隔线；属于"模块间"装饰，不属于任一模块本身
    _trailing_hr = _re.compile(r'\s*\n\s*[-*_]{3,}\s*$')
    for i, m in enumerate(matches):
        end = matches[i + 1].start() if i + 1 < len(matches) else len(content)
        body = content[m.start():end].rstrip()
        body = _trailing_hr.sub('', body).rstrip()
        out.append({
            "key": m.group(1).upper(),  # M01 / M02 ...
            "title": m.group(2).strip() or m.group(1).upper(),
            "content": body,
            "warning_count": len(_WARN_RE.findall(body)),
            "has_warning": bool(_WARN_RE.search(body)),
        })
    return out


def get_current_version(account_id: int) -> Optional[dict]:
    conn = db.get_conn()
    row = db._fetchone(conn,
        "SELECT * FROM customer_knowledge_kb WHERE account_id=%s AND is_current=1 LIMIT 1",
        (account_id,))
    if not row:
        # 兜底:当前版标记丢失(如"当前版"被删除后未转移)时退回最新版本,
        # 避免明明有知识库却整站显示"无知识库"。
        row = db._fetchone(conn,
            "SELECT * FROM customer_knowledge_kb WHERE account_id=%s "
            "ORDER BY version DESC LIMIT 1", (account_id,))
    if row and row.get("content"):
        row["modules"] = _split_into_modules(row["content"])
    return row


def resolve_kb_account(account_id: int) -> int:
    """KB 只读消费方(智能生文等)用:本账号有 KB 用自己;否则若「数据共享」勾了 kb 范围,
    跟随来源账号(拆分客户场景:知识库都在老账号,新账号生文直接复用)。"""
    try:
        conn = db.get_conn()
        has = db._fetchone(conn,
            "SELECT id FROM customer_knowledge_kb WHERE account_id=%s AND is_current=1 LIMIT 1",
            (account_id,))
        if has:
            return account_id
        acc = db.get_account(account_id) or {}
        ds = acc.get("dataShare") or {}
        src = ds.get("sourceAccountId")
        if src and "kb" in (ds.get("scopes") or []):
            return int(src)
    except Exception:
        logger.exception("[kb] resolve_kb_account failed account=%s", account_id)
    return account_id


def set_current_version(account_id: int, kb_id: int) -> bool:
    conn = db.get_conn()
    db._exec(conn,
        "UPDATE customer_knowledge_kb SET is_current=0 WHERE account_id=%s",
        (account_id,))
    db._exec(conn,
        "UPDATE customer_knowledge_kb SET is_current=1 WHERE id=%s AND account_id=%s",
        (kb_id, account_id))
    conn.commit()
    return True


def delete_version(kb_id: int) -> bool:
    conn = db.get_conn()
    db._exec(conn, "DELETE FROM customer_knowledge_kb WHERE id=%s", (kb_id,))
    conn.commit()
    return True


def _next_version(account_id: int) -> int:
    conn = db.get_conn()
    row = db._fetchone(conn,
        "SELECT MAX(version) AS mx FROM customer_knowledge_kb WHERE account_id=%s",
        (account_id,))
    return int((row or {}).get("mx") or 0) + 1


def _save_kb(*, account_id: int, content: str, instruction: str,
              source_ids: list, parent_id: Optional[int], created_by: str,
              llm_model: str = "", llm_tokens: int = 0) -> dict:
    """新建一版，自动设为 current。"""
    version = _next_version(account_id)
    conn = db.get_conn()
    # 旧 current 取消
    db._exec(conn,
        "UPDATE customer_knowledge_kb SET is_current=0 WHERE account_id=%s",
        (account_id,))
    cur = db._exec(conn,
        """INSERT INTO customer_knowledge_kb
           (account_id, version, content, instruction, source_ids, parent_id,
            is_current, created_by, llm_model, llm_used_tokens, created_at)
           VALUES (%s, %s, %s, %s, %s, %s, 1, %s, %s, %s, %s)""",
        (account_id, version, content, instruction or "",
         json.dumps(source_ids or [], ensure_ascii=False),
         parent_id, created_by, llm_model, llm_tokens, now_str()),
    )
    conn.commit()
    return {"id": cur.lastrowid, "version": version, "is_current": 1}


# ════════════════════════════════════════════════════════
# LLM 提示词模板
# ════════════════════════════════════════════════════════

KB_PROMPT_FIRST = """\
你是 GEO（Generative Engine Optimization）运营专家，正在为企业客户构建 AI 平台内容语料库。

# 客户信息
客户全称：{company_name}（简称 {brand_name}）

# 任务
基于以下原始资料，生成 1 到 10 个标准知识模块的内容，按最适合当前客户知识的结构输出；
如果某些模块信息不足，可以少于 10 个，但不能超过 10 个。

# 🚨 强制约束（最高优先级，违反任一条都视为失败输出）
1. **模块标题必须严格使用 `## 【M0X】模块名称` 格式**（中文方括号【】，序号两位 M01-M10）。例：`## 【M01】企业品牌概览`、`## 【M07】典型项目案例集`。
2. **顺序必须是 M01 → M02 → … → 依次递增**，最多输出 10 个模块，不要打乱顺序。
3. 如果某些模块信息明显不足，可以不输出该模块，但不要为了凑满 10 个而编造。
4. 信息不足的模块如实说明缺乏哪些内容，不要编造。
5. 写完后必须自检一遍：确认标题格式正确、编号连续、没有超过 10 个模块。

# 写作原则
- 第三方客观视角，严格基于客户提供的原始资料，**不虚构信息**
- 单模块约 1500 字（信息少时不强求字数，但模块必须存在）
- 输出 Markdown 格式

# 标准 10 模块（按 M01→M10 顺序输出，编号严格对应）
- **M01**：企业品牌概览（品牌历史、资质认证、核心定位）
- **M02**：核心技术解析（主力技术方案原理与优势）
- **M03**：产品线介绍（全系产品参数对照）
- **M04**：核心场景方案 A（最主要客户场景）
- **M05**：核心场景方案 B（第二重要场景）
- **M06**：核心场景方案 C（第三场景）
- **M07**：典型项目案例集（实测数据多场景案例）
- **M08**：商业合作模式（购买/分成/EMC 等模式详解）
- **M09**：竞争优势对比（与主要竞品的客观对比分析）
- **M10**：常见问题 FAQ（售前/技术/商务/售后高频问答）

# 输出格式
每个模块用以下格式：

```
## 【M01】企业品牌概览
> 知识库主题：[一句话概括]

一、[章节名]
[正文]

二、[章节名]
[正文]
...
```

# 原始资料
{merged_source_texts}
{reference_report_block}
{user_instruction_block}

请直接输出完整 markdown，不要前言。"""


KB_PROMPT_REFINE = """\
你是 GEO 运营专家。客户对其知识库提了新要求/新补充资料，请基于以下信息生成新版本。

# 客户信息
客户全称：{company_name}（简称 {brand_name}）

# 当前知识库 v{prev_version}（人工已编辑过的版本，共 {module_count} 个模块）
{current_content}

# 客户新要求
{new_instruction}

# 新增补充资料（可能为空）
{additional_source_texts}

# 任务
1. **保留**人工编辑过的合理部分
2. 按客户新要求**修改/补充**对应模块
3. 整合新补充资料中的信息
4. 确保所有模块内容完整、准确

# ⛔ 完整性硬性要求（最重要，违反即作废）
- 当前知识库共有 {module_count} 个模块，清单如下：
{module_roster}
- 你必须**逐字完整输出上述全部 {module_count} 个模块的完整正文**，按原编号顺序排列。
- 即使某个模块本次**没有改动**，也必须**原样完整重写**它的全部正文，**不得**省略。
- **严禁**出现「保持不变」「不再重复」「内容同上」「如需完整版可告知」「为节省篇幅省略」「…」之类的省略表述或占位说明。
- **禁止**任何前言/说明/元叙述（如"我注意到任务要求…"），直接从第一个 `## 【M01】` 开始输出。
- 客户新要求若只涉及个别模块，你仍要输出全部模块——只是改动对应模块、其余原样保留。

# 写作要求
- 第三方客观视角、严格基于资料、不虚构
- 单模块约 1500 字
- Markdown 格式，模块标题用 `## 【MXX】模块名`

请直接输出含全部 {module_count} 个模块的完整 markdown 新版本，从 `## 【M01】` 开始。"""


def _wait_for_parsing(source_ids: list[int], timeout_s: int = 600, poll_s: float = 2.0) -> dict:
    """阻塞等待 source_ids 全部脱离 pending/parsing 状态。
    返回 {done: [ids], failed: [(id, error)], stuck: [ids]}。
    Generate 流程在 daemon thread 里调用，等几分钟无副作用；前端早就拿到 task_id 走开了。
    """
    import time
    if not source_ids:
        return {"done": [], "failed": [], "stuck": []}
    start = time.time()
    placeholders = ",".join(["%s"] * len(source_ids))
    while True:
        rows = db._fetchall(db.get_conn(),
            f"SELECT id, parser_status, parser_error FROM customer_knowledge_source "
            f"WHERE id IN ({placeholders})", tuple(source_ids))
        not_settled = [r for r in rows if r["parser_status"] in ("pending", "parsing")]
        if not not_settled:
            done = [r["id"] for r in rows if r["parser_status"] == "done"]
            failed = [(r["id"], r.get("parser_error") or "") for r in rows if r["parser_status"] == "failed"]
            return {"done": done, "failed": failed, "stuck": []}
        if time.time() - start > timeout_s:
            stuck = [r["id"] for r in not_settled]
            done = [r["id"] for r in rows if r["parser_status"] == "done"]
            failed = [(r["id"], r.get("parser_error") or "") for r in rows if r["parser_status"] == "failed"]
            logger.warning("[kb] _wait_for_parsing timeout (%ds): stuck=%s", timeout_s, stuck)
            return {"done": done, "failed": failed, "stuck": stuck}
        time.sleep(poll_s)


def _own_source_ids(account_id: int, source_ids: list[int]) -> list[int]:
    """只保留确实属于该客户的资料 id(防跨客户注入他人素材)。保持入参顺序。"""
    ids = [int(s) for s in (source_ids or []) if str(s).strip()]
    if not ids:
        return []
    ph = ",".join(["%s"] * len(ids))
    rows = db._fetchall(db.get_conn(),
        f"SELECT id FROM customer_knowledge_source WHERE id IN ({ph}) AND account_id=%s",
        tuple(ids) + (int(account_id),))
    keep = {int(r["id"]) for r in rows}
    return [i for i in ids if i in keep]


def _merge_source_texts(source_ids: list[int], max_total_chars: int = 200_000) -> str:
    """拼接选中资料的解析文本，用 markdown header 分隔。"""
    if not source_ids:
        return "（未选择资料）"
    conn = db.get_conn()
    placeholders = ",".join(["%s"] * len(source_ids))
    rows = db._fetchall(conn,
        f"SELECT id, file_name, file_type, parsed_text FROM customer_knowledge_source "
        f"WHERE id IN ({placeholders}) AND parser_status='done' ORDER BY id",
        tuple(source_ids))
    parts = []
    total = 0
    for r in rows:
        seg = f"\n\n=== 资料：{r['file_name']} ({r['file_type']}) ===\n{r['parsed_text']}"
        if total + len(seg) > max_total_chars:
            parts.append(f"\n\n=== 资料：{r['file_name']} (已截断，原始 {len(r['parsed_text'])} 字)===\n{r['parsed_text'][:5000]}")
            break
        parts.append(seg)
        total += len(seg)
    return "".join(parts).strip() or "（资料尚未解析完成）"


def call_llm_by_settings(settings: dict, user_prompt: str, *, max_tokens: int, timeout: int,
                        mode: Optional[str] = None, model: Optional[str] = None) -> str:
    """按系统设置中的 llm_api_mode / llm_* 配置发起一次最小 LLM 请求。"""
    mode = (mode or settings.get("llm_api_mode") or "qwen").strip().lower()  # 默认使用通义千问
    base_url = (settings.get(f"{mode}_base_url") or settings.get("llm_base_url", "")).strip().rstrip("/")
    api_key = settings.get(f"{mode}_api_key") or settings.get("llm_api_key", "")
    model = model or settings.get(f"{mode}_model_name") or settings.get("llm_model_name") or "qwen-plus"  # 默认通义千问
    timeout = int(timeout or settings.get("llm_timeout") or 300)

    if not api_key:
        raise RuntimeError(f"{mode}_api_key 未配置，请先在系统设置中填写")
    if not base_url:
        raise RuntimeError(f"{mode}_base_url 未配置，请先在系统设置中填写")

    # 兼容不同网关的通用上限，避免把非法 max_tokens 透传导致 HTTP 400。
    max_tokens = max(1, min(int(max_tokens or 0), KB_MAX_OUTPUT_TOKENS))

    def _normalize_openai_base_url(url: str) -> str:
        if url.endswith("/v1/chat/completions"):
            return url
        if url.endswith("/chat/completions"):
            return url
        if url.endswith("/v1"):
            return f"{url}/chat/completions"
        return f"{url}/v1/chat/completions"

    def _normalize_claude_base_url(url: str) -> str:
        """Claude API: 去掉路径后缀，只保留 base"""
        for suffix in ["/v1/messages", "/messages"]:
            if url.endswith(suffix):
                return url[:-len(suffix)]
        return url

    with httpx.Client(timeout=timeout, trust_env=False) as client:
        if mode == "claude":
            base_url = _normalize_claude_base_url(base_url)
            url = f"{base_url}/v1/messages"
            payload = {
                "model": model,
                "max_tokens": max_tokens,
                "messages": [{"role": "user", "content": user_prompt}],
            }
            headers = {
                "x-api-key": api_key,
                "anthropic-version": "2023-06-01",
                "Content-Type": "application/json",
            }
            resp = client.post(url, headers=headers, json=payload)
            if resp.status_code >= 400:
                raise RuntimeError(f"Claude 请求失败 HTTP {resp.status_code}: {(resp.text or '')[:400]}")
            data = resp.json()
            content_blocks = data.get("content") or []
            text = ""
            for block in content_blocks:
                if block.get("type") == "text":
                    text += block.get("text", "")
            text = (text or "").strip()
            if not text:
                raise RuntimeError(f"Claude 返回为空: {data!r}")
            return text

        url = _normalize_openai_base_url(base_url)
        payload = {
            "model": model,
            "messages": [{"role": "user", "content": user_prompt}],
            "temperature": 0.1,
            "max_tokens": max_tokens,
        }
        headers = {"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"}
        resp = client.post(url, headers=headers, json=payload)
        if resp.status_code >= 400:
            raise RuntimeError(f"LLM 请求失败 HTTP {resp.status_code}: {(resp.text or '')[:400]}")
        data = resp.json()
        choices = data.get("choices") or []
        if not choices:
            raise RuntimeError(f"LLM 返回空 choices: {data!r}")
        text = (choices[0].get("message", {}).get("content", "") or "").strip()
        if not text:
            raise RuntimeError(f"LLM 返回为空: {data!r}")
        return text


def generate_kb_first(account_id: int, instruction: str, source_ids: list[int],
                       *,
                       reference_brand_report_id: Optional[int] = None,
                       reference_uploaded_report: Optional[tuple] = None) -> dict:
    """首次生成 v1 知识库。返回新版本 dict。

    可选参数（任一或两者皆可，均会作为 LLM 参考素材附加到 prompt）：
      reference_brand_report_id: 该客户已完成的 brand 报告 id
      reference_uploaded_report: (file_name, file_bytes) 上传的外部分析报告
    """
    acc = db.get_account(account_id)
    if not acc:
        raise ValueError("账户不存在")
    company = acc.get("companyName") or ""
    brand = acc.get("companyBrand") or company
    if isinstance(brand, list):
        brand = brand[0] if brand else company

    # 安全:只允许使用属于本客户的资料,过滤掉越权传入的他人 source_id
    source_ids = _own_source_ids(account_id, source_ids)

    # 等所有素材脱离 pending/parsing（最多 10 分钟，daemon thread 后台等，前端不感知）
    if source_ids:
        wait_result = _wait_for_parsing(source_ids, timeout_s=600)
        if wait_result["failed"]:
            logger.warning("[kb] %d 份资料解析失败将跳过：%s",
                           len(wait_result["failed"]), wait_result["failed"][:3])
        if wait_result["stuck"]:
            logger.warning("[kb] %d 份资料解析超时将跳过：%s",
                           len(wait_result["stuck"]), wait_result["stuck"])
        # 只用 done 的 source_ids
        source_ids = wait_result["done"]
        if not source_ids:
            raise ValueError("所有上传的素材都解析失败 / 超时，请检查文件格式后重试")

    merged = _merge_source_texts(source_ids)
    user_block = f"\n# 用户额外要求\n{instruction}\n" if instruction else ""

    # 收集竞争分析报告参考段（可来自已有报告 + 上传报告，可叠加）
    ref_segments: list[str] = []
    if reference_brand_report_id:
        try:
            md = _checklist_md_from_brand_report(account_id, int(reference_brand_report_id))
            if md:
                ref_segments.append(f"## 来源：客户已有竞争分析报告 #{reference_brand_report_id}\n{md}")
        except Exception as exc:
            logger.warning("[kb] 读已有报告失败 report=%s: %s",
                           reference_brand_report_id, exc)
    if reference_uploaded_report:
        try:
            file_name, file_bytes = reference_uploaded_report
            md = _checklist_md_from_uploaded(file_name, file_bytes)
            if md:
                ref_segments.append(f"## 来源：上传的外部分析报告 [{file_name}]\n{md}")
        except Exception as exc:
            logger.warning("[kb] 解析上传报告失败 file=%s: %s",
                           reference_uploaded_report[0] if reference_uploaded_report else "",
                           exc)
    reference_block = ""
    if ref_segments:
        reference_block = (
            "\n\n# 参考：来自竞争分析报告的资料清单（高可信，作为本次知识库 ground truth）\n"
            "> 以下内容是已经针对本品牌定制好的「12 类资料收集清单」，包含 description / standard / examples，"
            "请把它作为高优先级事实依据融入对应模块（M01-M10），不要与之冲突。\n\n"
            + "\n\n".join(ref_segments)
        )

    prompt = KB_PROMPT_FIRST.format(
        company_name=company, brand_name=brand,
        merged_source_texts=merged,
        reference_report_block=reference_block,
        user_instruction_block=user_block,
    )

    settings = db.get_all_settings()
    # 强制使用通义千问（不再依赖数据库 llm_api_mode 设置）
    mode = "qwen"
    model = settings.get("qwen_model_name") or settings.get("llm_model_name") or "qwen-plus"
    content = call_llm_by_settings(
        settings,
        prompt,
        max_tokens=KB_MAX_OUTPUT_TOKENS,
        timeout=int(settings.get("llm_timeout") or 900),
        mode=mode,
        model=model,
    )

    return _save_kb(
        account_id=account_id,
        content=content,
        instruction=instruction,
        source_ids=source_ids,
        parent_id=None,
        created_by="ai",
        llm_model=model,
    )


def generate_kb_first_qwen(account_id: int, instruction: str, source_ids: list[int],
                            *,
                            model: Optional[str] = None) -> dict:
    """使用通义千问 (Qwen) 首次生成 v1 知识库。返回新版本 dict。

    与 generate_kb_first 功能一致，但使用 Qwen/OpenAI 兼容接口。
    """
    acc = db.get_account(account_id)
    if not acc:
        raise ValueError("账户不存在")
    company = acc.get("companyName") or ""
    brand = acc.get("companyBrand") or company
    if isinstance(brand, list):
        brand = brand[0] if brand else company

    # 安全:只允许使用属于本客户的资料
    source_ids = _own_source_ids(account_id, source_ids)

    # 等待素材解析完成
    if source_ids:
        wait_result = _wait_for_parsing(source_ids, timeout_s=600)
        if wait_result["failed"]:
            logger.warning("[kb-qwen] %d 份资料解析失败将跳过：%s",
                           len(wait_result["failed"]), wait_result["failed"][:3])
        if wait_result["stuck"]:
            logger.warning("[kb-qwen] %d 份资料解析超时将跳过：%s",
                           len(wait_result["stuck"]), wait_result["stuck"][:3])
        source_ids = wait_result["done"]
        if not source_ids:
            raise ValueError("所有上传的素材都解析失败 / 超时，请检查文件格式后重试")

    merged = _merge_source_texts(source_ids)
    user_block = f"\n# 用户额外要求\n{instruction}\n" if instruction else ""

    prompt = KB_PROMPT_FIRST.format(
        company_name=company, brand_name=brand,
        merged_source_texts=merged,
        reference_report_block="",  # Qwen 版暂不支持参考报告
        user_instruction_block=user_block,
    )

    settings = db.get_all_settings()
    qwen_model = model or settings.get("qwen_model_name") or "qwen3.7-plus"

    logger.info("[kb-qwen] 开始生成知识库 account=%s model=%s sources=%d",
                account_id, qwen_model, len(source_ids))

    content = llm_qwen.call_qwen(
        settings,
        user_prompt=prompt,
        max_tokens=KB_MAX_OUTPUT_TOKENS,
        timeout=900,
        model=qwen_model,
        temperature=0.7,
    )

    return _save_kb(
        account_id=account_id,
        content=content,
        instruction=instruction,
        source_ids=source_ids,
        parent_id=None,
        created_by="ai-qwen",
        llm_model=qwen_model,
    )


def _checklist_md_from_brand_report(account_id: int, report_id: int) -> Optional[str]:
    """读已有 brand 报告 → 12 类清单 markdown（不入库，仅返回文本）。"""
    conn = db.get_conn()
    row = db._fetchone(conn,
        """SELECT resource_checklist_json, html_content
           FROM weekly_report
           WHERE id=%s AND account_id=%s AND report_type='brand' AND status='completed'""",
        (report_id, account_id))
    if not row:
        return None
    chk = None
    rcj = (row.get("resource_checklist_json") or "").strip()
    if rcj:
        try:
            chk = json.loads(rcj)
        except Exception:
            chk = None
    if not chk and row.get("html_content"):
        try:
            chk = _parse_checklist_from_html(row["html_content"])
        except Exception:
            chk = None
    if not chk or not (chk.get("categories") or []):
        return None
    return _render_checklist_to_markdown(chk)


def _checklist_md_from_uploaded(file_name: str, file_bytes: bytes) -> Optional[str]:
    """解析上传报告 → 12 类清单 markdown（不入库，仅返回文本）。"""
    if not file_bytes:
        return None
    ext = Path(file_name).suffix.lower()
    text = ""
    chk = None
    if ext in (".html", ".htm"):
        try:
            html = file_bytes.decode("utf-8", errors="replace")
        except Exception:
            html = file_bytes.decode("gbk", errors="replace")
        try:
            chk = _parse_checklist_from_html(html)
        except Exception:
            chk = None
        if not chk:
            from bs4 import BeautifulSoup
            text = BeautifulSoup(html, "html.parser").get_text("\n", strip=True)
    elif ext == ".pdf":
        text = _parse_pdf(_write_tmp(file_bytes, ext))
    elif ext == ".docx":
        text = _parse_docx(_write_tmp(file_bytes, ext))
    else:
        return None
    if not chk:
        if not text or len(text) < 100:
            return None
        chk = _llm_extract_checklist(text[:120_000])
    if not chk or not (chk.get("categories") or []):
        return None
    return _render_checklist_to_markdown(chk)


KB_PROMPT_EXPAND = """\
你是 GEO 知识库专家。下面是客户「{company_name}」(品牌「{brand_name}」)当前知识库**已有模块的标题**(仅供去重,不要改写它们),以及补充资料和要求。
请**新增 {add_count} 个全新知识模块**,主题不得与已有模块重复,要对该客户在 AI 引擎中的内容曝光有实际价值。

# 当前已有模块(仅标题,勿重复)
{existing_titles}

# 补充资料
{additional_source_texts}

# 补充要求
{new_instruction}

# 输出要求
1. **只输出新增的 {add_count} 个模块**,不要重复或改写已有模块。
2. 每个模块标题严格用 `## 【M{start_no:02d}】模块名称` 格式,编号从 M{start_no:02d} 起依次递增(M{start_no:02d}、下一个+1…)。
3. 每个模块结构: `## 标题` + 正文(约1500字;信息不足时如实说明,不要编造)。
4. 不要前言/结语/汇总表,直接从第一个 `##` 开始输出。
"""


def expand_kb(prev_kb_id: int, new_instruction: str,
              additional_source_ids: list[int], add_count: int = 3) -> dict:
    """AI 扩充:基于当前版本(已有模块去重) + 选定资料 + 补充要求,生成 add_count 个全新模块,追加成新版本。"""
    prev = get_version(prev_kb_id)
    if not prev:
        raise ValueError("当前版本不存在")
    account_id = prev["account_id"]
    acc = db.get_account(account_id)
    company = acc.get("companyName") if acc else ""
    brand = (acc.get("companyBrand") or company) if acc else company
    if isinstance(brand, list):
        brand = brand[0] if brand else company
    add_count = max(1, min(int(add_count or 3), 10))

    additional_source_ids = _own_source_ids(account_id, additional_source_ids)
    if additional_source_ids:
        wr = _wait_for_parsing(additional_source_ids, timeout_s=600)
        additional_source_ids = wr["done"]
    add_texts = _merge_source_texts(additional_source_ids) if additional_source_ids else "（无，主要依据补充要求与已有模块上下文扩充）"

    mods = _split_into_modules(prev["content"]) or []
    existing_titles = "\n".join(f"- {m.get('key', '')} {m.get('title', '')}" for m in mods) or "（无）"
    maxno = 0
    for m in mods:
        k = (m.get("key") or "")
        if k.startswith("M") and k[1:].isdigit():
            maxno = max(maxno, int(k[1:]))
    start_no = (maxno or len(mods)) + 1

    prompt = KB_PROMPT_EXPAND.format(
        company_name=company, brand_name=brand, add_count=add_count,
        existing_titles=existing_titles, additional_source_texts=add_texts,
        new_instruction=new_instruction or "（无特别要求，围绕本品牌补充有价值的知识模块）",
        start_no=start_no,
    )
    settings = db.get_all_settings()
    # 使用通义千问进行知识库扩充
    new_modules = call_llm_by_settings(
        settings,
        user_prompt=prompt,
        max_tokens=KB_MAX_OUTPUT_TOKENS,
        timeout=900,
        mode="qwen",
        model=settings.get("qwen_model_name") or "qwen-plus",
    )
    new_modules = _strip_kb_preamble(new_modules or "")
    combined = (prev["content"] or "").rstrip() + "\n\n" + new_modules.strip() + "\n"

    all_ids = list((prev.get("source_ids") and json.loads(prev["source_ids"])) or [])
    for sid in additional_source_ids or []:
        if sid not in all_ids:
            all_ids.append(sid)
    return _save_kb(
        account_id=account_id, content=combined,
        instruction=f"AI 扩充 {add_count} 个模块" + (f"：{new_instruction}" if new_instruction else ""),
        source_ids=all_ids, parent_id=prev_kb_id, created_by="ai",
    )


def refine_kb(prev_kb_id: int, new_instruction: str,
              edited_content: str, additional_source_ids: list[int]) -> dict:
    """二次优化：基于 prev_kb 的人工编辑版 + 新指令 + 新补充资料 → 新版本。"""
    prev = get_version(prev_kb_id)
    if not prev:
        raise ValueError("前一版不存在")
    account_id = prev["account_id"]
    acc = db.get_account(account_id)
    company = acc.get("companyName") if acc else ""
    brand = acc.get("companyBrand") or company if acc else company
    if isinstance(brand, list):
        brand = brand[0] if brand else company

    # 安全:补充资料只能取本客户的,过滤越权 id
    additional_source_ids = _own_source_ids(account_id, additional_source_ids)
    add_texts = _merge_source_texts(additional_source_ids) if additional_source_ids else "（无）"

    base_content = edited_content or prev["content"]
    base_mods = _split_into_modules(base_content) or []
    prev_count = len([m for m in base_mods if (m.get("key") or "").upper().startswith("M")])
    module_roster = "\n".join(f"  - {m.get('key', '')} {m.get('title', '')}"
                              for m in base_mods) or "  （无明确模块编号）"

    prompt = KB_PROMPT_REFINE.format(
        company_name=company, brand_name=brand,
        prev_version=prev["version"],
        current_content=base_content,
        new_instruction=new_instruction,
        additional_source_texts=add_texts,
        module_count=prev_count or len(base_mods),
        module_roster=module_roster,
    )

    settings = db.get_all_settings()
    model = settings.get("qwen_model_name") or "qwen-plus"
    # 使用通义千问进行知识库优化
    content = call_llm_by_settings(
        settings,
        user_prompt=prompt,
        max_tokens=KB_MAX_OUTPUT_TOKENS,
        timeout=900,
        mode="qwen",
        model=model,
    )
    content = _strip_kb_preamble(content)

    # 完整性护栏：二次优化只允许"改/增"模块，绝不允许模块数减少（防 LLM 省略导致丢内容）
    new_count = len([m for m in (_split_into_modules(content) or [])
                     if (m.get("key") or "").upper().startswith("M")])
    if prev_count and new_count < prev_count:
        raise ValueError(
            f"优化结果模块数异常减少（{prev_count} → {new_count}），疑似 AI 省略了未改动模块，"
            f"已拒绝保存以保护原内容，请重试。")

    all_ids = list((prev.get("source_ids") and json.loads(prev["source_ids"])) or [])
    for sid in additional_source_ids or []:
        if sid not in all_ids:
            all_ids.append(sid)

    return _save_kb(
        account_id=account_id,
        content=content,
        instruction=new_instruction,
        source_ids=all_ids,
        parent_id=prev_kb_id,
        created_by="ai",
        llm_model=model,
    )


def save_human_edit(prev_kb_id: int, edited_content: str, comment: str = "") -> dict:
    """人工编辑保存为新版本（不调 LLM）。"""
    prev = get_version(prev_kb_id)
    if not prev:
        raise ValueError("前一版不存在")
    return _save_kb(
        account_id=prev["account_id"],
        content=edited_content,
        instruction=comment or "（人工编辑）",
        source_ids=list((prev.get("source_ids") and json.loads(prev["source_ids"])) or []),
        parent_id=prev_kb_id,
        created_by="human",
    )


def import_human_kb(account_id: int, content: str, comment: str = "") -> dict:
    """把离线定稿的 KB markdown 直接导入为新版本（不调 LLM、无需前一版）。
    该客户已有 KB 时挂在 current 之下;没有则创建 v1。自动设为 current。"""
    cur = get_current_version(account_id)
    parent_id = cur["id"] if cur else None
    src_ids: list = []
    if cur and cur.get("source_ids"):
        try:
            src_ids = list(json.loads(cur["source_ids"]) or [])
        except Exception:
            src_ids = []
    return _save_kb(
        account_id=account_id,
        content=content,
        instruction=comment or "（离线定稿导入）",
        source_ids=src_ids,
        parent_id=parent_id,
        created_by="human",
    )


# ════════════════════════════════════════════════════════
# 入口 A/B：从竞争分析报告导入 12 类资料清单
# ════════════════════════════════════════════════════════

# 12 类固定 key（与 brand_reporter.py:879-892 严格对齐，顺序不可改）
FIXED_CHECKLIST_KEYS = [
    "company_strength", "tech_depth", "product_line", "market_validation",
    "competitor_logic", "brand_story", "category_role", "design_aesthetic",
    "user_segmentation", "media_coverage", "official_source", "faq_scenarios",
]


def customer_kb_overview() -> list[dict]:
    """正式客户 + 各自 KB 摘要（用于「查看已有 KB」dialog）。
    返回每行：account_id / company_name / company_brand / user_type
              / kb_count / current_version / current_created_by / current_created_at
              / latest_version / latest_created_by / latest_kb_at / latest_kb_id
    排序：有 KB 的在前；按最近 KB 时间倒序；其它 ID 升序。
    """
    rows = db._fetchall(db.get_conn(),
                                """SELECT * FROM (
                                     SELECT a.id AS account_id, a.company_name, a.company_brand, a.user_type,
                                         COUNT(k.id) AS kb_count,
                                         MAX(CASE WHEN k.is_current=1 THEN k.version END) AS current_version,
                                         MAX(CASE WHEN k.is_current=1 THEN k.created_by END) AS current_created_by,
                                         MAX(CASE WHEN k.is_current=1 THEN k.created_at END) AS current_created_at,
                                         MAX(CASE WHEN k.is_current=1 THEN k.id END) AS current_kb_id,
                                         MAX(k.version) AS latest_version,
                                         SUBSTRING_INDEX(GROUP_CONCAT(k.created_by ORDER BY k.version DESC SEPARATOR ','), ',', 1) AS latest_created_by,
                                         MAX(k.created_at) AS latest_kb_at,
                                         MAX(k.id) AS latest_kb_id
                            FROM account a
                            LEFT JOIN customer_knowledge_kb k ON k.account_id = a.id
                            GROUP BY a.id, a.company_name, a.company_brand, a.user_type
                                ) t
                     ORDER BY (t.kb_count > 0) DESC, t.latest_kb_at DESC, t.account_id ASC""")
    return rows or []


def list_brand_reports(account_id: int) -> list[dict]:
    """该账户已完成的 brand 报告列表（KB 创建对话框下拉用）。
    返回字段附加 has_checklist / has_html，前端可据此提示。
    """
    conn = db.get_conn()
    rows = db._fetchall(conn,
        """SELECT id, account_id, period_start, period_end, status,
                  CASE WHEN resource_checklist_json IS NOT NULL
                       AND LENGTH(resource_checklist_json) > 10
                       THEN 1 ELSE 0 END AS has_checklist,
                  CASE WHEN html_content IS NOT NULL
                       AND LENGTH(html_content) > 100
                       THEN 1 ELSE 0 END AS has_html,
                  created_at, completed_at
           FROM weekly_report
           WHERE account_id=%s AND report_type='brand' AND status='completed'
           ORDER BY id DESC""",
        (account_id,))
    return rows or []


def _parse_checklist_from_html(html: str) -> Optional[dict]:
    """bs4 反向解析 brand_report HTML 里的「GEO 运营资料收集清单」section。"""
    if not html:
        return None
    try:
        from bs4 import BeautifulSoup
    except ImportError:
        raise RuntimeError("bs4 未安装，请 pip install beautifulsoup4")

    soup = BeautifulSoup(html, "html.parser")
    section = soup.find("section", id="s_resources")
    if not section:
        return None

    out: dict = {"intro": "", "categories": [], "delivery_phases": []}

    intro = section.select_one(".rc-intro")
    if intro:
        out["intro"] = intro.get_text(strip=True)

    for idx, card in enumerate(section.select(".rc-card")):
        title_el = card.select_one(".rc-card-title")
        title = title_el.get_text(strip=True) if title_el else ""
        required = "required" in (card.get("class") or [])

        desc, standard, examples = "", "", []
        for sec in card.select(".rc-card-section"):
            lbl = sec.select_one(".lbl")
            if not lbl:
                continue
            label = lbl.get_text(strip=True)
            v = sec.select_one(".val")
            v_text = v.get_text(strip=True) if v else ""
            if label.startswith("资料"):
                desc = v_text
            elif label.startswith("参考"):
                standard = v_text
            elif label.startswith("举例"):
                examples = [li.get_text(strip=True)
                            for li in sec.select("li")
                            if li.get_text(strip=True)]

        key = FIXED_CHECKLIST_KEYS[idx] if idx < len(FIXED_CHECKLIST_KEYS) else f"cat{idx+1}"
        out["categories"].append({
            "key": key, "title": title, "required": required,
            "description": desc, "standard": standard, "examples": examples,
        })

    for ph in section.select(".rc-phase"):
        name_el = ph.select_one(".rc-phase-name")
        items = [s.get_text(strip=True)
                 for s in ph.select(".rc-phase-items span")
                 if s.get_text(strip=True)]
        note_el = ph.select_one(".rc-phase-note")
        out["delivery_phases"].append({
            "phase": name_el.get_text(strip=True) if name_el else "",
            "items": items,
            "note": note_el.get_text(strip=True) if note_el else "",
        })

    return out if out["categories"] else None


def _render_one_card(idx: int, c: dict) -> list[str]:
    L = []
    title = c.get("title", "")
    badge = "★ " if c.get("required") else ""
    L.append(f"### {badge}{idx}. {title}")
    if c.get("description"):
        L.append(f"**资料描述：** {c['description']}")
    if c.get("standard"):
        L.append(f"**参考标准：** {c['standard']}")
    examples = c.get("examples") or []
    if examples:
        L.append("**举例：**")
        for ex in examples:
            L.append(f"- {ex}")
    L.append("")
    return L


def _render_checklist_to_markdown(checklist: dict, target_brand: str = "") -> str:
    """把 12 类清单 JSON 渲染成 KB markdown。"""
    lines: list[str] = ["# 客户知识库 · GEO 12 类资料清单"]
    if target_brand:
        lines.append(f"> 目标品牌：**{target_brand}**")
    lines.append("")
    if checklist.get("intro"):
        lines.append(f"> {checklist['intro']}")
        lines.append("")

    cats = checklist.get("categories") or []
    required_cats = [c for c in cats if c.get("required")]
    optional_cats = [c for c in cats if not c.get("required")]

    if required_cats:
        lines.append("## ★ 启动期必选（6 项）")
        lines.append("")
        for i, c in enumerate(required_cats, 1):
            lines.extend(_render_one_card(i, c))

    if optional_cats:
        lines.append("## 扩展 / 稳定期（6 项）")
        lines.append("")
        for i, c in enumerate(optional_cats, 1):
            lines.extend(_render_one_card(i, c))

    phases = checklist.get("delivery_phases") or []
    if phases:
        lines.append("## 📅 交付节奏建议")
        lines.append("")
        for ph in phases:
            lines.append(f"### {ph.get('phase', '')}")
            items = ph.get("items") or []
            if items:
                lines.append("- " + " / ".join(items))
            if ph.get("note"):
                lines.append(f"- _备注：{ph['note']}_")
            lines.append("")

    return "\n".join(lines).rstrip() + "\n"


def generate_kb_from_checklist(account_id: int, checklist: dict,
                                source_label: str = "",
                                instruction: str = "") -> dict:
    """把 12 类清单入库为 KB v_next。"""
    acc = db.get_account(account_id)
    target_brand = ""
    if acc:
        cb = acc.get("companyBrand") or acc.get("company_brand") or ""
        if isinstance(cb, list):
            target_brand = cb[0] if cb else ""
        elif isinstance(cb, str) and cb.strip().startswith("["):
            try:
                arr = json.loads(cb)
                target_brand = arr[0] if arr else ""
            except Exception:
                target_brand = cb
        else:
            target_brand = str(cb or "")

    md = _render_checklist_to_markdown(checklist, target_brand=target_brand)
    return _save_kb(
        account_id=account_id,
        content=md,
        instruction=(instruction or f"由竞争分析报告 12 类资料清单导入 [{source_label}]"),
        source_ids=[],
        parent_id=None,
        created_by="ai",
    )


def kb_from_brand_report(account_id: int, report_id: int) -> dict:
    """方式 A：从已完成 brand 报告生成 KB。
    优先读 resource_checklist_json，没有则反解析 html_content。
    """
    conn = db.get_conn()
    row = db._fetchone(conn,
        """SELECT id, account_id, period_start, period_end,
                  resource_checklist_json, html_content
           FROM weekly_report
           WHERE id=%s AND account_id=%s AND report_type='brand' AND status='completed'""",
        (report_id, account_id))
    if not row:
        raise ValueError("找不到该报告或不属于此账户")

    checklist = None
    rcj = (row.get("resource_checklist_json") or "").strip()
    if rcj:
        try:
            checklist = json.loads(rcj)
        except Exception:
            checklist = None
    if not checklist:
        html = row.get("html_content") or ""
        if html:
            try:
                checklist = _parse_checklist_from_html(html)
            except Exception:
                logger.exception("[kb] parse html checklist failed report=%s", report_id)

    if not checklist or not (checklist.get("categories") or []):
        raise ValueError("该报告未生成「GEO 运营资料收集清单」章节，无法导入；请重新生成报告时勾选 resources 模块")

    label = f"#{report_id} ({row.get('period_start','')}~{row.get('period_end','')})"
    return generate_kb_from_checklist(account_id, checklist,
                                       source_label=label,
                                       instruction=f"从竞争分析报告 {label} 导入 12 类资料清单")


def _llm_extract_checklist(text: str) -> Optional[dict]:
    """让 LLM 从给定文本中抽取 12 类资料清单 JSON（用于上传外部报告场景）。"""
    settings = db.get_all_settings()
    schema = '''{
  "intro": "总述（80-120 字，可空）",
  "categories": [
    {"key": "company_strength", "title": "公司实力/品牌背书", "required": true,
     "description": "...", "standard": "...", "examples": ["...", "..."]}
  ],
  "delivery_phases": []
}'''
    fixed = """前 6 项 required=true，后 6 项 required=false：
1. company_strength    公司实力/品牌背书
2. tech_depth          技术实力/专业深度
3. product_line        产品线结构说明
4. market_validation   真实市场验证/销量与口碑
5. competitor_logic    竞品对比逻辑
6. brand_story         品牌故事与企业定位
7. category_role       品类推荐中的品牌角色
8. design_aesthetic    设计感与审美表达
9. user_segmentation   用户分层与推荐逻辑
10. media_coverage     媒体报道与第三方引用
11. official_source    官方信息源与引用路径
12. faq_scenarios      FAQ 场景问答"""
    prompt = f"""你是 GEO 资料分析专家。下面是一份「品牌竞争分析报告」的全文。
请从中提取「GEO 运营资料收集清单」12 类内容（若原文有该章节，直接抽取；若没有，基于报告内容合理推断）。

固定 12 类（顺序、key、required 必须严格保持）：
{fixed}

每类必须给出：title（中文）、description（资料需求，30-60 字）、standard（参考标准，30-50 字）、examples（2 条，结合报告中提到的实际产品/场景）。

输出严格 JSON，不要 markdown 围栏，不要任何解释：
{schema}

报告原文：
---
{text}
---"""
    # 使用通义千问进行品牌分析
    raw = call_llm_by_settings(
        settings,
        user_prompt=prompt,
        max_tokens=8000,
        timeout=240,
        mode="qwen",
        model=settings.get("qwen_model_name") or "qwen-plus",
    )
    if not raw:
        return None
    raw = raw.strip()
    if raw.startswith("```"):
        raw = raw.split("```", 2)[1] if "```" in raw[3:] else raw[3:]
        if raw.lstrip().startswith("json"):
            raw = raw.lstrip()[4:]
    raw = raw.strip()
    try:
        return json.loads(raw)
    except Exception:
        s, e = raw.find("{"), raw.rfind("}")
        if s >= 0 and e > s:
            try:
                return json.loads(raw[s:e + 1])
            except Exception:
                return None
        return None


def kb_from_uploaded_report(account_id: int, file_name: str, file_bytes: bytes) -> dict:
    """方式 B：用户上传外部分析报告（HTML/PDF/DOCX），解析+LLM 抽取 12 类清单后入库。"""
    if not file_bytes:
        raise ValueError("文件为空")
    if len(file_bytes) > MAX_FILE_SIZE:
        raise ValueError(f"文件过大（>{MAX_FILE_SIZE//1024//1024}MB）")

    ext = Path(file_name).suffix.lower()
    text = ""
    checklist = None

    # HTML 优先尝试结构化反解析（与 brand_report 模板一致格式），失败再走文本+LLM
    if ext in (".html", ".htm"):
        try:
            html = file_bytes.decode("utf-8", errors="replace")
        except Exception:
            html = file_bytes.decode("gbk", errors="replace")
        try:
            checklist = _parse_checklist_from_html(html)
        except Exception:
            checklist = None
        if not checklist:
            from bs4 import BeautifulSoup
            text = BeautifulSoup(html, "html.parser").get_text("\n", strip=True)
    elif ext == ".pdf":
        text = _parse_pdf(_write_tmp(file_bytes, ext))
    elif ext == ".docx":
        text = _parse_docx(_write_tmp(file_bytes, ext))
    else:
        raise ValueError(f"不支持的报告格式：{ext}，仅支持 HTML / PDF / DOCX")

    if not checklist:
        if not text or len(text) < 100:
            raise ValueError("解析后文本过短或为空，无法提取资料清单")
        checklist = _llm_extract_checklist(text[:120_000])

    if not checklist or not (checklist.get("categories") or []):
        raise ValueError("无法从该报告中识别出「资料收集清单」结构")

    label = f"上传文件 {file_name}"
    return generate_kb_from_checklist(account_id, checklist,
                                       source_label=label,
                                       instruction=f"从上传的分析报告 [{file_name}] 抽取 12 类资料清单")


def _write_tmp(file_bytes: bytes, ext: str) -> Path:
    """落临时文件，复用现有的 _parse_pdf / _parse_docx。"""
    import tempfile
    tmp = tempfile.NamedTemporaryFile(prefix="kbreport_", suffix=ext, delete=False)
    tmp.write(file_bytes)
    tmp.close()
    return Path(tmp.name)


# ════════════════════════════════════════════════════════
# 导出 PDF / DOCX
# ════════════════════════════════════════════════════════

_EXPORT_CSS = """
@page { size: A4; margin: 22mm 18mm; @bottom-center {
  content: counter(page) " / " counter(pages); color: #94a3b8; font-size: 9pt; } }
body { font-family: 'PingFang SC','Microsoft YaHei','Source Han Sans CN','Noto Sans CJK SC',sans-serif;
       font-size: 11pt; line-height: 1.75; color: #1e293b; }
h1 { font-size: 22pt; color: #0f172a; border-bottom: 3px solid #6366f1;
     padding-bottom: 8pt; margin: 0 0 18pt; page-break-before: avoid; }
h2 { font-size: 16pt; color: #1e40af; margin-top: 24pt; margin-bottom: 10pt;
     padding: 6pt 12pt; background: #eef2ff; border-left: 4pt solid #6366f1;
     page-break-after: avoid; page-break-before: always; }
h2:first-of-type { page-break-before: avoid; }
h3 { font-size: 13pt; color: #334155; margin-top: 16pt; margin-bottom: 6pt;
     page-break-after: avoid; }
h4 { font-size: 12pt; color: #475569; margin-top: 12pt; margin-bottom: 4pt; }
p { margin: 6pt 0; }
ul, ol { margin: 4pt 0 4pt 18pt; padding-left: 12pt; }
li { margin: 2pt 0; }
strong { color: #0f172a; }
blockquote { border-left: 3pt solid #cbd5e1; padding: 6pt 12pt;
             color: #475569; background: #f8fafc; margin: 8pt 0;
             border-radius: 3pt; }
table { border-collapse: collapse; width: 100%; margin: 8pt 0; font-size: 10pt; }
th, td { border: 0.5pt solid #cbd5e1; padding: 5pt 9pt; vertical-align: top; }
th { background: #f1f5f9; font-weight: 700; color: #1e293b; text-align: left; }
code { background: #f1f5f9; padding: 1pt 4pt; border-radius: 3pt;
       font-family: 'Source Code Pro','SF Mono',Menlo,monospace; font-size: 9.5pt;
       color: #be185d; }
pre { background: #0f172a; color: #cbd5e1; padding: 9pt 12pt; border-radius: 4pt;
      overflow: auto; font-size: 9pt; line-height: 1.5; }
pre code { background: transparent; color: inherit; padding: 0; }
hr { border: none; border-top: 1pt dashed #cbd5e1; margin: 12pt 0; }
.kb-warn-tag {
  background: #fee2e2; color: #991b1b; font-weight: 700;
  padding: 2pt 8pt; border-radius: 3pt;
  border: 1pt solid #ef4444;
  display: inline-block;
}
.kb-warn-block {
  background: #fef3c7;
  border: 1.5pt solid #f59e0b;
  border-left: 6pt solid #ef4444;
  padding: 9pt 12pt;
  border-radius: 4pt;
  margin: 10pt 0;
  color: #7c2d12;
  font-weight: 600;
  page-break-inside: avoid;
}
.kb-warn-block p { margin: 4pt 0; }
.kb-warn-block p:first-child { margin-top: 0; }
.kb-warn-block p:last-child { margin-bottom: 0; }
.kb-warn-block strong { color: #b91c1c; font-weight: 700; }
.kb-warn-block .kb-warn-tag {
  background: #fff; color: #b91c1c; border-color: #b91c1c;
}
"""


def _safe_filename(name: str) -> str:
    """去除 Windows / Linux 文件名非法字符，并截断"""
    import re as _re2
    name = _re2.sub(r'[\\/:"*?<>|\x00-\x1f]+', '_', name or "")
    name = _re2.sub(r'\s+', '_', name).strip('_')
    return (name or "knowledge_base")[:180]


def _kb_meta(kb_row: dict) -> dict:
    acc = db.get_account(kb_row.get("account_id"))
    company = (acc or {}).get("companyName") or ""
    brand_raw = (acc or {}).get("companyBrand") or ""
    brand = ""
    if isinstance(brand_raw, list):
        brand = brand_raw[0] if brand_raw else ""
    elif isinstance(brand_raw, str) and brand_raw.strip().startswith("["):
        try:
            arr = json.loads(brand_raw)
            brand = arr[0] if arr else ""
        except Exception:
            brand = brand_raw
    else:
        brand = str(brand_raw or "")

    primary = brand or company  # 优先用品牌名做主标识
    version = kb_row.get("version") or "?"
    return {
        "company": company,
        "brand": brand,
        "primary": primary,
        "version": version,
        "created_at": kb_row.get("created_at") or "",
        # 命名格式：「品牌·知识库·v?」
        "title": f"{primary} · 知识库 · v{version}",
    }


def _kb_render_html(kb_row: dict) -> str:
    """KB markdown → styled HTML（用于 PDF + 预览复用）。"""
    import markdown as _md
    from bs4 import BeautifulSoup
    content = kb_row.get("content") or ""
    body_html = _md.markdown(
        content,
        extensions=["tables", "fenced_code", "nl2br", "sane_lists"],
        output_format="html5",
    )
    # 含 ⚠ 的整段 blockquote 改成红色 warning 块
    soup = BeautifulSoup(body_html, "html.parser")
    for bq in soup.find_all("blockquote"):
        txt = bq.get_text() or ""
        if ("⚠" in txt) or ("待客户确认" in txt) or ("待确认" in txt):
            bq.name = "div"
            classes = bq.get("class") or []
            if "kb-warn-block" not in classes:
                classes.append("kb-warn-block")
            bq["class"] = classes
    body_html = str(soup)
    body_html = (body_html
        .replace("⚠️ 待客户确认", '<span class="kb-warn-tag">⚠️ 待客户确认</span>')
        .replace("⚠ 待客户确认", '<span class="kb-warn-tag">⚠ 待客户确认</span>')
    )
    meta = _kb_meta(kb_row)
    # 不再加独立封面页(正文首段已含品牌标题 + 版本/日期),避免首页大片留白被当成空白页。
    return f"""<!DOCTYPE html><html lang="zh-CN"><head>
<meta charset="utf-8"><title>{meta['primary']} 品牌知识库 v{meta['version']}</title>
<style>{_EXPORT_CSS}</style></head>
<body>{body_html}</body></html>"""


def export_kb_pdf(kb_id: int) -> tuple[bytes, str]:
    """KB → PDF (weasyprint)。返回 (pdf_bytes, suggested_filename)。"""
    row = db._fetchone(db.get_conn(),
        "SELECT * FROM customer_knowledge_kb WHERE id=%s", (kb_id,))
    if not row:
        raise ValueError("KB 不存在")
    html = _kb_render_html(row)
    from weasyprint import HTML
    pdf = HTML(string=html).write_pdf()
    meta = _kb_meta(row)
    fname = _safe_filename(f"{meta['primary']}_知识库_v{meta['version']}.pdf")
    return pdf, fname


def export_kb_docx(kb_id: int) -> tuple[bytes, str]:
    """KB markdown → DOCX (pandoc + python-docx 后处理 ⚠ 高亮)。"""
    import subprocess, tempfile, os
    row = db._fetchone(db.get_conn(),
        "SELECT * FROM customer_knowledge_kb WHERE id=%s", (kb_id,))
    if not row:
        raise ValueError("KB 不存在")
    content = row.get("content") or ""
    meta = _kb_meta(row)
    date_str = (meta["created_at"] or "")[:10] or ""
    md_full = (
        f"# {meta['primary']}\n\n"
        f"## 品牌知识库\n\n"
        f"_Version {meta['version']}{('  ·  ' + date_str) if date_str else ''}_\n\n"
        f"---\n\n"
        f"{content}"
    )
    md_path = docx_path = ""
    try:
        with tempfile.NamedTemporaryFile(suffix=".md", delete=False) as fmd:
            fmd.write(md_full.encode("utf-8"))
            md_path = fmd.name
        docx_path = md_path[:-3] + ".docx"
        proc = subprocess.run(
            ["pandoc", md_path, "-o", docx_path,
             "--standalone", "--from=gfm", "--to=docx"],
            capture_output=True, timeout=60)
        if proc.returncode != 0:
            raise RuntimeError(f"pandoc 失败: {proc.stderr.decode('utf-8','replace')[:300]}")
        # 后处理：所有含 ⚠/待客户确认 的段落加黄底+红字+加粗
        _docx_highlight_warnings(docx_path)
        with open(docx_path, "rb") as fb:
            data = fb.read()
    finally:
        for p in (md_path, docx_path):
            if p and os.path.exists(p):
                try: os.unlink(p)
                except Exception: pass

    fname = _safe_filename(f"{meta['primary']}_知识库_v{meta['version']}.docx")
    return data, fname


def _docx_highlight_warnings(docx_path: str) -> None:
    """扫所有段落，含 ⚠ / 待客户确认 / 待确认 字样的段落加黄底 + 红字 + 加粗。"""
    try:
        from docx import Document
        from docx.shared import RGBColor
        from docx.oxml.ns import qn
        from docx.oxml import OxmlElement
    except ImportError:
        return  # 没装就算了

    needles = ("⚠", "待客户确认", "待确认")
    doc = Document(docx_path)

    def _has_warn(text: str) -> bool:
        return any(n in (text or "") for n in needles)

    def _shade_paragraph(para, fill_hex: str):
        pPr = para._element.get_or_add_pPr()
        # 先删旧 shading
        for old in pPr.findall(qn("w:shd")):
            pPr.remove(old)
        shd = OxmlElement("w:shd")
        shd.set(qn("w:val"), "clear")
        shd.set(qn("w:color"), "auto")
        shd.set(qn("w:fill"), fill_hex)
        pPr.append(shd)
        # 加左侧粗红边（用 paragraph border）
        pBdr = pPr.find(qn("w:pBdr"))
        if pBdr is None:
            pBdr = OxmlElement("w:pBdr")
            pPr.append(pBdr)
        for tag in ("left", "top", "bottom", "right"):
            old = pBdr.find(qn(f"w:{tag}"))
            if old is not None:
                pBdr.remove(old)
        left = OxmlElement("w:left")
        left.set(qn("w:val"), "single")
        left.set(qn("w:sz"), "24")     # 3pt
        left.set(qn("w:space"), "6")
        left.set(qn("w:color"), "B91C1C")
        pBdr.append(left)

    def _restyle_runs(para, color: RGBColor, bold: bool):
        # 至少要有一个 run 才能改格式；如果段落是空 run 列表，新建一个
        runs = para.runs
        if not runs:
            return
        for r in runs:
            r.font.color.rgb = color
            r.bold = bold

    red = RGBColor(0xB9, 0x1B, 0x1B)
    for para in doc.paragraphs:
        if _has_warn(para.text):
            _shade_paragraph(para, "FEF3C7")  # 黄色背景
            _restyle_runs(para, red, True)

    # 表格里也扫一遍
    for table in doc.tables:
        for row in table.rows:
            for cell in row.cells:
                for para in cell.paragraphs:
                    if _has_warn(para.text):
                        _shade_paragraph(para, "FEF3C7")
                        _restyle_runs(para, red, True)

    doc.save(docx_path)
