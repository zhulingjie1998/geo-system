"""WordPress REST API 发布服务。

对接 WordPress 站点的 Application Passwords 认证，支持：
- 创建/更新/删除文章
- 上传媒体文件
- 分类管理
- 连通性测试
"""

from __future__ import annotations

import base64
import logging
import re
import time
from typing import Optional

import requests

logger = logging.getLogger("gunicorn.error")

# WP REST API 默认超时（上传大图/网络慢时需要较长）
_WP_TIMEOUT = 60


def _build_auth_header(username: str, app_password: str) -> dict:
    """构建 WordPress Application Passwords 认证头。"""
    token = base64.b64encode(f"{username}:{app_password}".encode()).decode()
    return {"Authorization": f"Basic {token}"}


def _normalize_wp_url(site_url: str) -> str:
    """确保站点 URL 以 / 结尾，用于拼接 REST API 路径。"""
    url = site_url.strip().rstrip("/")
    if not url.startswith(("http://", "https://")):
        url = "https://" + url
    return url + "/"


def test_connection(site_url: str, username: str, app_password: str) -> dict:
    """测试 WordPress 站点连通性 + 认证有效性。
    
    Returns:
        {'ok': bool, 'site_info': dict|None, 'error': str|None}
    """
    base = _normalize_wp_url(site_url)
    headers = _build_auth_header(username, app_password)
    try:
        r = requests.get(
            f"{base}wp-json/wp/v2/users/me",
            headers=headers,
            timeout=_WP_TIMEOUT,
        )
        if r.status_code == 200:
            user = r.json()
            return {
                "ok": True,
                "site_info": {
                    "site_name": user.get("name", ""),
                    "user_role": user.get("roles", [""])[0] if user.get("roles") else "",
                    "avatar": user.get("avatar_urls", {}).get("96", ""),
                },
                "error": None,
            }
        elif r.status_code == 401:
            return {"ok": False, "site_info": None, "error": "认证失败：用户名或令牌不正确"}
        elif r.status_code == 403:
            return {"ok": False, "site_info": None, "error": "访问被拒绝：可能未启用 REST API 或 IP 被限制"}
        elif r.status_code == 404:
            return {"ok": False, "site_info": None, "error": "REST API 未找到：请确认是 WordPress 站点"}
        else:
            try:
                body = r.json()
                msg = body.get("message", r.text[:200])
            except Exception:
                msg = r.text[:200]
            return {"ok": False, "site_info": None, "error": f"HTTP {r.status_code}: {msg}"}
    except requests.exceptions.ConnectionError:
        return {"ok": False, "site_info": None, "error": "无法连接到站点，请检查地址是否正确"}
    except requests.exceptions.Timeout:
        return {"ok": False, "site_info": None, "error": "连接超时，站点响应过慢"}
    except Exception as e:
        logger.exception("wp test_connection error")
        return {"ok": False, "site_info": None, "error": str(e)}


def list_categories(site_url: str, username: str, app_password: str, per_page: int = 50) -> list[dict]:
    """获取站点分类列表。"""
    base = _normalize_wp_url(site_url)
    headers = _build_auth_header(username, app_password)
    params = {"per_page": per_page, "orderby": "count", "order": "desc"}
    try:
        r = requests.get(f"{base}wp-json/wp/v2/categories", headers=headers, params=params, timeout=_WP_TIMEOUT)
        if r.status_code == 200:
            return r.json()
        return []
    except Exception as e:
        logger.warning("wp list_categories error: %s", e)
        return []


def create_post(
    site_url: str,
    username: str,
    app_password: str,
    title: str,
    content: str,
    status: str = "publish",
    category_ids: Optional[list[int]] = None,
    featured_media_id: Optional[int] = None,
    excerpt: str = "",
    tags: Optional[list[int]] = None,
) -> dict:
    """发布文章到 WordPress 站点。
    
    Args:
        site_url: WP 站点地址
        username: WP 用户名
        app_password: WP Application Password
        title: 文章标题
        content: 文章正文（HTML 格式）
        status: publish/draft/pending/future
        category_ids: 分类 ID 列表
        featured_media_id: 特色图片 media ID
        excerpt: 摘要
        tags: 标签 ID 列表
    
    Returns:
        {'ok': bool, 'post_id': int, 'post_url': str, 'link': str, 'error': str|None}
    """
    base = _normalize_wp_url(site_url)
    headers = _build_auth_header(username, app_password)
    headers["Content-Type"] = "application/json"

    payload = {
        "title": title,
        "content": content,
        "status": status,
    }
    if excerpt:
        payload["excerpt"] = excerpt
    if category_ids:
        payload["categories"] = category_ids
    if featured_media_id:
        payload["featured_media"] = featured_media_id
    if tags:
        payload["tags"] = tags

    try:
        r = requests.post(
            f"{base}wp-json/wp/v2/posts",
            headers=headers,
            json=payload,
            timeout=_WP_TIMEOUT,
        )
        if r.status_code in (200, 201):
            post = r.json()
            post_id = post.get("id")
            post_url = post.get("link", "")
            # 如果 WP 没有返回 link，尝试用 permalink_template 或构建回退 URL
            if not post_url and post_id:
                post_url = post.get("permalink_template", "").replace("%postname%", post.get("slug", str(post_id)))
                if not post_url:
                    post_url = f"{base}?p={post_id}"
            return {
                "ok": True,
                "post_id": post_id,
                "post_url": post_url,
                "link": post_url,
                "status": post.get("status"),
                "error": None,
            }
        elif r.status_code == 401:
            return {"ok": False, "post_id": 0, "post_url": "", "error": "认证失败"}
        elif r.status_code == 403:
            return {"ok": False, "post_id": 0, "post_url": "", "error": "无发布权限"}
        else:
            try:
                body = r.json()
                # WP 错误可能返回 {code, message, data}
                msgs = []
                if isinstance(body, dict):
                    msgs.append(body.get("message", ""))
                    extra = body.get("data", {})
                    if isinstance(extra, dict):
                        for k, v in extra.items():
                            if k not in ("status",):
                                msgs.append(f"{k}: {v}")
                else:
                    msgs.append(str(body)[:300])
                err = "; ".join(filter(None, msgs)) or f"HTTP {r.status_code}"
            except Exception:
                err = f"HTTP {r.status_code}: {r.text[:200]}"
            return {"ok": False, "post_id": 0, "post_url": "", "error": err}
    except requests.exceptions.ConnectionError:
        return {"ok": False, "post_id": 0, "post_url": "", "error": "无法连接到站点"}
    except requests.exceptions.Timeout:
        return {"ok": False, "post_id": 0, "post_url": "", "error": "发布超时"}
    except Exception as e:
        logger.exception("wp create_post error")
        return {"ok": False, "post_id": 0, "post_url": "", "error": str(e)}


