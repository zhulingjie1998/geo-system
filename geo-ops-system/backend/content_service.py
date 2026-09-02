# -*- coding: utf-8 -*-
"""智能生文 — 内容生成服务层。

职责:
  1. generate_topics()  — 根据关键词 + KB 模块摘要，调用 LLM 生成差异化主题列表
  2. generate_article() — 根据指令 + 主题 + KB 模块内容，调用 Qwen 生成单篇文章
  3. DB 读写: content_draft_batch / content_draft 表的 CRUD
"""
from __future__ import annotations

import json
import logging
import threading
import uuid
from datetime import datetime
from typing import Any, Optional

import db
import kb_service
import llm_qwen

logger = logging.getLogger(__name__)

# ============================================================
# 辅助
# ============================================================

def _now() -> str:
    return datetime.now().strftime("%Y-%m-%d %H:%M:%S")


def _get_kb_modules(account_id: int, module_keys: list[str] | None) -> list[dict]:
    """取当前 KB 版本中指定模块的完整内容。"""
    eff_id = kb_service.resolve_kb_account(account_id)
    row = kb_service.get_current_version(eff_id)
    if not row:
        return []
    all_modules = row.get("modules") or []
    if not module_keys:
        return all_modules
    return [m for m in all_modules if m.get("key") in module_keys]


def _kb_context_text(modules: list[dict]) -> str:
    """把 KB 模块列表拼成 LLM 可读的上下文文本。"""
    if not modules:
        return "(无知识库内容)"
    parts = []
    for m in modules:
        title = m.get("title") or m.get("key") or ""
        body = (m.get("content") or "").strip()
        parts.append(f"### {title}\n{body}")
    return "\n\n".join(parts)


# ============================================================
# 语言支持
# ============================================================

def _get_language_name(code: str) -> str:
    """根据语言代码返回语言名称（用于 system prompt）"""
    lang_map = {
        'zh-CN': '简体中文', 'zh-TW': '繁體中文',
        'en-US': 'American English', 'en-GB': 'British English',
        'ja-JP': '日本語', 'ko-KR': '한국어',
        'vi-VN': 'Tiếng Việt', 'th-TH': 'ภาษาไทย',
        'id-ID': 'Bahasa Indonesia', 'ms-MY': 'Bahasa Melayu',
        'fil-PH': 'Filipino',
        'fr-FR': 'Français', 'de-DE': 'Deutsch',
        'es-ES': 'Español', 'es-MX': 'Español (Latinoamérica)',
        'it-IT': 'Italiano', 'pt-PT': 'Português (Portugal)',
        'pt-BR': 'Português (Brasil)', 'nl-NL': 'Nederlands',
        'pl-PL': 'Polski', 'ru-RU': 'Русский',
        'uk-UA': 'Українська', 'ar-SA': 'العربية',
        'hi-IN': 'हिन्दी', 'ta-IN': 'தமிழ்',
        'tr-TR': 'Türkçe', 'sv-SE': 'Svenska',
        'da-DK': 'Dansk', 'fi-FI': 'Suomi',
        'nb-NO': 'Norsk', 'el-GR': 'Ελληνικά',
        'cs-CZ': 'Čeština', 'ro-RO': 'Română',
        'hu-HU': 'Magyar', 'bg-BG': 'Български',
        'he-IL': 'עברית', 'fa-IR': 'فارسی',
        'ur-PK': 'اردو', 'bn-BD': 'বাংলা',
        'sw-KE': 'Swahili', 'zu-ZA': 'Zulu',
        'km-KH': 'ខ្មែរ', 'lo-LA': 'ພາສາລາວ',
        'my-MM': 'မြန်မာဘာသာ', 'te-IN': 'తెలుగు',
        'kn-IN': 'ಕನ್ನಡ',
    }
    return lang_map.get(code, code) or '简体中文'


def _get_language_instruction(code: str) -> str:
    """根据语言代码生成语言相关的指令提示"""
    # 特殊语言的额外指令
    special_instructions = {
        'zh-CN': '# 输出要求\n- 请使用**简体中文**输出文章\n- 使用规范的中文标点符号',
        'zh-TW': '# 輸出要求\n- 請使用**繁體中文**輸出文章\n- 使用規範的中文標點符號',
        'en-US': '# Output Requirements\n- Please write in **American English**\n- Use proper English grammar and spelling (US conventions)',
        'en-GB': '# Output Requirements\n- Please write in **British English**\n- Use proper English grammar and spelling (UK conventions)',
        'ja-JP': '# 出力要件\n- **日本語**で記事を執筆してください\n- 適切な日本語の文法と表現を使用してください',
        'ko-KR': '# 출력 요구사항\n- **한국어**로 기사를 작성해주세요\n- 적절한 한국어 문법과 표현을 사용하세요',
        'th-TH': '# ความต้องการในการส่งออก\n- กรุณาเขียนบทความเป็น**ภาษาไทย**\n- ใช้ไวยากรณ์และการสะกดที่ถูกต้อง',
        'vi-YV': '# Yêu cầu đầu ra\n- Viết bài bằng **Tiếng Việt**\n- Sử dụng ngữ pháp và chính tả tiếng Việt chuẩn',
        'ar-SA': '# متطلبات الإخراج\n- يرجى كتابة المقالة باللغة **العربية**\n- استخدم القواعد والنحو العربي الصحيح',
    }
    
    base_instruction = f'# 输出语言\n- 请使用 **{_get_language_name(code)}** 输出整篇文章'
    
    return special_instructions.get(code, base_instruction)


