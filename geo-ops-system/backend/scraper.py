"""scraper.py - Firecrawl 网页抓取模块（引用源分析）。

通过 Firecrawl API 抓取引用源 URL 的页面内容（Markdown），
并可选调用 LLM 提取 pub_date / content_type / website_type。
"""

from __future__ import annotations

import json
import logging
import queue as _queue
import re
import threading
import time
from typing import Callable, Generator

import httpx

import db

logger = logging.getLogger("gunicorn.error")


class RateLimiter:
    """简单全局限速器：控制请求发起速率（RPS）。"""

    def __init__(self, rps: float) -> None:
        self.interval = 1.0 / rps if rps and rps > 0 else 0.0
        self._lock = threading.Lock()
        self._next_ts = 0.0

    def acquire(self) -> None:
        if self.interval <= 0:
            return
        sleep_for = 0.0
        with self._lock:
            now = time.monotonic()
            if now < self._next_ts:
                sleep_for = self._next_ts - now
                self._next_ts += self.interval
            else:
                self._next_ts = now + self.interval
        if sleep_for > 0:
            time.sleep(sleep_for)


def firecrawl_scrape(url: str, api_key: str, api_url: str, timeout: int = 60) -> dict:
    """调用 Firecrawl API 抓取单个 URL，返回原始 API 响应。"""
    endpoint = f"{api_url.rstrip('/')}/v2/scrape"
    headers = {
        "Authorization": f"Bearer {api_key}",
        "Content-Type": "application/json",
    }
    payload = {"url": url, "formats": ["markdown"]}

    with httpx.Client(timeout=timeout, trust_env=False) as client:
        resp = client.post(endpoint, json=payload, headers=headers)
        resp.raise_for_status()
        return resp.json()


def _scrape_one(
    url: str,
    title: str,
    site_name: str,
    account_id: int,
    search_date: str,
    api_key: str,
    api_url: str,
    timeout: int,
    retries: int,
    limiter,
    settings: dict | None = None,
) -> dict:
    """抓取单个 URL 并写入数据库。若 settings 提供且抓取成功，则立即提取元数据。"""
    last_error = ""
    for attempt in range(retries + 1):
        try:
            if limiter:
                limiter.acquire()
            result = firecrawl_scrape(url, api_key, api_url, timeout)
            if not result.get("success", False):
                raise RuntimeError("API 返回 success=false")
            markdown = (result.get("data") or {}).get("markdown") or ""
            page_title = (result.get("data") or {}).get("metadata", {}).get("title", "")

            scrape_id = db.save_scrape_result({
                "account_id": account_id,
                "search_date": search_date,
                "url": url,
                "title": page_title or title,
                "site_name": site_name,
                "markdown_content": markdown,
                "scrape_status": "done",
            })

            # 立即提取元数据（内容分析合并进抓取）
            meta = {"pub_date": "", "content_type": "", "website_type": ""}
            if settings and markdown:
                try:
                    meta = extract_content_meta(markdown, settings)
                    db.update_scrape_result(scrape_id, {
                        "markdown_content": markdown,
                        "pub_date": meta.get("pub_date", ""),
                        "content_type": meta.get("content_type", ""),
                        "website_type": meta.get("website_type", ""),
                        "scrape_status": "done",
                    })
                except Exception as exc:
                    logger.warning("[scraper] inline extract failed for %s: %s", url, exc)

            return {
                "url": url, "ok": True, "scrape_id": scrape_id,
                "content_length": len(markdown),
                "title": page_title or title,
                "meta": meta,
            }
        except Exception as exc:
            last_error = str(exc)
            if attempt < retries:
                time.sleep(2 ** attempt)

    scrape_id = db.save_scrape_result({
        "account_id": account_id,
        "search_date": search_date,
        "url": url,
        "title": title,
        "site_name": site_name,
        "markdown_content": "",
        "scrape_status": "failed",
        "error_message": last_error,
    })
    return {"url": url, "ok": False, "scrape_id": scrape_id, "error": last_error}




