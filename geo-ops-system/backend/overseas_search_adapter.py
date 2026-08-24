"""查词适配器：任务编排 + Ka 异步接口对接。

对接内部 CloroTaskRecordKa 接口（tcloud-geo），流程：
  1. 批量提交关键词×平台 → 获得 localTaskId 列表
  2. 轮询 kaTaskDetail（~60s 间隔）直到全部完成
  3. 将结果写入 search_result 表

API 端点（固定 base_url）：
  - POST /firecrawl/kaTaskSubmit       单条提交
  - POST /firecrawl/kaTaskBatchSubmit  批量提交
  - POST /firecrawl/kaTaskDetail       查询详情

平台枚举：perplexity / chatGpt / google / gemini / bingCopilot / googleAIM
"""

from __future__ import annotations

import json
import logging
import threading
import time
import uuid
from datetime import datetime

import httpx

import db
from platforms import PLATFORM_MODEL_MAP, _normalize_platforms

logger = logging.getLogger(__name__)

# ═══════════════════════════════════════════
# Ka 接口配置（固定，无需系统设置）
# ═══════════════════════════════════════════

KA_BASE_URL = "https://api.71360.com/api/app/tcloud-geo"

# 前端平台展示名 → Ka 接口 platform 枚举值
PLATFORM_KA_MAP = {
    "ChatGPT": "chatGpt",
    "Google AIO": "google",
    "Google AIM": "googleAIM",
    "Gemini": "gemini",
    "Perplexity": "perplexity",
    "Copilot": "bingCopilot",
}

# 轮询配置
POLL_INTERVAL = 60      # 秒
POLL_MAX_WAIT = 600     # 最大等待 10 分钟


def _ka_post(endpoint: str, payload: dict, timeout: int = 30) -> dict:
    """向 Ka 接口发送 POST 请求，返回 data 字段或抛异常。"""
    url = f"{KA_BASE_URL.rstrip('/')}/{endpoint.lstrip('/')}"
    try:
        with httpx.Client(timeout=timeout, trust_env=False) as client:
            resp = client.post(url, json=payload)
        resp.raise_for_status()
        body = resp.json()
    except httpx.HTTPStatusError as e:
        logger.error("[Ka] HTTP %s %s: %s", e.response.status_code, url, e.response.text[:300])
        raise RuntimeError(f"Ka 接口错误 ({e.response.status_code}): {e.response.text[:200]}") from e
    except Exception as e:
        logger.exception("[Ka] 请求失败: %s", url)
        raise RuntimeError(f"Ka 请求异常: {e}") from e

    if body.get("code") != 200:
        msg = body.get("message", "未知错误")
        logger.warning("[Ka] 业务错误 code=%s msg=%s", body.get("code"), msg)
        raise RuntimeError(f"Ka 错误: {msg}")

    return body.get("data", body)


def submit_ka_tasks(tasks: list[dict]) -> list[dict]:
    """批量提交 Ka 查词任务。"""
    if not tasks:
        return []
    normalized = []
    for t in tasks:
        p = t.get("platform", "")
        if p in ("perplexity", "chatGpt", "google", "gemini", "bingCopilot", "googleAIM"):
            ka_platform = p
        else:
            ka_platform = PLATFORM_KA_MAP.get(p, p)
        normalized.append({
            "keyword": t["keyword"],
            "platform": ka_platform,
            "language": t.get("language", "en"),
        })
    all_results = []
    for i in range(0, len(normalized), 200):
        batch = normalized[i:i + 200]
        data = _ka_post("/firecrawl/kaTaskBatchSubmit", {"tasks": batch})
        if isinstance(data, list):
            all_results.extend(data)
        else:
            all_results.append(data)
    return all_results


def query_ka_detail(local_task_ids: list[int]) -> list[dict]:
    """查询 Ka 任务详情。"""
    if not local_task_ids:
        return []
    data = _ka_post("/firecrawl/kaTaskDetail", {"localTaskIds": local_task_ids})
    return data if isinstance(data, list) else [data]


def poll_ka_until_complete(local_task_ids: list[int],
                           interval: float = POLL_INTERVAL,
                           max_wait: float = POLL_MAX_WAIT,
                           on_progress=None) -> list[dict]:
    """轮询直到所有任务完成。"""
    start = time.time()
    pending = set(local_task_ids)
    final_map = {}
    while pending and (time.time() - start) < max_wait:
        batch = list(pending)
        results = query_ka_detail(batch)
        for r in results:
            tid = r.get("localTaskId")
            if tid is None:
                continue
            final_map[tid] = r
            status = r.get("status", "")
            if status in ("COMPLETED", "FAILED"):
                pending.discard(tid)
        done_count = len(local_task_ids) - len(pending)
        if on_progress:
            on_progress(done_count, len(local_task_ids), list(final_map.values()))
        if pending:
            remaining = max_wait - (time.time() - start)
            wait = min(interval, remaining)
            if wait > 0:
                time.sleep(wait)
    for tid in pending:
        if tid not in final_map:
            final_map[tid] = {"localTaskId": tid, "status": "FAILED", "errorMessage": "轮询超时"}
    return list(final_map.values())