# ============================================================
# DB CRUD — content_draft_batch
# ============================================================

def create_batch(*, user_id: int, account_id: int, name: str,
                 template_id: int, llm_provider: str,
                 kb_module_keys: str, user_instruction: str,
                 word_min: int | None, word_max: int | None,
                 source_kind: str, source_topics: str,
                 total_count: int, gen_mode: str = "type",
                 type_keys: str | None = None, focus_note: str | None = None) -> int:
    now = _now()
    with db.transaction() as conn:
        db._exec(conn,
            """INSERT INTO content_draft_batch
               (name, user_id, account_id, template_id, llm_provider,
                kb_module_keys, user_instruction, word_min, word_max,
                source_kind, source_topics, total_count, done_count, failed_count,
                status, created_at, updated_at, gen_mode, type_keys, focus_note)
               VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,0,0,'pending',%s,%s,%s,%s,%s)""",
            (name, user_id, account_id, template_id, llm_provider,
             kb_module_keys, user_instruction, word_min, word_max,
             source_kind, source_topics, total_count,
             now, now, gen_mode, type_keys, focus_note))
        row = db._fetchone(conn, "SELECT LAST_INSERT_ID() AS id")
        return int((row or {}).get("id") or 0)


def update_batch_status(batch_id: int, *, status: str,
                        done_count: int | None = None,
                        failed_count: int | None = None):
    parts = ["status=%s", "updated_at=%s"]
    args: list = [status, _now()]
    if done_count is not None:
        parts.append("done_count=%s"); args.append(int(done_count))
    if failed_count is not None:
        parts.append("failed_count=%s"); args.append(int(failed_count))
    args.append(batch_id)
    with db.transaction() as conn:
        db._exec(conn, f"UPDATE content_draft_batch SET {', '.join(parts)} WHERE id=%s", tuple(args))


def get_batch(batch_id: int) -> Optional[dict]:
    conn = db.get_conn()
    return db._fetchone(conn, "SELECT * FROM content_draft_batch WHERE id=%s", (batch_id,))


def list_batches(account_id: int | None = None, limit: int = 50) -> list[dict]:
    conn = db.get_conn()
    if account_id:
        rows = db._fetchall(conn,
            "SELECT * FROM content_draft_batch WHERE account_id=%s ORDER BY id DESC LIMIT %s",
            (account_id, limit))
    else:
        rows = db._fetchall(conn,
            "SELECT * FROM content_draft_batch ORDER BY id DESC LIMIT %s", (limit,))
    return [dict(r) for r in rows]


# ============================================================
# DB CRUD — content_draft
# ============================================================

def create_draft(*, batch_id: int, user_id: int, account_id: int,
                 template_id: int, topic: str, variant_index: int = 1,
                 llm_provider: str = "qwen", llm_model: str | None = None,
                 extra_instruction: str | None = None) -> int:
    now = _now()
    with db.transaction() as conn:
        db._exec(conn,
            """INSERT INTO content_draft
               (batch_id, user_id, account_id, template_id, topic, variant_index,
                llm_provider, llm_model, extra_instruction, gen_kind, status, created_at, updated_at)
               VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,'fresh','pending',%s,%s)""",
            (batch_id, user_id, account_id, template_id, topic, variant_index,
             llm_provider, llm_model, extra_instruction, now, now))
        row = db._fetchone(conn, "SELECT LAST_INSERT_ID() AS id")
        return int((row or {}).get("id") or 0)


def update_draft_status(draft_id: int, *, status: str,
                        title: str | None = None,
                        content: str | None = None,
                        word_count: int | None = None,
                        error_msg: str | None = None):
    parts = ["status=%s", "updated_at=%s"]
    args: list = [status, _now()]
    if title is not None:
        parts.append("title=%s"); args.append(title)
    if content is not None:
        parts.append("content=%s"); args.append(content)
    if word_count is not None:
        parts.append("word_count=%s"); args.append(int(word_count))
    if error_msg is not None:
        parts.append("error_msg=%s"); args.append(error_msg[:1500] if error_msg else None)
    args.append(draft_id)
    with db.transaction() as conn:
        db._exec(conn, f"UPDATE content_draft SET {', '.join(parts)} WHERE id=%s", tuple(args))


