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
POLL_INTERVAL = 8       # 秒（基础轮询频率）
POLL_MAX_WAIT = 1800    # 最大等待 30 分钟（适应大规模任务）
POLL_BACKOFF_MAX = 30   # 最大退避间隔（秒），当大量任务排队时自动放慢

# 批量提交配置
BATCH_SIZE = 20          # 每批任务数
BATCH_SUBMIT_DELAY = 2   # 批次间延迟（秒），避免API限流
MAX_CONCURRENT_SUBMITS = 5  # 最大并发提交批次数

# 并行轮询配置
PARALLEL_POLL_START_DELAY = 10  # 提交开始后多少秒启动轮询线程（秒）

# 截图补全配置
SCREENSHOT_MAX_WAIT = 600  # 截图最大等待时间（10分钟，适应大规模任务）
SCREENSHOT_POLL_INTERVAL = 15  # 截图轮询间隔（秒）
SCREENSHOT_SUCCESS_STATUSES = ("COMPLETED", "RENDERING")  # 有文本内容即视为成功

# 最终等待配置（QUEUED/RENDERING任务）
FINAL_PENDING_MAX_WAIT = 300  # 最终等待未完成任务的最大时间（5分钟）
FINAL_PENDING_POLL_INTERVAL = 10  # 最终等待期间的轮询间隔

# 重试配置
MAX_RETRIES = 3          # 最大重试次数
RETRY_DELAY = 5          # 重试间隔秒数

# 大规模任务阈值
LARGE_TASK_THRESHOLD = 500  # 超过此数量视为大规模任务


def _ka_post(endpoint: str, payload: dict, timeout: int = 60) -> dict:
    """向 Ka 接口发送 POST 请求，返回 data 字段或抛异常。带自动重试。"""
    url = KA_BASE_URL.rstrip("/") + "/" + endpoint.lstrip("/")
    print(f"[DEBUG-KA-POST] 请求: {endpoint}, timeout={timeout}", flush=True)
    last_exc = None
    for attempt in range(1, MAX_RETRIES + 1):
        body = None
        try:
            print(f"[DEBUG-KA-POST] 尝试 {attempt}/{MAX_RETRIES}: 发送HTTP请求...", flush=True)
            with httpx.Client(timeout=timeout, trust_env=False) as client:
                resp = client.post(url, json=payload)
            print(f"[DEBUG-KA-POST] HTTP响应: status={resp.status_code}", flush=True)
            resp.raise_for_status()
            body = resp.json()
        except httpx.HTTPStatusError as e:
            err_msg = "Ka HTTP error ({}): {}".format(e.response.status_code, e.response.text[:200])
            logger.error("[Ka] %s %s (attempt %d/%d): %s", e.response.status_code, url, attempt, MAX_RETRIES, e.response.text[:300])
            last_exc = RuntimeError(err_msg)
            last_exc.__cause__ = e
            if e.response.status_code < 500 or attempt >= MAX_RETRIES:
                raise last_exc
        except Exception as e:
            logger.exception("[Ka] request failed (attempt %d/%d): %s", attempt, MAX_RETRIES, url)
            last_exc = RuntimeError("Ka request error: {}".format(e))
            last_exc.__cause__ = e
            if attempt >= MAX_RETRIES:
                raise last_exc

        # check business error code
        if body is not None:
            if body.get("code") != 200:
                msg = body.get("message", "unknown error")
                logger.warning("[Ka] biz error code=%s msg=%s (attempt %d/%d)", body.get("code"), msg, attempt, MAX_RETRIES)
                last_exc = RuntimeError("Ka error: {}".format(msg))
                # retry only on server busy
                busy_keywords = ["\u7e41\u5fd9", " busy", " retry"]
                is_busy = any(kw in msg.lower() for kw in busy_keywords)
                if is_busy and attempt < MAX_RETRIES:
                    logger.info("[Ka] waiting %ds before retry...", RETRY_DELAY)
                    time.sleep(RETRY_DELAY)
                    continue
                raise last_exc

            return body.get("data", body)

        # body is None means exception occurred, wait and retry
        if attempt < MAX_RETRIES:
            logger.info("[Ka] waiting %ds before attempt %d...", RETRY_DELAY, attempt + 1)
            time.sleep(RETRY_DELAY)

    raise last_exc or RuntimeError("Ka request failed: max retries exceeded")


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
        language = t.get("language", "en")
        if ka_platform == "gemini" and language in ("", None, "en"):
            language = "US"
        normalized.append({
            "keyword": t["keyword"],
            "platform": ka_platform,
            "language": language,
        })
    all_results = []
    print(f"[DEBUG-KA] submit_ka_tasks: 共 {len(normalized)} 个任务, 分批处理", flush=True)
    for i in range(0, len(normalized), BATCH_SIZE):
        batch = normalized[i:i + BATCH_SIZE]
        print(f"[DEBUG-KA] 提交批次 {i//BATCH_SIZE+1}: {len(batch)} 个任务", flush=True)
        data = _ka_post("/firecrawl/kaTaskBatchSubmit", {"tasks": batch}, timeout=120)
        print(f"[DEBUG-KA] 批次 {i//BATCH_SIZE+1} 返回: {type(data)}, 长度={len(data) if isinstance(data, list) else 1}", flush=True)
        if isinstance(data, list):
            all_results.extend(data)
        else:
            all_results.append(data)
    print(f"[DEBUG-KA] submit_ka_tasks 完成: 共返回 {len(all_results)} 个结果", flush=True)
    return all_results


