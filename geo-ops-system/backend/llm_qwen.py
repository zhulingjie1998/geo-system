"""llm_qwen.py — 通义千问 (Qwen) / OpenAI 兼容 LLM 客户端

支持阿里云通义千问、以及任何 OpenAI 兼容接口。
用于知识库 AI 生成场景。

配置方式：通过「系统设置 → 品牌分析 → 通义千问」页面配置，或环境变量
  qwen_base_url    (必填，如 https://dashscope.aliyuncs.com/compatible-mode/v1)
  qwen_api_key     (必填)
  qwen_model_name  (默认: qwen-plus)
  qwen_timeout     (默认: 300)

环境变量（开发调试用）：
  QWEN_BASE_URL, QWEN_API_KEY
"""

from __future__ import annotations

import json
import logging
import os
import time
from typing import Optional, Generator, Iterator

import httpx

logger = logging.getLogger("llm_qwen")

# ── 默认配置（无硬编码，必须通过系统设置或环境变量配置） ──────
_DEFAULT_BASE_URL = ""
_DEFAULT_MODEL = "qwen-plus"
_DEFAULT_API_KEY = ""

# ── 重试策略 ──────────────────────────────────────────────────────────
_MAX_ATTEMPTS = 3
_RETRY_BACKOFF = [2, 5, 10]


def _is_retryable(status: Optional[int]) -> bool:
    if status is None:
        return True
    if status in (401, 403):
        return False
    return True


def _post_chat(url: str, headers: dict, payload: dict,
               timeout: int, label: str) -> dict:
    """POST /v1/chat/completions，瞬时失败最多重试 _MAX_ATTEMPTS 次。"""
    last_status: Optional[int] = None
    last_body = ""
    for attempt in range(1, _MAX_ATTEMPTS + 1):
        try:
            with httpx.Client(timeout=timeout, trust_env=False) as client:
                resp = client.post(url, headers=headers, json=payload)
            if resp.status_code < 300:
                if attempt > 1:
                    logger.info("[%s] 第 %d 次尝试成功", label, attempt)
                return resp.json()
            last_status = resp.status_code
            last_body = (resp.text or "")[:600]
            if not _is_retryable(last_status):
                raise RuntimeError(
                    f"{label} 请求被拒(HTTP {last_status})：{last_body[:400]}"
                )
            logger.warning("[%s] 第 %d/%d 次 HTTP %s，将重试",
                           label, attempt, _MAX_ATTEMPTS, last_status)
        except RuntimeError:
            raise
        except Exception as e:
            last_status = None
            last_body = repr(e)
            logger.warning("[%s] 第 %d/%d 次异常：%s",
                           label, attempt, _MAX_ATTEMPTS, last_body[:200])
        if attempt < _MAX_ATTEMPTS:
            time.sleep(_RETRY_BACKOFF[min(attempt - 1, len(_RETRY_BACKOFF) - 1)])
    raise RuntimeError(
        f"{label} 连续 {_MAX_ATTEMPTS} 次失败"
        + (f"（最后 HTTP {last_status}）" if last_status else "（网络异常）")
        + f"：{last_body[:400]}"
    )


def call_qwen(
    settings: dict,
    *,
    user_prompt: str,
    system_prompt: Optional[str] = None,
    max_tokens: int = 8192,
    timeout: Optional[int] = None,
    model: Optional[str] = None,
    temperature: float = 0.7,
) -> str:
    """发送单轮对话请求到 Qwen/OpenAI 兼容接口，返回文本内容。

    Args:
        settings: 包含 qwen_* 配置的字典（从 DB system_setting 加载）
        user_prompt: 用户消息
        system_prompt: 系统提示词（可选）
        max_tokens: 最大输出 token 数
        timeout: 超时秒数
        model: 模型名称（覆盖默认值）
        temperature: 温度参数

    Returns:
        模型返回的文本内容

    Raises:
        RuntimeError: API key 缺失或响应格式错误
    """
    base_url = (settings.get("qwen_base_url") or "").rstrip("/")
    api_key = settings.get("qwen_api_key") or ""
    # 支持环境变量覆盖（开发调试用）
    if not base_url:
        base_url = os.environ.get("QWEN_BASE_URL", _DEFAULT_BASE_URL).rstrip("/")
    if not api_key:
        api_key = os.environ.get("QWEN_API_KEY", _DEFAULT_API_KEY)

    model = model or settings.get("qwen_model_name") or _DEFAULT_MODEL
    if timeout is None:
        timeout = int(settings.get("qwen_timeout") or 300)

    if not api_key:
        raise RuntimeError(
            "qwen_api_key 未配置。"
            "请前往「系统设置」填入，或设置环境变量 QWEN_API_KEY"
        )

    url = f"{base_url}/chat/completions"
    payload: dict = {
        "model": model,
        "max_tokens": max_tokens,
        "temperature": temperature,
        "messages": [{"role": "user", "content": user_prompt}],
    }
    if system_prompt:
        payload["messages"].insert(0, {"role": "system", "content": system_prompt})

    headers = {
        "Authorization": f"Bearer {api_key}",
        "Content-Type": "application/json",
    }

    logger.info("[qwen] POST %s model=%s max_tokens=%s", url, model, max_tokens)
    data = _post_chat(url, headers, payload, timeout, "qwen")

    # 解析 OpenAI 兼容响应
    choices = data.get("choices") or []
    if not choices:
        raise RuntimeError(f"Qwen 返回空 choices: {data!r}")

    text = choices[0].get("message", {}).get("content", "").strip()
    if not text:
        raise RuntimeError(f"Qwen 返回为空: {data!r}")

    # 记录 token 用量
    usage = data.get("usage")
    if usage:
        logger.info("[qwen] 用量 prompt=%s completion=%s total=%s",
                     usage.get("prompt_tokens"), usage.get("completion_tokens"),
                     usage.get("total_tokens"))

    return text