def get_draft(draft_id: int) -> Optional[dict]:
    conn = db.get_conn()
    return db._fetchone(conn, "SELECT * FROM content_draft WHERE id=%s", (draft_id,))


def list_drafts_by_batch(batch_id: int) -> list[dict]:
    conn = db.get_conn()
    rows = db._fetchall(conn,
        "SELECT * FROM content_draft WHERE batch_id=%s ORDER BY variant_index ASC, id ASC",
        (batch_id,))
    return [dict(r) for r in rows]


# ============================================================
# 主题生成
# ============================================================

def generate_topics(account_id: int, keywords: list[dict],
                    kb_module_keys: list[str] | None,
                    count: int, prompt: str) -> list[dict]:
    """调用 LLM 生成差异化主题列表。

    Args:
        account_id: 客户 ID
        keywords: [{id, word}]
        kb_module_keys: 引用的 KB 模块 key 列表
        count: 需要生成的主题数
        prompt: 前端构建好的 prompt
    Returns:
        [{keyword, title, angle, targetAudience, _keywordId}]
    """
    settings = db.get_all_settings()
    model = settings.get("qwen_model_name") or "qwen-plus"

    try:
        raw = llm_qwen.call_qwen(
            settings,
            user_prompt=prompt,
            system_prompt="你是一个专业的 SEO 内容策划师，擅长生成差异化主题。",
            max_tokens=4096,
            timeout=120,
            model=model,
            temperature=0.8,
        )
        # 尝试解析 JSON
        topics = _parse_json_response(raw)
        if topics:
            # 补充 _keywordId
            kw_map = {kw["word"]: kw.get("id") for kw in keywords}
            for t in topics:
                t["_keywordId"] = kw_map.get(t.get("keyword"))
            return topics[:count]
    except Exception as e:
        logger.exception("[content] generate_topics LLM call failed: %s", e)

    # Fallback: 本地模拟
    return _fallback_topics(keywords, count)


def _parse_json_response(text: str) -> list[dict] | None:
    """从 LLM 返回文本中提取 JSON 数组。"""
    if not text:
        return None
    text = text.strip()
    # 去掉 markdown 代码块
    if text.startswith("```"):
        lines = text.split("\n")
        lines = [l for l in lines if not l.strip().startswith("```")]
        text = "\n".join(lines)
    # 尝试直接解析
    try:
        data = json.loads(text)
        if isinstance(data, list):
            return data
        if isinstance(data, dict) and "topics" in data:
            return data["topics"]
    except json.JSONDecodeError:
        pass
    # 尝试提取第一个 JSON 数组
    import re
    m = re.search(r'\[.*?\]', text, re.DOTALL)
    if m:
        try:
            return json.loads(m.group(0))
        except json.JSONDecodeError:
            pass
    return None


def _fallback_topics(keywords: list[dict], count: int) -> list[dict]:
    angles = [
        "产品深度评测", "技术原理解析", "实际应用案例",
        "行业趋势洞察", "选购指南", "竞品对比分析",
        "常见问题解答", "新手入门指南", "维护保养技巧", "市场前景分析",
    ]
    topics = []
    angle_idx = 0
    for kw in keywords:
        cnt = kw.get("count") or 1
        for i in range(cnt):
            if len(topics) >= count:
                break
            angle = angles[angle_idx % len(angles)]
            topics.append({
                "keyword": kw["word"],
                "title": f"{kw['word']}：{angle}",
                "angle": angle,
                "targetAudience": "潜在采购决策者",
                "_keywordId": kw.get("id"),
            })
            angle_idx += 2
        if len(topics) >= count:
            break
    return topics[:count]


# ============================================================
# 文章生成
# ============================================================