def run_query(platform: str, model: str, keyword: str,
              brand: str = "", settings: dict | None = None) -> dict:
    """执行单条查询（同步包装 Ka 异步接口）。提交→轮询→返回结果。"""
    start = time.time()
    ka_platform = PLATFORM_KA_MAP.get(platform, model)
    try:
        submit_result = _ka_post("/firecrawl/kaTaskSubmit", {
            "keyword": keyword,
            "platform": ka_platform,
            "language": "en",
        })
        local_task_id = submit_result.get("localTaskId")
        submit_status = submit_result.get("status", "")
        if submit_status == "FAILED" or not local_task_id:
            err = submit_result.get("errorMessage", "提交失败")
            return _fail_result(err, time.time() - start)
        results = poll_ka_until_complete([local_task_id], interval=10, max_wait=300)
        if not results:
            return _fail_result("无返回结果", time.time() - start)
        task = results[0]
        return _parse_ka_result(task, time.time() - start)
    except Exception as exc:
        logger.exception("run_query[%s] failed for keyword=%s", platform, keyword[:50])
        return _fail_result(str(exc)[:500], time.time() - start)


def _parse_ka_result(task: dict, duration: float) -> dict:
    """将 Ka 任务结果转换为 run_query 约定格式。"""
    status = task.get("status", "")
    if status != "COMPLETED":
        err = task.get("errorMessage", "") or f"任务状态: {status}"
        return _fail_result(err[:500], duration)
    result_obj = task.get("result") or {}
    text = result_obj.get("text", "") or ""
    screenshot_url = task.get("screenshotUrl", "") or result_obj.get("remotePath", "") or ""
    summarys = result_obj.get("summarys") or []
    html_parts = [f"<p>{_escape_html(text)}</p>"]
    if summarys:
        html_parts.append("<div class='sources'><h4>来源</h4><ul>")
        for s in summarys[:8]:
            href = s.get("href", "#")
            title = s.get("title", "") or "来源"
            summ = s.get("summary", "") or ""
            html_parts.append(f"<li><a href='{_escape_html(href)}' target='_blank'>{_escape_html(title)}</a> - {_escape_html(summ)}</li>")
        html_parts.append("</ul></div>")
    answer_html = "\n".join(html_parts)
    response_json = json.dumps({"localTaskId": task.get("localTaskId"), "platform": task.get("platform"), "keyword": task.get("keyword"), "result": result_obj}, ensure_ascii=False)[:5000]
    return {
        "success": True, "answer_text": text, "answer_html": answer_html,
        "response_json": response_json, "screenshot_url": screenshot_url,
        "duration": round(duration, 2), "error_message": "",
    }


def _fail_result(error_message: str, duration: float) -> dict:
    return {"success": False, "answer_text": "", "answer_html": "", "response_json": "",
            "screenshot_url": "", "duration": round(duration, 2), "error_message": error_message}


def _escape_html(s: str) -> str:
    return s.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;").replace('"', "&quot;")


def _resolve_keywords(account_id: int, override_keywords) -> list[dict]:
    """取本次要查的关键词行 [{id, prompt, category, core}]。"""
    rows = db.get_keywords(account_id)
    if override_keywords:
        # 支持两种格式: 字符串列表 ['led light'] 或对象列表 [{'prompt':'led light','category':'test'}]
        want = set()
        for k in override_keywords:
            if isinstance(k, dict):
                p = (k.get("prompt") or "").strip()
            else:
                p = str(k).strip()
            if p:
                want.add(p)
        rows = [r for r in rows if (r.get("intentPrompt") or "").strip() in want]
    return [{"id": r.get("id"), "prompt": (r.get("intentPrompt") or "").strip(),
             "category": r.get("intentCategory") or "", "core": r.get("coreIntentWord") or ""}
            for r in rows if (r.get("intentPrompt") or "").strip()]