def run_scrape_stream(
    urls: list[dict],
    account_id: int,
    search_date: str,
    cancel_check: Callable[[], bool] | None = None,
) -> Generator[dict, None, None]:
    """批量抓取引用源 URL，生成 SSE 进度事件。

    urls: [{"url": "...", "title": "...", "siteName": "..."}]
    事件类型: start / progress / heartbeat / finish / cancelled / error
    """
    settings = db.get_all_settings()
    api_key = settings.get("firecrawl_api_key", "")
    api_url = settings.get("firecrawl_api_url", "https://api.firecrawl.dev")
    concurrency = int(settings.get("firecrawl_concurrency", "5"))
    timeout = 60

    if not api_key:
        yield {"type": "error", "msg": "Firecrawl API Key 未配置，请在系统设置中填写"}
        return

    total = len(urls)
    if not total:
        yield {"type": "finish", "success": 0, "failed": 0, "total": 0}
        return

    # 先清除旧的抓取记录
    db.delete_scrape_results(account_id, search_date)

    yield {"type": "start", "total": total}

    limiter = RateLimiter(concurrency)
    result_q: _queue.Queue = _queue.Queue()
    done = 0
    success = 0
    failed = 0

    import concurrent.futures
    executor = concurrent.futures.ThreadPoolExecutor(max_workers=concurrency)

    try:
        for item in urls:
            executor.submit(
                lambda u=item: result_q.put(
                    _scrape_one(
                        url=u["url"],
                        title=u.get("title", ""),
                        site_name=u.get("siteName", ""),
                        account_id=account_id,
                        search_date=search_date,
                        api_key=api_key,
                        api_url=api_url,
                        timeout=timeout,
                        retries=2,
                        limiter=limiter,
                        settings=settings,
                    )
                )
            )

        last_ping = time.monotonic()
        while done < total:
            if cancel_check and cancel_check():
                executor.shutdown(wait=False, cancel_futures=True)
                yield {"type": "cancelled", "done": done, "total": total,
                       "success": success, "failed": failed}
                return
            try:
                r = result_q.get(timeout=0.5)
            except _queue.Empty:
                if time.monotonic() - last_ping >= 5:
                    last_ping = time.monotonic()
                    yield {"type": "heartbeat", "done": done, "total": total,
                           "success": success, "failed": failed}
                continue
            done += 1
            if r["ok"]:
                success += 1
            else:
                failed += 1
            yield {
                "type": "progress",
                "done": done,
                "total": total,
                "url": r["url"],
                "status": "done" if r["ok"] else "failed",
                "error": r.get("error", ""),
                "contentLength": r.get("content_length", 0),
                "success": success,
                "failed": failed,
            }
    except Exception as exc:
        yield {"type": "error", "msg": str(exc)}
    finally:
        executor.shutdown(wait=False, cancel_futures=True)

    yield {"type": "finish", "success": success, "failed": failed, "total": total}


# ── 内容元数据提取（从已抓取的 Markdown 中用 LLM 提取） ──────────────────

EXTRACT_PROMPT = """请分析以下网页内容，提取三个信息字段：

1. **pub_date**（发布日期）：提取页面中出现的发布时间、更新时间或创建时间。
   - 格式统一为 `YYYY-MM-DD HH:mm:ss`
   - 若只有日期无时间，时间部分填 `00:00:00`
   - 若无法判断，返回空字符串

2. **content_type**（内容类型），从以下选项中选择一个：
   - 品牌/产品介绍
   - 榜单推荐/评测对比
   - 教程指南
   - 问答/社区讨论
   - 知识科普
   - 新闻资讯

3. **website_type**（网站类型），从以下选项中选择一个：
   - 企业官网
   - B2B商铺
   - 自媒体平台
   - 百科平台
   - 企业信息平台
   - 社区论坛

若无法判断某字段，返回空字符串。

仅输出 JSON，禁止任何解释性文字：
{{"pub_date": "", "content_type": "", "website_type": ""}}

---

网页内容：
{content}
"""


