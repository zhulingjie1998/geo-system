"""查词平台常量：平台展示名 ↔ 模型代码，以及别名归一。

供 db / 查词适配器 / 路由共用。查词的实际执行见 overseas_search_adapter。
"""

from __future__ import annotations

# 平台展示名 → 模型代码
PLATFORM_MODEL_MAP = {
    "ChatGPT": "chatgpt",
    "Gemini": "gemini",
    "Google AIO": "google_aio",
    "Google AIM": "google_aim",
    "Perplexity": "perplexity",
    "Copilot": "copilot",
}

# 别名表：兼容简写/历史/手动录入的非标准写法，统一映射到 PLATFORM_MODEL_MAP 的标准 key
PLATFORM_ALIASES = {
    # ChatGPT
    "chatgpt": "ChatGPT",
    "chatGpt": "ChatGPT",       # Ka 接口枚举
    "GPT": "ChatGPT",
    "gpt": "ChatGPT",
    "OpenAI": "ChatGPT",
    "openai": "ChatGPT",
    # Gemini
    "gemini": "Gemini",
    "Google Gemini": "Gemini",
    "Bard": "Gemini",
    # Google AIO (AI Overview)
    "google_aio": "Google AIO",
    "google": "Google AIO",      # Ka 接口枚举
    "aio": "Google AIO",
    "AIO": "Google AIO",
    "AI Overview": "Google AIO",
    "ai overview": "Google AIO",
    "Google AI Overview": "Google AIO",
    # Google AIM (AI Mode)
    "google_aim": "Google AIM",
    "googleAIM": "Google AIM",   # Ka 接口枚举
    "aim": "Google AIM",
    "AIM": "Google AIM",
    "AI Mode": "Google AIM",
    "ai mode": "Google AIM",
    "Google AI Mode": "Google AIM",
    # Perplexity
    "perplexity": "Perplexity",
    "PPLX": "Perplexity",
    "pplx": "Perplexity",
    # Copilot
    "copilot": "Copilot",
    "bingCopilot": "Copilot",   # Ka 接口枚举
    "Bing": "Copilot",
    "Bing Copilot": "Copilot",
    "Microsoft Copilot": "Copilot",
}


def normalize_platforms(plats) -> list:
    """把 platforms 列表里的别名/简写映射到标准 key；保持顺序、去重、丢弃空值。"""
    seen = set()
    out = []
    for p in (plats or []):
        s = (str(p) if p is not None else "").strip()
        if not s:
            continue
        s = PLATFORM_ALIASES.get(s, s)
        if s in seen:
            continue
        seen.add(s)
        out.append(s)
    return out


_normalize_platforms = normalize_platforms
