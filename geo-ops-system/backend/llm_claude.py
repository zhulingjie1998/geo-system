"""llm_claude.py — Claude (Anthropic) client for the GEO system.

Talks to the /v1/messages endpoint (currently hosted on LLM 网关, but
settable via system_setting keys). Kept separate from brand_analyzer so weekly
report generation doesn't entangle with per-result brand extraction.

Settings keys (from system_setting table):
  claude_base_url   (default: )
  claude_api_key
  claude_model_name (default: claude-sonnet-4-6)
  claude_timeout    (default: 180)
"""

from __future__ import annotations

import json
import logging
import re
import time
from typing import Optional

import httpx

logger = logging.getLogger("llm_claude")

# ── 重试策略 ──────────────────────────────────────────────────────────
# 背景：上游 LLM 网关 经 AWS Bedrock 代理，实测同一请求会偶发
# 400 ValidationException（"InvokeModel: operation error Bedrock ..."）
# 几分钟后又恢复 200——属上游瞬时抽风。报告生成一次跑数十分钟，单次
# 瞬时失败不应毁掉整份报告，故统一在此做重试。
_MAX_ATTEMPTS = 5
# 尝试间隔（秒）：长度 = _MAX_ATTEMPTS-1；最坏额外 ~45s，远小于报告时长
_RETRY_BACKOFF = [3, 6, 12, 24]


def _is_retryable(status: Optional[int]) -> bool:
    """status=None 为网络层异常（超时/断连）→ 重试；
    401/403 鉴权问题重试无意义 → 直接抛；
    其余（400/408/409/425/429/5xx 等）一律视为可能瞬时 → 重试。"""
    if status is None:
        return True
    if status in (401, 403):
        return False
    return True


def _post_messages(url: str, headers: dict, payload: dict,
                   timeout: int, label: str) -> dict:
    """POST /v1/messages，瞬时失败最多重试 _MAX_ATTEMPTS 次，全失败再抛。

    返回解析后的 JSON dict。最终失败抛 RuntimeError，并带上 HTTP 状态码
    与响应体片段（修复原先 raise_for_status 吞掉 Bedrock 真实原因的问题）。
    """
    last_status: Optional[int] = None
    last_body = ""
    for attempt in range(1, _MAX_ATTEMPTS + 1):
        try:
            with httpx.Client(timeout=timeout, trust_env=False) as client:
                resp = client.post(url, headers=headers, json=payload)
            if resp.status_code < 300:
                if attempt > 1:
                    logger.info("[%s] 第 %d 次尝试成功（前 %d 次瞬时失败）",
                                label, attempt, attempt - 1)
                return resp.json()
            last_status = resp.status_code
            last_body = (resp.text or "")[:600]
            if not _is_retryable(last_status):
                raise RuntimeError(
                    f"{label} 请求被拒(HTTP {last_status})，不可重试：{last_body[:400]}"
                )
            logger.warning("[%s] 第 %d/%d 次 HTTP %s，将重试。body=%s",
                           label, attempt, _MAX_ATTEMPTS, last_status, last_body[:240])
        except RuntimeError:
            raise
        except Exception as e:  # 网络层：超时 / 断连 / DNS 等
            last_status = None
            last_body = repr(e)
            logger.warning("[%s] 第 %d/%d 次网络异常，将重试：%s",
                           label, attempt, _MAX_ATTEMPTS, last_body[:240])
        if attempt < _MAX_ATTEMPTS:
            time.sleep(_RETRY_BACKOFF[min(attempt - 1, len(_RETRY_BACKOFF) - 1)])
    raise RuntimeError(
        f"{label} 连续 {_MAX_ATTEMPTS} 次失败"
        + (f"（最后 HTTP {last_status}）" if last_status else "（网络异常）")
        + f"：{last_body[:400]}"
    )