def generate_article(*, account_id: int, instruction: str,
                     model: str | None, keyword: str,
                     topic_title: str, topic_angle: str,
                     supplement: str, kb_module_ids: list,
                     language: str = "zh-CN",
                     metadata: dict | None = None) -> dict:
    """调用 Qwen 生成单篇文章。

    Args:
        language: 输出语言代码，如 zh-CN, en-US, ja-JP 等

    Returns:
        {article_id, title, content, word_count}
    """
    settings = db.get_all_settings()
    # 强制使用通义千问（忽略前端传来的 claude 等其他模型）
    if model and not model.startswith('qwen') and not model.startswith('qw-'):
        logger.warning("[content] 前端传入非Qwen模型(%s)，强制切换为qwen-plus", model)
        model = None
    qwen_model = model or settings.get("qwen_model_name") or "qwen-plus"

    # 获取 KB 模块内容
    kb_modules = _get_kb_modules(account_id, kb_module_ids)
    kb_context = _kb_context_text(kb_modules)

    # 根据语言代码构建语言指令
    lang_instruction = _get_language_instruction(language)

    # 构建完整 prompt
    user_prompt = f"""# 写作指令
{instruction}

# 主题信息
- 关键词：{keyword}
- 主题标题：{topic_title}
- 写作角度：{topic_angle}

# 重点补充（最高优先级）
{supplement or '（无）'}

# 客户知识库参考内容
{kb_context}

{lang_instruction}

请根据以上信息，撰写一篇高质量的文章。直接输出文章正文（含标题），不要输出其他说明。"""

    try:
        content = llm_qwen.call_qwen(
            settings,
            user_prompt=user_prompt,
            system_prompt=f"你是一个专业的内容创作者，擅长根据知识库素材和写作指令生成高质量文章。请用{_get_language_name(language)}输出内容。",
            max_tokens=8192,
            timeout=300,
            model=qwen_model,
            temperature=0.7,
        )
    except Exception as e:
        logger.exception("[content] generate_article LLM call failed: %s", e)
        raise

    # 提取标题（第一行如果以 # 开头）
    title = topic_title
    lines = content.strip().split("\n")
    if lines and lines[0].strip().startswith("#"):
        title = lines[0].strip().lstrip("#").strip()
        # 去掉标题行，保留正文
        content = "\n".join(lines[1:]).strip()
    elif lines and len(lines[0].strip()) < 100:
        # 第一行短文本作为标题
        title = lines[0].strip()
        content = "\n".join(lines[1:]).strip()

    word_count = len(content)

    # 保存到 content_draft 表（自动创建批次以便在内容库中显示）
    user_id = (metadata or {}).get("user_id") or 0
    
    # 自动创建批次（单篇生成也创建批次，方便内容库展示）
    batch_name = f"智能生文-{topic_title[:30]}" if topic_title else "智能生文"
    batch_id = create_batch(
        user_id=user_id,
        account_id=account_id,
        name=batch_name,
        template_id=0,
        llm_provider="qwen",
        kb_module_keys=",".join(str(x) for x in (kb_module_ids or [])),
        user_instruction=instruction[:2000] if instruction else "",
        word_min=None,
        word_max=None,
        source_kind="ai-write",
        source_topics=topic_title or "",
        total_count=1,
        gen_mode="single",
    )
    
    # 创建草稿并关联到批次
    draft_id = create_draft(
        batch_id=batch_id,  # 使用新创建的批次ID
        user_id=user_id, account_id=account_id,
        template_id=0, topic=topic_title, variant_index=1,
        llm_provider="qwen", llm_model=qwen_model,
        extra_instruction=instruction[:2000] if instruction else None,
    )
    
    # 更新草稿状态和批次状态
    update_draft_status(draft_id, status="done", title=title,
                        content=content, word_count=word_count)
    
    # 更新批次为完成状态
    update_batch_status(batch_id, status="done", done_count=1)

    return {
        "article_id": draft_id,
        "title": title,
        "content": content,
        "word_count": word_count,
    }


# ============================================================
# 批量生成（后台线程）
# ============================================================

def _do_batch_generate(batch_id: int, tasks: list[dict]):
    """后台线程:逐个执行生成任务。"""
    done = 0
    failed = 0
    total = len(tasks)

    for i, task in enumerate(tasks):
        try:
            update_batch_status(batch_id, status="running")
            result = generate_article(
                account_id=task["account_id"],
                instruction=task["instruction"],
                model=task["model"],
                keyword=task["keyword"],
                topic_title=task["topic_title"],
                topic_angle=task["topic_angle"],
                supplement=task["supplement"],
                kb_module_ids=task["kb_module_ids"],
                metadata={"user_id": task.get("user_id", 0)},
            )
            done += 1
        except Exception as e:
            logger.exception("[content] batch task %d/%d failed: %s", i + 1, total, e)
            failed += 1

    if failed == total:
        update_batch_status(batch_id, status="failed", done_count=done, failed_count=failed)
    elif failed > 0:
        update_batch_status(batch_id, status="partial_failed", done_count=done, failed_count=failed)
    else:
        update_batch_status(batch_id, status="done", done_count=done, failed_count=failed)


def start_batch_generate(*, batch_id: int, tasks: list[dict]):
    """启动后台批量生成线程。"""
    t = threading.Thread(target=_do_batch_generate, args=(batch_id, tasks), daemon=True)
    t.start()
    return t
