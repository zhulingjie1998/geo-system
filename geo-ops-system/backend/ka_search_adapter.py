"""Ka 查词任务适配器：对接内部 CloroTaskRecordKa 接口。

接口文档：
  - 单个提交: POST /api/app/tcloud-geo/firecrawl/kaTaskSubmit
  - 批量提交: POST /api/app/tcloud-geo/firecrawl/kaTaskBatchSubmit
  - 结果查询: POST /api/app/tcloud-geo/firecrawl/kaTaskDetail

平台枚举: perplexity / chatGpt / google / gemini / bingCopilot / googleAIM

任务状态: CREATED → QUEUED → PROCESSING → RENDERING → COMPLETED / FAILED
"""

from __future__ import annotations

import logging
import time
from typing import Any

import requests

logger = logging.getLogger(__name__)

# 内部接口基础 URL
KA_BASE_URL = "https://api.71360.com/api/app/tcloud-geo"

# 平台映射（前端显示名 → 接口枚举值）
PLATFORM_MAP = {
    "chatgpt": "chatGpt",
    "google_aio": "google",
    "google_aim": "googleAIM",
    "gemini": "gemini",
    "perplexity": "perplexity",
    "copilot": "bingCopilot",
}

# 反向映射（接口值 → 显示名）
REVERSE_PLATFORM_MAP = {v: k for k, v in PLATFORM_MAP.items()}

# 任务状态映射
STATUS_MAP = {
    "CREATED": "已创建",
    "QUEUED": "排队中",
    "PROCESSING": "处理中",
    "RENDERING": "渲染中",
    "COMPLETED": "已完成",
    "FAILED": "失败",
}

OUTER_STATUS_MAP = {
    0: "处理中",
    1: "成功",
    2: "失败",
}


def _request(method: str, path: str, json_data: dict | None = None, timeout: int = 30) -> dict:
    """发送请求到内部 Ka 接口。"""
    url = f"{KA_BASE_URL}{path}"
    try:
        resp = requests.request(method, url, json=json_data, timeout=timeout)
        resp.raise_for_status()
        data = resp.json()
        if data.get("code") != 200 and data.get("code") != 0:
            logger.error(f"[Ka] 接口返回错误: {data}")
            return {"error": data.get("message", "未知错误"), "raw": data}
        return data
    except requests.exceptions.Timeout:
        logger.error(f"[Ka] 请求超时: {method} {url}")
        return {"error": f"请求超时({timeout}s)"}
    except requests.exceptions.ConnectionError as e:
        logger.error(f"[Ka] 连接失败: {e}")
        return {"error": f"连接失败: {e}"}
    except Exception as e:
        logger.exception(f"[Ka] 请求异常: {method} {url}")
        return {"error": str(e)}


def submit_task(keyword: str, platform: str, language: str = "en") -> dict:
    """提交单个查词任务。

    Args:
        keyword: 查询关键词
        platform: 平台（使用前端 key，如 chatgpt/google_aio/gemini 等）
        language: 语言，默认 en

    Returns:
        { localTaskId, keyword, platform, status, errorMessage }
    """
    api_platform = PLATFORM_MAP.get(platform, platform)
    payload = {
        "keyword": keyword,
        "language": language,
        "platform": api_platform,
    }
    result = _request("POST", "/firecrawl/kaTaskSubmit", payload)
    data = result.get("data", {})
    # 统一返回格式
    return {
        "localTaskId": data.get("localTaskId"),
        "keyword": keyword,
        "platform": platform,
        "apiPlatform": api_platform,
        "status": data.get("status"),
        "errorMessage": data.get("errorMessage"),
        "error": result.get("error"),
    }


def submit_batch(tasks: list[dict]) -> list[dict]:
    """批量提交查词任务。

    Args:
        tasks: [{ keyword, platform, language? }, ...]
              platform 使用前端 key

    Returns:
        [{ localTaskId, keyword, platform, status, errorMessage }, ...]
    """
    api_tasks = []
    for t in tasks:
        api_tasks.append({
            "keyword": t["keyword"],
            "language": t.get("language", "en"),
            "platform": PLATFORM_MAP.get(t["platform"], t["platform"]),
        })
    result = _request("POST", "/firecrawl/kaTaskBatchSubmit", {"tasks": api_tasks})
    items = result.get("data", [])
    # 合并原始请求信息
    output = []
    for i, item in enumerate(items):
        orig = tasks[i] if i < len(tasks) else {}
        output.append({
            "localTaskId": item.get("localTaskId"),
            "keyword": item.get("keyword", orig.get("keyword")),
            "platform": orig.get("platform"),
            "apiPlatform": item.get("platform"),
            "status": item.get("status"),
            "errorMessage": item.get("errorMessage"),
            "error": result.get("error"),
        })
    return output


def query_detail(local_task_ids: list[int]) -> list[dict]:
    """查询任务详情（批量）。

    Args:
        local_task_ids: 提交时返回的 localTaskId 列表

    Returns:
        [task_detail, ...]  见接口文档
    """
    if not local_task_ids:
        return []
    result = _request("POST", "/firecrawl/kaTaskDetail", {"localTaskIds": local_task_ids})
    items = result.get("data", [])
    # 标准化返回格式
    output = []
    for item in items:
        r = item.get("result") or {}
        output.append({
            "localTaskId": item.get("localTaskId"),
            "cloroTaskId": item.get("cloroTaskId"),
            "keyword": item.get("keyword"),
            "language": item.get("language"),
            "platform": REVERSE_PLATFORM_MAP.get(item.get("platform"), item.get("platform")),
            "apiPlatform": item.get("platform"),
            "priority": item.get("priority"),
            "status": item.get("status"),
            "statusDesc": STATUS_MAP.get(item.get("status"), item.get("status")),
            "outerStatus": item.get("outerStatus"),
            "screenshotUrl": item.get("screenshotUrl"),
            "errorMessage": item.get("errorMessage"),
            "createdAt": item.get("createdAt"),
            "submittedAt": item.get("submittedAt"),
            "callbackAt": item.get("callbackAt"),
            "completedAt": item.get("completedAt"),
            # 结果内容
            "text": r.get("text"),
            "summarys": r.get("summarys", []),
            "remotePath": r.get("remotePath"),
            "hasContent": r.get("hasContent"),
        })
    return output


def poll_until_complete(local_task_ids: list[int],
                        interval: float = 5.0,
                        max_wait: float = 300.0,
                        on_progress=None) -> dict[str, list[dict]]:
    """轮询等待任务完成。

    Args:
        local_task_ids: 任务 ID 列表
        interval: 轮询间隔（秒）
        max_wait: 最大等待时间（秒）
        on_progress: 回调函数(completed, total, results)

    Returns:
        { completed: [...], failed: [...], pending: [...] }
    """
    start = time.time()
    all_results = {}

    while time.time() - start < max_wait:
        results = query_detail(local_task_ids)
        all_results = {r["localTaskId"]: r for r in results}

        completed = [r for r in results if r["status"] in ("COMPLETED", "FAILED")]
        pending = [r for r in results if r["status"] not in ("COMPLETED", "FAILED")]

        if on_progress:
            on_progress(len(completed), len(results), results)

        # 全部完成或失败
        if not pending:
            break

        time.sleep(interval)

    results = list(all_results.values())
    return {
        "completed": [r for r in results if r["status"] == "COMPLETED"],
        "failed": [r for r in results if r["status"] == "FAILED"],
        "pending": [r for r in results if r["status"] not in ("COMPLETED", "FAILED")],
        "all": results,
    }