def start_search_for_account_async(account_id: int, override_models=None, override_keywords=None) -> dict:
    """创建 RUNNING 任务并立即返回；后台线程批量提交+轮询 Ka 接口，完成后落库置 COMPLETED。"""
    account = db.get_account(account_id)
    if not account:
        raise ValueError("账户不存在")
    logger.warning("[DEBUG-ADAPTER] override_models=%s, account.platforms=%s", override_models, account.get("platforms"))
    platforms = _normalize_platforms(override_models or account.get("platforms") or [])
    logger.warning("[DEBUG-ADAPTER] after normalize=%s, PLATFORM_MODEL_MAP keys=%s", platforms, list(PLATFORM_MODEL_MAP.keys()))
    platforms = [p for p in platforms if p in PLATFORM_MODEL_MAP]
    if not platforms:
        raise ValueError("请先为该客户配置查询平台")
    keywords = _resolve_keywords(account_id, override_keywords)
    if not keywords:
        raise ValueError("该客户尚未配置关键词（提示词）")
    brand = account.get("companyBrand") or ""
    total = len(keywords) * len(platforms)
    task_id = str(uuid.uuid4())
    db.create_search_task(task_id, account_id, total, status="RUNNING", source="internal_manual")
    t = threading.Thread(target=_run_task_worker_ka, args=(task_id, account_id, brand, keywords, platforms), daemon=True)
    t.start()
    return {"taskId": task_id, "status": "RUNNING", "total": total, "completed": 0}


def _run_task_worker_ka(task_id, account_id, brand, keywords, platforms):
    """后台执行：批量提交 → 轮询 → 落库 → COMPLETED。"""
    search_date = datetime.now().strftime("%Y-%m-%d")
    try:
        tasks_to_submit = []
        kw_map = {kw["prompt"]: kw for kw in keywords}
        for kw in keywords:
            for platform in platforms:
                tasks_to_submit.append({"keyword": kw["prompt"], "platform": platform, "language": "en"})
        all_submitted = []
        completed_submit = 0
        for i in range(0, len(tasks_to_submit), 200):
            batch = tasks_to_submit[i:i + 200]
            results = submit_ka_tasks(batch)
            for j, r in enumerate(results):
                all_submitted.append({"localTaskId": r.get("localTaskId"), "keyword": batch[j]["keyword"], "platform": batch[j]["platform"], "status": r.get("status", "FAILED"), "errorMessage": r.get("errorMessage", "")})
            completed_submit += len(batch)
            db.update_search_task_progress(task_id, completed_submit, f"已提交 {completed_submit}/{len(tasks_to_submit)}")
        valid_ids = [t["localTaskId"] for t in all_submitted if t["localTaskId"]]
        if valid_ids:
            def on_progress(done, total_cnt, results):
                db.update_search_task_progress(task_id, done, f"查询中 {done}/{total_cnt}")
            final_results = poll_ka_until_complete(valid_ids, interval=POLL_INTERVAL, max_wait=POLL_MAX_WAIT, on_progress=on_progress)
            result_map = {r["localTaskId"]: r for r in final_results}
        else:
            result_map = {}
        saved = 0
        for entry in all_submitted:
            tid = entry["localTaskId"]
            ka_result = result_map.get(tid) if tid else {}
            status = ka_result.get("status", entry.get("status", "FAILED"))
            result_obj = ka_result.get("result") or {}
            text = result_obj.get("text", "") or ""
            screenshot_url = (ka_result.get("screenshotUrl", "") or result_obj.get("remotePath", "") or "")
            error_msg = (ka_result.get("errorMessage", "") or entry.get("errorMessage", ""))
            kw_entry = kw_map.get(entry["keyword"], keywords[0])
            db.save_search_result({
                "task_id": task_id, "account_id": account_id, "keyword_id": kw_entry.get("id"),
                "platform": entry["platform"], "model": PLATFORM_MODEL_MAP.get(entry["platform"], entry["platform"]),
                "keyword": entry["keyword"], "intent_category": kw_entry.get("category", ""),
                "core_intent_word": kw_entry.get("core", ""), "intent_prompt": entry["keyword"],
                "success": 1 if status == "COMPLETED" else 0,
                "response_json": json.dumps(ka_result, ensure_ascii=False)[:5000],
                "answer_text": text, "answer_html": "", "screenshot_url": screenshot_url,
                "duration": 0, "attempt": 1, "error_message": error_msg[:500] if error_msg else "",
                "rescue_round": "initial", "search_date": search_date,
            })
            saved += 1
        db.update_search_task_status(task_id, "COMPLETED")
        logger.info("[Ka] 任务 %s 完成: %d/%d 条已保存", task_id, saved, len(all_submitted))
    except Exception:
        logger.exception("[Ka] search task worker crashed")
        try:
            db.update_search_task_status(task_id, "ERROR", "查词执行异常")
        except Exception:
            pass