def call_claude(
    settings: dict,
    *,
    user_prompt: str,
    system_prompt: Optional[str] = None,
    max_tokens: int = 4096,
    timeout: Optional[int] = None,
    model: Optional[str] = None,
    **_ignored,  # P3: 吞掉历史 `temperature=` 等已废弃参数，避免破坏调用方
) -> str:
    """Send a single-turn request to Claude and return the concatenated text content.

    Raises RuntimeError if the API key is missing or the response is malformed.
    Network / HTTP errors are re-raised so callers can decide retry policy.

    timeout: 显式覆盖 settings.claude_timeout；大 max_tokens 输出场景应传更大值
             （如 brand_reporter 一次输出 50k+ tokens，建议 600 秒）。

    P3 (2026-05-19)：移除 temperature 形参。
      实测 LLM 网关→Bedrock 后端对非默认 temperature 会间歇返回 400
      ValidationException；省略该字段（用模型默认）100% 稳定。
      旧调用方传 temperature=x 会被 **_ignored 吞掉，不影响行为。
    """
    if "temperature" in _ignored:
        logger.debug("[claude] temperature=%s ignored (P3: param removed; bedrock requires default)",
                     _ignored["temperature"])

    base_url = (settings.get("claude_base_url") or "").rstrip("/")
    api_key = settings.get("claude_api_key") or ""
    model = model or settings.get("claude_model_name") or "claude-sonnet-4-6"
    if timeout is None:
        timeout = int(settings.get("claude_timeout") or 180)

    if not api_key:
        raise RuntimeError("claude_api_key 未配置，请前往系统设置填入")

    url = f"{base_url}/v1/messages"
    payload: dict = {
        "model": model,
        "max_tokens": max_tokens,
        "messages": [{"role": "user", "content": user_prompt}],
    }
    if system_prompt:
        payload["system"] = system_prompt

    headers = {
        "x-api-key": api_key,
        "content-type": "application/json",
        "anthropic-version": "2023-06-01",
    }

    logger.info("[claude] POST %s model=%s max_tokens=%s", url, model, max_tokens)
    data = _post_messages(url, headers, payload, timeout, "claude")

    content_blocks = data.get("content") or []
    texts = [b.get("text", "") for b in content_blocks if isinstance(b, dict) and b.get("type") == "text"]
    text = "".join(texts).strip()
    if not text:
        raise RuntimeError(f"Claude 返回为空: {data!r}")
    return text