def query_ka_detail(local_task_ids: list[int]) -> list[dict]:
    """查询 Ka 任务详情（分批查询避免超时）。"""
    if not local_task_ids:
        return []
    all_results = []
    # 分批查询，每批最多30个ID
    batch_size = 30
    for i in range(0, len(local_task_ids), batch_size):
        batch = local_task_ids[i:i + batch_size]
        try:
            data = _ka_post("/firecrawl/kaTaskDetail", {"localTaskIds": batch})
            if isinstance(data, list):
                all_results.extend(data)
            elif data:
                all_results.append(data)
        except Exception as e:
            logger.warning("[Ka] query_ka_detail batch failed: %s", e)
            # 为这批创建失败结果
            for tid in batch:
                all_results.append({"localTaskId": tid, "status": "FAILED", "errorMessage": str(e)[:200]})
    return all_results


def poll_ka_until_complete(local_task_ids: list[int],
                           interval: float = POLL_INTERVAL,
                           max_wait: float = POLL_MAX_WAIT,
                           on_progress=None,
                           on_result=None) -> list[dict]:
    """轮询直到所有任务完成。on_result 回调用于实时保存单条结果。"""
    start = time.time()
    pending = set(local_task_ids)
    final_map = {}
    print(f"[DEBUG-KA-POLL] poll_ka_until_complete 开始: {len(pending)} 个任务, max_wait={max_wait}s", flush=True)
    while pending and (time.time() - start) < max_wait:
        batch = list(pending)
        print(f"[DEBUG-KA-POLL] 轮询中... 剩余 {len(pending)} 个, 已用时 {time.time()-start:.1f}s", flush=True)
        try:
            results = query_ka_detail(batch)
            print(f"[DEBUG-KA-POLL] 查询返回 {len(results)} 条结果", flush=True)
        except Exception as e:
            logger.warning("[Ka] query_ka_detail failed: %s, retrying...", e)
            time.sleep(5)
            continue
        for r in results:
            tid = r.get("localTaskId")
            if tid is None:
                continue
            final_map[tid] = r
            status = r.get("status", "")
            if status in ("COMPLETED", "FAILED"):
                pending.discard(tid)
                # 实时回调：每完成一条就通知调用方保存
                if on_result:
                    try:
                        on_result(r)
                    except Exception:
                        pass
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
    language = "US" if ka_platform == "gemini" else "en"
    try:
        submit_result = _ka_post("/firecrawl/kaTaskSubmit", {
            "keyword": keyword,
            "platform": ka_platform,
            "language": language,
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
    """将 Ka 任务结果转换为 run_query 约定格式。
    
    成功判定规则（2026-08-28 更新）：
    - COMPLETED + 有文本: 完全成功
    - COMPLETED + 无文本 + 有截图: 部分成功（截图有效，文本提取失败）
    - RENDERING + 有文本: 成功（截图生成中，后续补全）
    - FAILED/其他: 失败
    """
    status = task.get("status", "")
    result_obj = task.get("result") or {}
    text = result_obj.get("text", "") or ""
    
    # 判断是否有有效内容
    has_text = len(text.strip()) > 0
    screenshot_url = task.get("screenshotUrl", "") or result_obj.get("remotePath", "") or ""
    has_screenshot = len(screenshot_url.strip()) > 0
    
    if status in SCREENSHOT_SUCCESS_STATUSES and has_text:
        # 有文本内容 → 成功（截图可能还在渲染）
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
        response_json = json.dumps({"localTaskId": task.get("localTaskId"), "platform": task.get("platform"), "keyword": task.get("keyword"), "result": result_obj, "screenshotStatus": "rendering" if status == "RENDERING" else "ready"}, ensure_ascii=False)[:5000]
        return {
            "success": True, "answer_text": text, "answer_html": answer_html,
            "response_json": response_json, "screenshot_url": screenshot_url,
            "duration": round(duration, 2), "error_message": "",
            "screenshot_status": "rendering" if status == "RENDERING" and not screenshot_url else "ready",
        }
    elif status == "COMPLETED" and not has_text and has_screenshot:
        # COMPLETED 无文本但有截图 → 部分成功（截图有效，文本提取失败）
        response_json = json.dumps({"localTaskId": task.get("localTaskId"), "platform": task.get("platform"), "keyword": task.get("keyword"), "result": result_obj, "screenshotStatus": "ready"}, ensure_ascii=False)[:5000]
        return {
            "success": True, "answer_text": "(截图内容，无文本)", "answer_html": "<p>该结果仅有截图，无文本内容。</p>",
            "response_json": response_json, "screenshot_url": screenshot_url,
            "duration": round(duration, 2), "error_message": "",
            "screenshot_status": "ready",
        }
    elif status == "COMPLETED" and not has_text:
        # COMPLETED 但无文本 → 也算失败
        err = task.get("errorMessage", "") or "结果无效(无文本内容)"
        return _fail_result(err[:500], duration)
    else:
        # 其他失败状态
        err = task.get("errorMessage", "") or f"任务状态: {status}"
        return _fail_result(err[:500], duration)


def _fail_result(error_message: str, duration: float) -> dict:
    return {"success": False, "answer_text": "", "answer_html": "", "response_json": "",
            "screenshot_url": "", "duration": round(duration, 2), "error_message": error_message}


def _escape_html(s: str) -> str:
    return s.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;").replace('"', "&quot;")

def _complete_screenshots(task_id: str, task_ids: list, submit_idx: dict, kw_map: dict, 
                          keywords: list, account_id: int, search_date: str):
    """异步补全截图：对 RENDERING 状态的任务持续轮询直到有截图或超时。
    
    Args:
        task_id: 搜索任务ID
        task_ids: 需要补全截图的 Ka 任务ID列表
        submit_idx: 提交信息映射 {localTaskId: {keyword, platform}}
        kw_map: 关键词映射
        keywords: 关键词列表
        account_id: 客户ID
        search_date: 搜索日期
    """
    logger.info("[Ka-Screenshot] 截图补全线程启动，%d 条任务，最大等待 %ds", len(task_ids), SCREENSHOT_MAX_WAIT)
    
    start_time = time.time()
    pending_ids = list(task_ids)  # 待补全的ID列表
    
    while pending_ids and (time.time() - start_time) < SCREENSHOT_MAX_WAIT:
        # 批量查询状态
        try:
            results = query_ka_detail(pending_ids)
        except Exception as e:
            logger.warning("[Ka-Screenshot] 轮询失败: %s, 10秒后重试...", e)
            time.sleep(SCREENSHOT_POLL_INTERVAL)
            continue
        
        newly_completed = []
        still_pending = []
        
        for r in results:
            tid = r.get("localTaskId")
            if not tid:
                continue
            
            status = r.get("status", "")
            screenshot_url = r.get("screenshotUrl", "") or ((r.get("result") or {}).get("remotePath", "") or "")
            
            if screenshot_url or status == "COMPLETED":
                # 截图已就绪 → 更新数据库
                info = submit_idx.get(tid, {})
                keyword = info.get("keyword", "")
                platform = info.get("platform", "")
                kw_entry = kw_map.get(keyword, keywords[0])
                
                try:
                    db.update_search_result_screenshot(
                        task_id=task_id,
                        platform=platform,
                        keyword=keyword,
                        screenshot_url=screenshot_url
                    )
                    logger.debug("[Ka-Screenshot] 截图已更新: %s (%s)", tid, platform)
                    newly_completed.append(tid)
                except Exception as e:
                    logger.error("[Ka-Screenshot] 更新截图失败: %s (task=%s)", e, tid)
                    # 即使更新失败也移除，避免无限重试
                    newly_completed.append(tid)
            elif status == "FAILED":
                # 任务失败 → 标记截图失败并移除
                logger.warning("[Ka-Screenshot] 任务失败，无法获取截图: %s", tid)
                newly_completed.append(tid)
            else:
                # 仍在渲染中
                still_pending.append(tid)
        
        pending_ids = still_pending
        
        if newly_completed:
            logger.info("[Ka-Screenshot] 本轮完成 %d 条，剩余 %d 条", len(newly_completed), len(pending_ids))
        
        if pending_ids:
            time.sleep(SCREENSHOT_POLL_INTERVAL)
    
    # 处理超时的任务
    if pending_ids:
        elapsed = int(time.time() - start_time)
        logger.warning("[Ka-Screenshot] %d 条任务截图超时(%ds)，标记为加载失败", len(pending_ids), elapsed)
        for tid in pending_ids:
            info = submit_idx.get(tid, {})
            keyword = info.get("keyword", "")
            platform = info.get("platform", "")
            try:
                db.update_search_result_screenshot(
                    task_id=task_id,
                    platform=platform,
                    keyword=keyword,
                    screenshot_url="TIMEOUT"  # 特殊标记：超时
                )
            except Exception as e:
                logger.error("[Ka-Screenshot] 标记超时失败: %s", e)
    
    logger.info("[Ka-Screenshot] 截图补全线程结束")


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

    # 关键修复：如果本日已存在旧平台结果，而当前搜索配置已缩小到新平台集合，
    # 需要先清理同一天被移除平台对应的历史记录，避免前端继续看到旧平台的数据。
    try:
        today = datetime.now().strftime("%Y-%m-%d")
        existing_platforms = db.get_today_platforms_for_account(account_id, today)
        stale_platforms = sorted(existing_platforms - set(platforms))
        if stale_platforms:
            logger.warning("[DEBUG-ADAPTER] 清理同日旧平台结果: account_id=%s stale=%s keep=%s", account_id, stale_platforms, platforms)
            db.delete_today_results_for_platforms(account_id, today, stale_platforms)
    except Exception as e:
        logger.warning("[DEBUG-ADAPTER] 清理旧平台结果失败，继续执行: %s", e)

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
    """后台执行：批量提交 + 并行轮询(实时落库) → COMPLETED。
    
    架构说明：
    - 主线程：负责批量提交任务到 Ka API
    - 轮询线程：在提交开始一段时间后，并行轮询已提交的任务结果
    - 两线程通过 threading.Lock 保证共享数据安全
    """
    search_date = datetime.now().strftime("%Y-%m-%d")
    saved_results = []  # 已保存的结果，避免重复（需加锁）
    all_processed = set()  # 所有已处理过的任务ID（无论是否最终完成），防止重复添加
    final_completed = []  # 已最终完成的任务（失败 或 成功且有截图）
    updated_screenshots = []  # 已更新截图的任务ID
    result_lock = threading.Lock()  # 保护 saved_results
    submitted_ids = []  # 已提交的 ID 列表（需加锁）
    id_lock = threading.Lock()  # 保护 submitted_ids
    submit_error = [None]  # 用于传递提交线程的异常
    poll_error = [None]  # 用于传递轮询线程的异常
    submit_complete = [False]  # 标记提交是否完成
    
    try:
        tasks_to_submit = []
        kw_map = {kw["prompt"]: kw for kw in keywords}
        for kw in keywords:
            for platform in platforms:
                tasks_to_submit.append({"keyword": kw["prompt"], "platform": platform, "language": "en"})
        
        # 构建提交索引：localTaskId → (keyword, platform)
        submit_idx = {}
        all_submitted = []
        completed_submit = 0
        
        # ═══════════════════════════════════════════
        # 轮询线程函数：在后台持续轮询已提交的任务
        # ═══════════════════════════════════════════
        def _poll_worker():
            """轮询线程：定期检查已提交任务的状态并保存结果"""
            try:
                logger.info("[Ka] 轮询线程已启动，等待 %ds 后开始首次轮询...", PARALLEL_POLL_START_DELAY)
                time.sleep(PARALLEL_POLL_START_DELAY)
                
                while True:
                    # 检查是否有可轮询的 ID
                    with id_lock:
                        current_ids = list(submitted_ids)
                    
                    if not current_ids:
                        # 没有已提交的 ID，检查是否提交已完成
                        if submit_complete[0]:
                            break
                        time.sleep(2)
                        continue
                    
                    # 更新心跳（轮询线程也负责保活）
                    db.touch_search_task_heartbeat(task_id)
                    
                    # 执行一轮轮询
                    try:
                        results = query_ka_detail(current_ids)
                    except Exception as e:
                        logger.warning("[Ka] 轮询查询失败: %s, 5秒后重试...", e)
                        time.sleep(5)
                        continue
                    
                    # 处理本轮结果
                    new_completed = 0
                    for r in results:
                        tid = r.get("localTaskId")
                        if not tid:
                            continue
                        status = r.get("status", "")
                        
                        # 成功判定：COMPLETED 或 RENDERING（有文本内容），或 COMPLETED 有截图但无文本
                        result_obj = r.get("result") or {}
                        text = result_obj.get("text", "") or ""
                        screenshot_url = r.get("screenshotUrl", "") or result_obj.get("remotePath", "") or ""
                        has_text = len(text.strip()) > 0
                        has_screenshot = len(screenshot_url.strip()) > 0
                        is_success = (status in SCREENSHOT_SUCCESS_STATUSES and has_text) or \
                                     (status == "COMPLETED" and not has_text and has_screenshot)
                        is_failed = status == "FAILED" or (status in ("COMPLETED",) and not has_text and not has_screenshot)
                        
                        if is_success or is_failed:
                            with result_lock:
                                # ✅ FIX: 检查是否已处理过（防止重复添加到 saved_results）
                                if tid in all_processed:
                                    # 已处理过，检查是否需要更新截图
                                    _is_final = is_failed or (is_success and screenshot_url)
                                    if _is_final and tid not in final_completed:
                                        # 之前没最终完成，现在最终完成了
                                        final_completed.append(tid)
                                    if is_success and screenshot_url and tid not in updated_screenshots:
                                        updated_screenshots.append(tid)
                                        # 更新数据库截图
                                        info = submit_idx.get(tid, {})
                                        _kw = info.get("keyword", "")
                                        _plat = info.get("platform", "")
                                        try:
                                            db.update_search_result_screenshot(task_id, _plat, _kw, screenshot_url)
                                            logger.debug("[Ka] 截图已更新: %s", tid)
                                        except Exception as e:
                                            logger.error("[Ka] 更新截图失败: %s", e)
                                    continue
                                
                                # 首次处理：标记为已处理
                                all_processed.add(tid)
                                saved_results.append(tid)
                                
                                # 检查是否已最终完成（失败 或 成功且有截图）
                                _is_final = is_failed or (is_success and screenshot_url)
                                if _is_final:
                                    final_completed.append(tid)
                            
                            # 保存单条结果到数据库
                            info = submit_idx.get(tid, {})
                            keyword = info.get("keyword", "")
                            platform = info.get("platform", "")
                            screenshot_url = (r.get("screenshotUrl", "") or result_obj.get("remotePath", "") or "")
                            error_msg = (r.get("errorMessage", "") or "")
                            
                            # 计算实际耗时（从提交到完成）
                            _submit_time = info.get("submit_time", 0)
                            _actual_duration = round(time.time() - _submit_time, 2) if _submit_time else 0
                            
                            kw_entry = kw_map.get(keyword, keywords[0])
                            
                            # 截图状态标记
                            screenshot_status = "rendering" if (status == "RENDERING" and not screenshot_url) else ("ready" if screenshot_url else "failed")
                            
                            db.save_search_result({
                                "task_id": task_id, "account_id": account_id, "keyword_id": kw_entry.get("id"),
                                "platform": platform, "model": PLATFORM_MODEL_MAP.get(platform, platform),
                                "keyword": keyword, "intent_category": kw_entry.get("category", ""),
                                "core_intent_word": kw_entry.get("core", ""), "intent_prompt": keyword,
                                "success": 1 if is_success else 0,
                                "response_json": json.dumps(r, ensure_ascii=False)[:5000],
                                "answer_text": text, "answer_html": "", "screenshot_url": screenshot_url,
                                "duration": _actual_duration, "attempt": 1, 
                                "error_message": error_msg[:500] if error_msg else "",
                                "rescue_round": "initial", "search_date": search_date,
                            })
                            new_completed += 1
                    
                    # 更新进度显示
                    with result_lock:
                        done_count = len(saved_results)
                    total_count = len(tasks_to_submit)
                    # ✅ FIX: 只用 done_count（实际完成数）作为进度
                    db.update_search_task_progress(task_id, done_count, f"查询中 {done_count}/{total_count}")
                    
                    # 检查是否应该退出轮询
                    # 修正：只有当提交已完成 AND 所有任务都有明确结果(COMPLETED/FAILED)时才退出
                    # 不能只看 saved_results，因为 QUEUED/RENDERING 的任务还没结果
                    if submit_complete[0]:
                        with id_lock:
                            current_ids = list(submitted_ids)
                        with result_lock:
                            # 只有当已保存的数量等于总提交数量时才退出
                            # 这确保了所有任务都已经得到最终结果
                            all_done = len(saved_results) >= len(current_ids) if current_ids else False
                        
                        if all_done:
                            logger.info("[Ka] 轮询线程: 所有任务已完成(%d/%d)，退出", len(saved_results), len(current_ids))
                            break
                        # 如果还有未完成的任务，继续轮询
                        elif current_ids:
                            pending_count = len(current_ids) - len(saved_results)
                            logger.debug("[Ka] 轮询线程: 还有 %d 个任务等待结果，继续...", pending_count)
                    
                    # 等待下一轮轮询（智能退避：根据待处理数量动态调整间隔）
                    if current_ids:
                        pending_count = len(current_ids) - len(saved_results)
                        # 待处理越多，轮询间隔越长（避免API压力）
                        if pending_count > 100:
                            _actual_interval = min(POLL_BACKOFF_MAX, POLL_INTERVAL + (pending_count // 20))
                        elif pending_count > 50:
                            _actual_interval = min(POLL_BACKOFF_MAX, POLL_INTERVAL + (pending_count // 30))
                        else:
                            _actual_interval = POLL_INTERVAL
                        if _actual_interval > POLL_INTERVAL:
                            logger.debug("[Ka] 智能退避: %d个待处理，间隔%ds", pending_count, _actual_interval)
                        time.sleep(_actual_interval)
                    else:
                        time.sleep(POLL_INTERVAL)
                    
            except Exception as e:
                import traceback as tb
                err_detail = ''.join(tb.format_exception(type(e), e, e.__traceback__))
                logger.exception("[Ka] 轮询线程异常: %s", str(e))
                poll_error[0] = e
                with open(f'/tmp/ka_poll_error_{task_id[:8]}.log', 'w') as f:
                    f.write(err_detail)
        
        # 启动轮询线程
        poll_thread = threading.Thread(target=_poll_worker, daemon=True)
        poll_thread.start()
        logger.info("[Ka] 轮询线程已创建，将在 %ds 后开始工作", PARALLEL_POLL_START_DELAY)
        
        # ═══════════════════════════════════════════
        # 主线程：批量提交任务（带限流和错误隔离）
        # ═══════════════════════════════════════════
        total_batches = (len(tasks_to_submit) + BATCH_SIZE - 1) // BATCH_SIZE
        is_large_task = len(tasks_to_submit) >= LARGE_TASK_THRESHOLD
        
        for i in range(0, len(tasks_to_submit), BATCH_SIZE):
            batch = tasks_to_submit[i:i + BATCH_SIZE]
            batch_num = i // BATCH_SIZE + 1
            
            try:
                results = submit_ka_tasks(batch)
                
                # 处理本批提交结果
                batch_ids = []
                _batch_submit_time = time.time()  # 记录本批提交时间用于计算耗时
                for j, r in enumerate(results):
                    local_id = r.get("localTaskId")
                    all_submitted.append({"localTaskId": local_id, "keyword": batch[j]["keyword"], "platform": batch[j]["platform"], "status": r.get("status", "FAILED"), "errorMessage": r.get("errorMessage", "")})
                    if local_id:
                        submit_idx[local_id] = {"keyword": batch[j]["keyword"], "platform": batch[j]["platform"], "submit_time": _batch_submit_time}
                        batch_ids.append(local_id)
                
                # 将新提交的 ID 加入共享列表（供轮询线程使用）
                with id_lock:
                    submitted_ids.extend(batch_ids)
                
                completed_submit += len(batch)
                # 提交阶段：显示已提交数量（不混淆为完成数量）
                db.update_search_task_progress(task_id, 0, f"已提交 {completed_submit}/{len(tasks_to_submit)}")
                
                logger.info("[Ka] 批次 %d/%d 提交成功: %d 条任务", batch_num, total_batches, len(batch_ids))
                
            except Exception as e:
                # 单批失败不影响其他批次，记录错误继续
                logger.error("[Ka] 批次 %d/%d 提交失败: %s (本批%d条任务将标记为失败)", 
                           batch_num, total_batches, str(e), len(batch))
                # 将本批所有任务标记为提交失败
                for item in batch:
                    all_submitted.append({"localTaskId": None, "keyword": item["keyword"], "platform": item["platform"], "status": "FAILED", "errorMessage": f"提交失败: {str(e)[:200]}"})
            
            # ✅ 更新心跳，防止前端显示"已超时"
            db.touch_search_task_heartbeat(task_id)
            
            # 批次间延迟：避免API限流（大规模任务更保守）
            if i + BATCH_SIZE < len(tasks_to_submit):
                delay = BATCH_SUBMIT_DELAY * (2 if is_large_task else 1)
                time.sleep(delay)
        
        # 标记提交完成
        submit_complete[0] = True
        logger.info("[Ka] 主线程: 所有任务已提交 (%d条)，等待轮询线程完成...", len(all_submitted))
        
        # 等待轮询线程完成（最多等待 POLL_MAX_WAIT 秒）
        poll_thread.join(timeout=POLL_MAX_WAIT)
        
        # 检查是否有异常
        if poll_error[0]:
            logger.warning("[Ka] 轮询线程异常: %s", poll_error[0])
        
        # ═══════════════════════════════════════════
        # 最终处理：检查遗漏的结果 + 截图补全
        # ═══════════════════════════════════════════
        valid_ids = [t["localTaskId"] for t in all_submitted if t["localTaskId"]]
        if valid_ids:
            # 做一次最终轮询，确保没有遗漏
            logger.info("[Ka] 执行最终轮询，检查 %d 条任务的最终状态...", len(valid_ids))
            try:
                final_results = query_ka_detail(valid_ids)
                for r in final_results:
                    tid = r.get("localTaskId")
                    if not tid:
                        continue
                    with result_lock:
                        if tid in saved_results:
                            continue
                        saved_results.append(tid)
                    
                    info = submit_idx.get(tid, {})
                    keyword = info.get("keyword", "")
                    platform = info.get("platform", "")
                    status = r.get("status", "FAILED")
                    result_obj = r.get("result") or {}
                    text = result_obj.get("text", "") or ""
                    screenshot_url = (r.get("screenshotUrl", "") or result_obj.get("remotePath", "") or "")
                    error_msg = (r.get("errorMessage", "") or "")
                    
                    # 计算实际耗时
                    _submit_time = info.get("submit_time", 0)
                    _actual_duration = round(time.time() - _submit_time, 2) if _submit_time else 0
                    
                    kw_entry = kw_map.get(keyword, keywords[0])
                    
                    # 成功判定：有文本内容即视为成功
                    is_success = status in SCREENSHOT_SUCCESS_STATUSES and len(text.strip()) > 0
                    
                    # 只保存非QUEUED/非RENDERING状态的结果（这些状态的需要继续等待）
                    if status not in ("QUEUED", "RENDERING"):
                        db.save_search_result({
                            "task_id": task_id, "account_id": account_id, "keyword_id": kw_entry.get("id"),
                            "platform": platform, "model": PLATFORM_MODEL_MAP.get(platform, platform),
                            "keyword": keyword, "intent_category": kw_entry.get("category", ""),
                            "core_intent_word": kw_entry.get("core", ""), "intent_prompt": keyword,
                            "success": 1 if is_success else 0,
                            "response_json": json.dumps(r, ensure_ascii=False)[:5000],
                            "answer_text": text, "answer_html": "", "screenshot_url": screenshot_url,
                            "duration": _actual_duration, "attempt": 1, 
                            "error_message": error_msg[:500] if error_msg else "",
                            "rescue_round": "initial", "search_date": search_date,
                        })
                
                # 检查是否还有QUEUED或RENDERING状态的任务，如果有则继续等待
                pending_ids = []
                for r in final_results:
                    tid = r.get("localTaskId")
                    if tid and r.get("status") in ("QUEUED", "RENDERING"):
                        pending_ids.append(tid)
                
                if pending_ids:
                    logger.warning("[Ka] 发现 %d 个任务仍处于 QUEUED/RENDERING 状态，继续等待...", len(pending_ids))
                for r in final_results:
                    tid = r.get("localTaskId")
                    if tid and r.get("status") in ("QUEUED", "RENDERING"):
                        pending_ids.append(tid)
                
                if pending_ids:
                    logger.warning("[Ka] 发现 %d 个任务仍处于 QUEUED/RENDERING 状态，继续等待...", len(pending_ids))
                    # 继续轮询QUEUED/RENDERING的任务（使用配置的超时时间）
                    _wait_start = time.time()
                    _max_pending_wait = FINAL_PENDING_MAX_WAIT  # 使用配置值
                    _pending_poll_interval = FINAL_PENDING_POLL_INTERVAL  # 使用配置值
                    while pending_ids and (time.time() - _wait_start) < _max_pending_wait:
                        time.sleep(_pending_poll_interval)
                        try:
                            _pending_results = query_ka_detail(pending_ids)
                            _still_pending = []
                            for qr in _pending_results:
                                _qtid = qr.get("localTaskId")
                                if not _qtid:
                                    continue
                                _qstatus = qr.get("status", "")
                                _qresult_obj = qr.get("result") or {}
                                _qtext = _qresult_obj.get("text", "") or ""
                                _qscreenshot_url = qr.get("screenshotUrl", "") or _qresult_obj.get("remotePath", "") or ""
                                _qerror_msg = (qr.get("errorMessage", "") or "")
                                
                                _qinfo = submit_idx.get(_qtid, {})
                                _qkeyword = _qinfo.get("keyword", "")
                                _qplatform = _qinfo.get("platform", "")
                                _qkw_entry = kw_map.get(_qkeyword, keywords[0])
                                _q_submit_time = _qinfo.get("submit_time", 0)
                                _q_actual_duration = round(time.time() - _q_submit_time, 2) if _q_submit_time else 0
                                
                                if _qstatus in ("QUEUED", "RENDERING"):
                                    _still_pending.append(_qtid)
                                else:
                                    # 任务已完成（成功或失败），保存结果
                                    _q_is_success = _qstatus in SCREENSHOT_SUCCESS_STATUSES and len(_qtext.strip()) > 0
                                    db.save_search_result({
                                        "task_id": task_id, "account_id": account_id, "keyword_id": _qkw_entry.get("id"),
                                        "platform": _qplatform, "model": PLATFORM_MODEL_MAP.get(_qplatform, _qplatform),
                                        "keyword": _qkeyword, "intent_category": _qkw_entry.get("category", ""),
                                        "core_intent_word": _qkw_entry.get("core", ""), "intent_prompt": _qkeyword,
                                        "success": 1 if _q_is_success else 0,
                                        "response_json": json.dumps(qr, ensure_ascii=False)[:5000],
                                        "answer_text": _qtext, "answer_html": "", "screenshot_url": _qscreenshot_url,
                                        "duration": _q_actual_duration, "attempt": 1, 
                                        "error_message": _qerror_msg[:500] if _qerror_msg else "",
                                        "rescue_round": "initial", "search_date": search_date,
                                    })
                                    logger.info("[Ka] 待处理任务完成: %s -> %s", _qtid, _qstatus)
                            
                            pending_ids = _still_pending
                            if pending_ids:
                                logger.info("[Ka] 仍有 %d 个任务在等待，已等待 %.0fs/%ds...", 
                                           len(pending_ids), time.time() - _wait_start, _max_pending_wait)
                        except Exception as e:
                            logger.error("[Ka] 待处理轮询失败: %s", e)
                            break
                    
                    # 对于仍然QUEUED/RENDERING的任务，标记为超时失败
                    if pending_ids:
                        logger.warning("[Ka] %d 个任务等待超时，标记为失败", len(pending_ids))
                        for _qtid in pending_ids:
                            _qinfo = submit_idx.get(_qtid, {})
                            _qkeyword = _qinfo.get("keyword", "")
                            _qplatform = _qinfo.get("platform", "")
                            _qkw_entry = kw_map.get(_qkeyword, keywords[0])
                            db.save_search_result({
                                "task_id": task_id, "account_id": account_id, "keyword_id": _qkw_entry.get("id"),
                                "platform": _qplatform, "model": PLATFORM_MODEL_MAP.get(_qplatform, _qplatform),
                                "keyword": _qkeyword, "intent_category": _qkw_entry.get("category", ""),
                                "core_intent_word": _qkw_entry.get("core", ""), "intent_prompt": _qkeyword,
                                "success": 0, 
                                "response_json": json.dumps({"localTaskId": _qtid, "status": "TIMEOUT"}, ensure_ascii=False),
                                "answer_text": "", "answer_html": "", "screenshot_url": "",
                                "duration": 0, "attempt": 1, 
                                "error_message": "任务等待超时（QUEUED/RENDERING状态）",
                                "rescue_round": "initial", "search_date": search_date,
                            })
                
                # 启动截图补全线程（异步补全所有缺少截图的成功记录）
                rendering_tasks = []
                for r in final_results:
                    tid = r.get("localTaskId")
                    if not tid:
                        continue
                    status = r.get("status", "")
                    screenshot_url = r.get("screenshotUrl", "") or (r.get("result") or {}).get("remotePath", "") or ""
                    # 需要补全的条件：RENDERING状态 或 COMPLETED但无截图
                    if status == "RENDERING" and not screenshot_url:
                        rendering_tasks.append(tid)
                    elif status == "COMPLETED" and not screenshot_url:
                        # COMPLETED 但没有截图的任务也需要补全
                        rendering_tasks.append(tid)
                
                if rendering_tasks:
                    logger.info("[Ka] 启动截图补全线程，%d 条任务需要补全截图...", len(rendering_tasks))
                    screenshot_thread = threading.Thread(
                        target=_complete_screenshots,
                        args=(task_id, rendering_tasks, submit_idx, kw_map, keywords, account_id, search_date),
                        daemon=True
                    )
                    screenshot_thread.start()
                        
            except Exception as e:
                logger.error("[Ka] 最终轮询失败: %s", e)
        else:
            # 没有有效ID的任务直接标记失败
            for entry in all_submitted:
                kw_entry = kw_map.get(entry["keyword"], keywords[0])
                db.save_search_result({
                    "task_id": task_id, "account_id": account_id, "keyword_id": kw_entry.get("id"),
                    "platform": entry["platform"], "model": PLATFORM_MODEL_MAP.get(entry["platform"], entry["platform"]),
                    "keyword": entry["keyword"], "intent_category": kw_entry.get("category", ""),
                    "core_intent_word": kw_entry.get("core", ""), "intent_prompt": entry["keyword"],
                    "success": 0, "response_json": "", "answer_text": "", "answer_html": "",
                    "screenshot_url": "", "duration": 0, "attempt": 1,
                    "error_message": (entry.get("errorMessage") or "提交失败")[:500],
                    "rescue_round": "initial", "search_date": search_date,
                })
        
        db.update_search_task_status(task_id, "COMPLETED")
        with result_lock:
            saved_count = len(saved_results)
        logger.info("[Ka] 任务 %s 完成: %d/%d 条已保存", task_id, saved_count, len(all_submitted))
        
    except Exception as e:
        import traceback as tb
        err_detail = ''.join(tb.format_exception(type(e), e, e.__traceback__))
        logger.exception("[Ka] search task worker crashed: %s", str(e))
        try:
            db.update_search_task_status(task_id, "ERROR", f"查词执行异常: {str(e)[:500]}")
            # 同时写入详细错误到文件
            with open(f'/tmp/ka_error_{task_id[:8]}.log', 'w') as f:
                f.write(err_detail)
        except Exception:
            pass