def call_qwen_stream(
    settings: dict,
    *,
    user_prompt: str,
    system_prompt: Optional[str] = None,
    max_tokens: int = 8192,
    timeout: Optional[int] = None,
    model: Optional[str] = None,
    temperature: float = 0.7,
) -> Generator[str, None, None]:
    """流式调用 Qwen/OpenAI 兼容接口，逐 chunk 生成文本。

    Args:
        settings: 包含 qwen_* 配置的字典
        user_prompt: 用户消息
        system_prompt: 系统提示词（可选）
        max_tokens: 最大输出 token 数
        timeout: 超时秒数
        model: 模型名称（覆盖默认值）
        temperature: 温度参数

    Yields:
        每次返回一个文本片段 (str)

    Example:
        for chunk in call_qwen_stream(settings, user_prompt="你好"):
            print(chunk, end="", flush=True)
    """
    base_url = (settings.get("qwen_base_url") or "").rstrip("/")
    api_key = settings.get("qwen_api_key") or ""
    if not base_url:
        base_url = os.environ.get("QWEN_BASE_URL", _DEFAULT_BASE_URL).rstrip("/")
    if not api_key:
        api_key = os.environ.get("QWEN_API_KEY", "")
    if not base_url:
        base_url = _DEFAULT_BASE_URL
    if not api_key:
        api_key = _DEFAULT_API_KEY

    model = model or settings.get("qwen_model_name") or _DEFAULT_MODEL
    if timeout is None:
        timeout = int(settings.get("qwen_timeout") or 300)

    if not api_key:
        raise RuntimeError("qwen_api_key 未配置")

    url = f"{base_url}/chat/completions"
    payload: dict = {
        "model": model,
        "max_tokens": max_tokens,
        "temperature": temperature,
        "stream": True,  # 开启流式输出
        "messages": [{"role": "user", "content": user_prompt}],
    }
    if system_prompt:
        payload["messages"].insert(0, {"role": "system", "content": system_prompt})

    headers = {
        "Authorization": f"Bearer {api_key}",
        "Content-Type": "application/json",
    }

    logger.info("[qwen-stream] POST %s model=%s stream=True", url, model)

    try:
        with httpx.Client(timeout=timeout, trust_env=False) as client:
            with client.stream("POST", url, headers=headers, json=payload) as resp:
                if resp.status_code >= 400:
                    body = resp.text[:600]
                    raise RuntimeError(f"Qwen Stream HTTP {resp.status_code}: {body}")

                # 解析 SSE 流
                for line in resp.iter_lines():
                    if not line:
                        continue
                    line = line.strip()
                    if not line.startswith("data: "):
                        continue
                    data_str = line[6:]  # 去掉 "data: " 前缀
                    if data_str.strip() == "[DONE]":
                        break
                    try:
                        chunk_data = json.loads(data_str)
                        choices = chunk_data.get("choices") or []
                        if choices:
                            delta = choices[0].get("delta", {})
                            content = delta.get("content", "")
                            if content:
                                yield content
                    except json.JSONDecodeError:
                        logger.debug("[qwen-stream] 无法解析 chunk: %s", data_str[:200])
                        continue

    except Exception as e:
        logger.exception("[qwen-stream] 流式请求异常")
        raise


def call_qwen_with_tools(
    settings: dict,
    *,
    user_prompt: str,
    system_prompt: Optional[str] = None,
    tools: list[dict] | None = None,
    max_tokens: int = 8192,
    timeout: Optional[int] = None,
    model: Optional[str] = None,
) -> str | dict:
    """支持 function calling 的 Qwen 调用（预留扩展）。"""
    # TODO: 后续可支持结构化输出 / tool use 场景
    return call_qwen(
        settings,
        user_prompt=user_prompt,
        system_prompt=system_prompt,
        max_tokens=max_tokens,
        timeout=timeout,
        model=model,
    )


# ============================================================
# 辅助：加载 Qwen 配置（与 llm_claude 保持一致的模式）
# ============================================================

def load_qwen_settings(db_module=None) -> dict:
    """从 DB system_setting 表加载 qwen_* 配置。

    返回字典包含：
      qwen_base_url, qwen_api_key, qwen_model_name, qwen_timeout
    """
    if db_module is None:
        import db as db_module

    keys = ["qwen_base_url", "qwen_api_key", "qwen_model_name", "qwen_timeout"]
    settings: dict = {}
    for k in keys:
        try:
            row = db_module.fetch_one(
                "SELECT setting_value FROM system_setting WHERE setting_key = %s", (k,)
            )
            if row:
                settings[k] = row["setting_value"]
        except Exception:
            pass
    return settings