def update_post(
    site_url: str,
    username: str,
    app_password: str,
    wp_post_id: int,
    title: Optional[str] = None,
    content: Optional[str] = None,
    status: Optional[str] = None,
) -> dict:
    """更新已有文章。"""
    base = _normalize_wp_url(site_url)
    headers = _build_auth_header(username, app_password)
    headers["Content-Type"] = "application/json"

    payload = {}
    if title is not None:
        payload["title"] = title
    if content is not None:
        payload["content"] = content
    if status is not None:
        payload["status"] = status

    try:
        r = requests.post(
            f"{base}wp-json/wp/v2/posts/{wp_post_id}",
            headers=headers,
            json=payload,
            timeout=_WP_TIMEOUT,
        )
        if r.status_code in (200, 201):
            post = r.json()
            return {
                "ok": True,
                "post_id": post.get("id"),
                "post_url": post.get("link", ""),
                "error": None,
            }
        return {"ok": False, "post_id": 0, "post_url": "", "error": f"HTTP {r.status_code}"}
    except Exception as e:
        logger.exception("wp update_post error")
        return {"ok": False, "post_id": 0, "post_url": "", "error": str(e)}


def delete_post(site_url: str, username: str, app_password: str, wp_post_id: int) -> dict:
    """删除已发布的文章（移至回收站）。"""
    base = _normalize_wp_url(site_url)
    headers = _build_auth_header(username, app_password)

    try:
        r = requests.delete(
            f"{base}wp-json/wp/v2/posts/{wp_post_id}?force=true",
            headers=headers,
            timeout=_WP_TIMEOUT,
        )
        if r.status_code in (200, 202):
            return {"ok": True, "error": None}
        return {"ok": False, "error": f"HTTP {r.status_code}"}
    except Exception as e:
        logger.exception("wp delete_post error")
        return {"ok": False, "error": str(e)}


def upload_media(
    site_url: str,
    username: str,
    app_password: str,
    file_data: bytes,
    filename: str,
    mime_type: str = "",
) -> dict:
    """上传媒体文件到 WordPress 媒体库。
    
    Returns:
        {'ok': bool, 'media_id': int, 'url': str, 'error': str|None}
    """
    base = _normalize_wp_url(site_url)
    headers = _build_auth_header(username, app_password)
    # 媒体上传不能用 JSON Content-Type
    headers.pop("Content-Type", None)

    if not mime_type:
        ext = filename.rsplit(".", 1)[-1].lower() if "." in filename else ""
        _MIME_MAP = {
            "jpg": "image/jpeg", "jpeg": "image/jpeg",
            "png": "image/png", "gif": "image/gif",
            "webp": "image/webp", "svg": "image/svg+xml",
            "pdf": "application/pdf",
            "doc": "application/msword",
            "docx": "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
        }
        mime_type = _MIME_MAP.get(ext, "application/octet-stream")

    try:
        r = requests.post(
            f"{base}wp-json/wp/v2/media",
            headers=headers,
            data=file_data,
            files={"file": (filename, file_data, mime_type)},
            timeout=_WP_TIMEOUT * 2,
        )
        if r.status_code in (200, 201):
            media = r.json()
            return {
                "ok": True,
                "media_id": media.get("id"),
                "url": media.get("source_url", media.get("link", "")),
                "error": None,
            }
        return {"ok": False, "media_id": 0, "url": "", "error": f"HTTP {r.status_code}"}
    except Exception as e:
        logger.exception("wp upload_media error")
        return {"ok": False, "media_id": 0, "url": "", "error": str(e)}


# ── HTML → WordPress 内容转换工具 ──────────────────────────────────────


def html_to_wp_content(html: str, images_map: Optional[dict] = None) -> str:
    """将富文本 HTML 转换为 WordPress 兼容内容。
    
    - 将本地/base64 图片替换为已上传的 WP 媒体 URL
    - 清理不安全的标签
    - 添加 WordPress 图片样式类
    """
    if not html:
        return ""

    content = html

    # 替换图片 URL（如果提供了映射）
    if images_map:
        for src, wp_url in images_map.items():
            content = content.replace(f'src="{src}"', f'src="{wp_url}"')
            content = content.replace(f"src='{src}'", f"src='{wp_url}'")

    # 移除 wangEditor 等编辑器特有的属性
    content = re.sub(r'\sdata-\w+(?:="[^"]*"|=\'[^\']*\')?', '', content)

    # 给图片添加 WordPress 对齐类
    content = re.sub(
        r'(<img[^>]+?)\s*/>',
        r'\1 class="alignnone size-full" />',
        content,
    )

    return content