def call_claude_with_image(
    settings: dict,
    *,
    image_bytes: bytes,
    image_media_type: str,
    user_prompt: str,
    system_prompt: Optional[str] = None,
    max_tokens: int = 4096,
    timeout: Optional[int] = None,
    model: Optional[str] = None,
    **_ignored,  # P3: 吞掉历史 `temperature=` 等已废弃参数
) -> str:
    """Claude Vision 多模态：把图片+文字 prompt 一起发，返回模型识别的文字。

    image_media_type: 'image/jpeg' / 'image/png' / 'image/gif' / 'image/webp'
    image_bytes:      原始字节，内部 base64

    P3 (2026-05-19)：移除 temperature 形参，理由同 call_claude。
    """
    if "temperature" in _ignored:
        logger.debug("[claude_vision] temperature=%s ignored (P3)", _ignored["temperature"])

    import base64
    base_url = (settings.get("claude_base_url") or "").rstrip("/")
    api_key = settings.get("claude_api_key") or ""
    model = model or settings.get("claude_model_name") or "claude-sonnet-4-6"
    if timeout is None:
        timeout = int(settings.get("claude_timeout") or 180)
    if not api_key:
        raise RuntimeError("claude_api_key 未配置")

    image_b64 = base64.standard_b64encode(image_bytes).decode("ascii")
    url = f"{base_url}/v1/messages"
    payload: dict = {
        "model": model,
        "max_tokens": max_tokens,
        "messages": [{
            "role": "user",
            "content": [
                {"type": "image", "source": {
                    "type": "base64", "media_type": image_media_type, "data": image_b64,
                }},
                {"type": "text", "text": user_prompt},
            ],
        }],
    }
    if system_prompt:
        payload["system"] = system_prompt

    headers = {
        "x-api-key": api_key,
        "content-type": "application/json",
        "anthropic-version": "2023-06-01",
    }
    logger.info("[claude-vision] POST %s model=%s img_size=%dKB", url, model, len(image_bytes)//1024)
    data = _post_messages(url, headers, payload, timeout, "claude-vision")

    content_blocks = data.get("content") or []
    texts = [b.get("text", "") for b in content_blocks if isinstance(b, dict) and b.get("type") == "text"]
    text = "".join(texts).strip()
    if not text:
        raise RuntimeError(f"Claude Vision 返回为空: {data!r}")
    return text


# ═══════════════════════════════════════════════════════════════════════
# JSON 容错解析（多 reporter 共用）
# ═══════════════════════════════════════════════════════════════════════

def _escape_inner_quotes(s: str) -> str:
    """扫描 JSON 文本，将字符串值内出现的未转义双引号转义。
    判定"字符串终止引号"的规则：下一个非空白字符为 , : } ] 或换行；
    其它情况一律视为串内引号，转为 \\"。"""
    out = []
    i, n = 0, len(s)
    in_str = False
    escaped = False
    while i < n:
        c = s[i]
        if not in_str:
            out.append(c)
            if c == '"':
                in_str = True
            i += 1
            continue
        if escaped:
            out.append(c)
            escaped = False
            i += 1
            continue
        if c == '\\':
            out.append(c)
            escaped = True
            i += 1
            continue
        if c == '"':
            j = i + 1
            while j < n and s[j] in ' \t':
                j += 1
            if j >= n or s[j] in ',:}]\r\n':
                out.append(c)
                in_str = False
            else:
                out.append('\\"')
            i += 1
            continue
        out.append(c)
        i += 1
    return ''.join(out)


def parse_json_lenient(raw: str, *, with_escape_quotes: bool = False) -> Optional[dict]:
    """多阶段宽容解析 LLM 返回的 JSON 文本。失败返回 None。

    阶段：
      1. 去 markdown 代码围栏 ```json ... ```
      2. 截取第一个 { 到最后一个 }
      3. 中文引号 → ASCII 引号
      4. 去尾逗号（trailing comma）
      5. with_escape_quotes=True 时启用串内引号转义（最严格修复，weekly_reporter 用）

    brand_reporter 调用时 with_escape_quotes=False（保持原有行为，更保守）；
    weekly_reporter 调用时 with_escape_quotes=True（保留原有更鲁棒的修复）。
    """
    if not raw:
        return None
    txt = raw.strip()
    if txt.startswith("```"):
        txt = re.sub(r"^```[a-zA-Z]*\s*\n?", "", txt)
        if txt.endswith("```"):
            txt = txt[:-3]
        txt = txt.strip()
    m = re.search(r"\{[\s\S]*\}", txt)
    candidate = m.group() if m else txt
    zh_norm = candidate.replace("“", '"').replace("”", '"').replace("‘", "'").replace("’", "'")
    fixers = [
        lambda s: s,
        lambda s: re.sub(r",\s*([}\]])", r"\1", s),
        lambda s: zh_norm,
        lambda s: re.sub(r",\s*([}\]])", r"\1", zh_norm),
    ]
    if with_escape_quotes:
        fixers += [
            lambda s: _escape_inner_quotes(zh_norm),
            lambda s: re.sub(r",\s*([}\]])", r"\1", _escape_inner_quotes(zh_norm)),
        ]
    for fix in fixers:
        try:
            return json.loads(fix(candidate))
        except Exception:
            continue
    # 终极兜底:json_repair(截断/未闭合字符串/未转义裸引号/多余逗号都能容错抢救)。
    # 解决 Claude 偶发把 JSON 截断或串内带裸引号时,保守修复器全废、报告 91% 崩溃的问题。
    try:
        import json_repair
        repaired = json_repair.loads(candidate)
        if isinstance(repaired, dict) and repaired:
            return repaired
    except Exception:
        pass
    return None