def extract_content_meta(markdown: str, settings: dict) -> dict:
    """从 Markdown 内容中用 LLM 提取 pub_date / content_type / website_type。"""
    if not markdown or not markdown.strip():
        return {"pub_date": "", "content_type": "", "website_type": ""}

    mode = settings.get("llm_api_mode", "qwen")  # 默认使用通义千问
    # 各模式独立 base_url:qwen 必须走 dashscope(qwen_base_url),不能用网关 llm_base_url(否则 dashscope key 发给网关→401)。
    # 与 brand_analyzer._call_llm 保持一致(此前漏了这步,是 qwen 抽取 401 的根因)。
    base_url = (settings.get(f"{mode}_base_url") or settings.get("llm_base_url", "")).rstrip("/")
    api_key = settings.get(f"{mode}_api_key") or settings.get("llm_api_key", "")
    model = settings.get(f"{mode}_model_name") or settings.get("llm_model_name", "qwen-plus")  # 默认通义千问
    timeout = int(settings.get("llm_timeout", "300"))

    if not api_key:
        return {"pub_date": "", "content_type": "", "website_type": ""}

    # 截断过长内容（取前 10000 字符）
    truncated = markdown[:10000] if len(markdown) > 10000 else markdown
    user_content = EXTRACT_PROMPT.format(content=truncated)

    try:
        with httpx.Client(timeout=timeout, trust_env=False) as client:
            if mode == "claude":
                # Claude Messages API
                claude_base = base_url.rstrip("/")
                if claude_base.endswith("/v1/messages"):
                    claude_base = claude_base[:-len("/v1/messages")]
                elif claude_base.endswith("/messages"):
                    claude_base = claude_base[:-len("/messages")]
                url = f"{claude_base}/v1/messages"
                payload = {
                    "model": model,
                    "max_tokens": 2000,
                    "messages": [{"role": "user", "content": user_content}],
                }
                resp = client.post(url, json=payload, headers={
                    "x-api-key": api_key,
                    "anthropic-version": "2023-06-01",
                    "content-type": "application/json",
                })
            elif mode == "gemini":
                url = f"{base_url}/v1beta/models/{model}:generateContent?key={api_key}"
                payload = {
                    "contents": [{"role": "user", "parts": [{"text": user_content}]}],
                    "generationConfig": {"temperature": 0.1, "maxOutputTokens": 2000},
                }
                resp = client.post(url, json=payload)
            else:
                url = f"{base_url}/v1/chat/completions"
                payload = {
                    "model": model,
                    "messages": [{"role": "user", "content": user_content}],
                    "temperature": 0.1,
                    "max_tokens": 2000,
                }
                resp = client.post(url, json=payload, headers={"Authorization": f"Bearer {api_key}"})

            resp.raise_for_status()
            data = resp.json()

            if mode == "claude":
                raw = ""
                for block in data.get("content", []):
                    if block.get("type") == "text":
                        raw += block.get("text", "")
            elif mode == "gemini":
                raw = data.get("candidates", [{}])[0].get("content", {}).get("parts", [{}])[0].get("text", "")
            else:
                raw = data.get("choices", [{}])[0].get("message", {}).get("content", "")

            match = re.search(r'\{[\s\S]*\}', raw)
            if match:
                parsed = json.loads(match.group())
                return {
                    "pub_date": parsed.get("pub_date", "") or "",
                    "content_type": parsed.get("content_type", "") or "",
                    "website_type": parsed.get("website_type", "") or "",
                }
    except Exception as exc:
        logger.warning("[scraper] extract_content_meta failed: %s", exc)

    return {"pub_date": "", "content_type": "", "website_type": ""}


def extract_all_scrape_meta(account_id: int, search_date: str) -> int:
    """对已抓取的内容批量提取元数据，返回处理数量。"""
    settings = db.get_all_settings()
    scrapes = db.get_scrape_results(account_id, search_date)
    count = 0
    for s in scrapes:
        if s.get("scrapeStatus") != "done":
            continue
        markdown = s.get("markdownContent", "")
        if not markdown:
            continue
        meta = extract_content_meta(markdown, settings)
        db.update_scrape_result(s["id"], {
            "markdown_content": markdown,
            "pub_date": meta["pub_date"],
            "content_type": meta["content_type"],
            "website_type": meta["website_type"],
            "scrape_status": "done",
        })
        count += 1
    return count




def extract_all_scrape_meta_concurrent(account_id: int, search_date: str, concurrency: int = 10) -> int:
    """并发版本：对已抓取的内容批量提取元数据，返回处理数量。
    
    Args:
        account_id: 账户ID
        search_date: 查词日期
        concurrency: 并发数，默认10
    """
    import concurrent.futures
    import queue as _queue
    
    settings = db.get_all_settings()
    scrapes = db.get_scrape_results(account_id, search_date)
    
    # 过滤需要处理的记录
    to_process = [
        s for s in scrapes 
        if s.get("scrapeStatus") == "done" and s.get("markdownContent", "").strip()
    ]
    
    if not to_process:
        logger.info("[scraper] No records to process for account=%s date=%s", account_id, search_date)
        return 0
    
    total = len(to_process)
    logger.info("[scraper] Starting concurrent extraction: %d records, concurrency=%d", total, concurrency)
    
    result_q = _queue.Queue()
    success_count = 0
    error_count = 0
    
    def _process_one(scrape_item):
        """处理单条记录"""
        try:
            markdown = scrape_item.get("markdownContent", "")
            meta = extract_content_meta(markdown, settings)
            db.update_scrape_result(scrape_item["id"], {
                "markdown_content": markdown,
                "pub_date": meta["pub_date"],
                "content_type": meta["content_type"],
                "website_type": meta["website_type"],
                "scrape_status": "done",
            })
            return {"ok": True, "id": scrape_item["id"]}
        except Exception as e:
            logger.warning("[scraper] Failed to process scrape_id=%s: %s", scrape_item.get("id"), e)
            return {"ok": False, "id": scrape_item.get("id"), "error": str(e)}
    
    with concurrent.futures.ThreadPoolExecutor(max_workers=concurrency) as executor:
        # 提交所有任务
        futures = [executor.submit(_process_one, item) for item in to_process]
        
        # 等待完成
        for future in concurrent.futures.as_completed(futures):
            try:
                result = future.result()
                if result["ok"]:
                    success_count += 1
                else:
                    error_count += 1
                
                # 每处理10条打印一次进度
                if (success_count + error_count) % 10 == 0:
                    logger.info("[scraper] Progress: %d/%d processed (%d success, %d errors)", 
                              success_count + error_count, total, success_count, error_count)
            except Exception as e:
                error_count += 1
                logger.warning("[scraper] Future failed: %s", e)
    
    logger.info("[scraper] Extraction complete: %d/%d success, %d errors", 
               success_count, total, error_count)
    return success_count


# ═══════════════════════════════════════════
# 后台持久化抓取（不依赖 SSE 连接）
# ═══════════════════════════════════════════

def run_scrape_background(task_id, urls, account_id, search_date):
    """在后台线程中抓取，进度写入数据库。前端可随时轮询/重连。"""
    settings = db.get_all_settings()
    api_key = settings.get("firecrawl_api_key", "")
    api_url = settings.get("firecrawl_api_url", "https://api.firecrawl.dev")
    concurrency = int(settings.get("firecrawl_concurrency", "5"))
    timeout_sec = 60

    if not api_key:
        db.finish_citation_scrape_task(task_id, "error", error_msg="Firecrawl API Key 未配置")
        return

    total = len(urls)
    if not total:
        db.finish_citation_scrape_task(task_id, "completed", 0, 0)
        return

    # 清除旧抓取记录
    db.delete_scrape_results(account_id, search_date)

    limiter = RateLimiter(concurrency)
    result_q = _queue.Queue()
    done = 0
    ok_count = 0
    fail_count = 0

    import concurrent.futures
    executor = concurrent.futures.ThreadPoolExecutor(max_workers=concurrency)

    try:
        for item in urls:
            executor.submit(
                lambda u=item: result_q.put(
                    _scrape_one(
                        url=u["url"],
                        title=u.get("title", ""),
                        site_name=u.get("siteName", ""),
                        account_id=account_id,
                        search_date=search_date,
                        api_key=api_key,
                        api_url=api_url,
                        timeout=timeout_sec,
                        retries=2,
                        limiter=limiter,
                        settings=settings,
                    )
                )
            )

        hb_counter = 0
        while done < total:
            # 检查取消
            if db.is_cancel_requested(task_id):
                executor.shutdown(wait=False, cancel_futures=True)
                db.finish_citation_scrape_task(task_id, "cancelled", ok_count, fail_count)
                db.clear_cancel(task_id)
                return

            try:
                r = result_q.get(timeout=0.5)
            except _queue.Empty:
                # 每 5 次空循环更新一次心跳
                hb_counter += 1
                if hb_counter % 10 == 0:
                    db.update_citation_scrape_progress(task_id, done, ok_count, fail_count, "")
                continue

            done += 1
            is_ok = r["ok"]
            if is_ok:
                ok_count += 1
            else:
                fail_count += 1

            domain = ""
            try:
                from urllib.parse import urlparse
                domain = urlparse(r["url"]).hostname or ""
                if domain.startswith("www."):
                    domain = domain[4:]
            except Exception:
                domain = r["url"][:30]

            # 写入事件
            dur = r.get("duration", 0) or 0
            db.add_citation_scrape_event(
                task_id, r["url"], r.get("title", ""), domain,
                is_ok, dur, r.get("error", ""))

            # 更新进度
            db.update_citation_scrape_progress(task_id, done, ok_count, fail_count, domain)

    except Exception as exc:
        db.finish_citation_scrape_task(task_id, "error", ok_count, fail_count, str(exc))
        return
    finally:
        executor.shutdown(wait=False, cancel_futures=True)

    db.finish_citation_scrape_task(task_id, "completed", ok_count, fail_count)
