"""资源站点管理 + WordPress 发布路由。

提供：
- 站点 CRUD（增删改查、批量导入、连通性测试）
- 发布文章到指定站点
- 发布记录查询
"""

from __future__ import annotations

import logging
import time
from datetime import datetime

from flask import jsonify, request, session

import db
import wp_publisher

logger = logging.getLogger("gunicorn.error")


def _require_auth():
    """检查登录态，未登录返回 None（使用 Flask Session）"""
    uid = session.get("user_id")
    if not uid:
        return None
    return db.get_admin_user_by_id(int(uid))


def _json_auth_error():
    return jsonify({"error": "请先登录"}), 401


# ── 站点 CRUD ────────────────────────────────────────────────────────────


def api_resource_sites_list():
    """获取资源站点列表（支持按类型筛选）"""
    user = _require_auth()
    if not user:
        return _json_auth_error()

    site_type = (request.args.get("type") or "").strip()
    status = request.args.get("status")  # 可选 "1"=启用 "0"=停用

    conn = db.get_conn()
    where = ["1=1"]
    params = []
    if site_type:
        where.append("site_type=%s")
        params.append(site_type)
    if status is not None:
        where.append("status=%s")
        params.append(status)

    sql = f"""
        SELECT id, site_type, site_name, site_url, username,
               LEFT(application_password, 8) AS app_password_mask,
               status, last_test_at, last_test_result, last_test_error,
               created_at, updated_at
        FROM resource_site
        WHERE {' AND '.join(where)}
        ORDER BY site_type, site_name
    """
    rows = db._fetchall(conn, sql, params or None)
    # 补全各类型计数
    count_sql = "SELECT site_type, COUNT(*) AS cnt FROM resource_site WHERE status=1 GROUP BY site_type"
    type_counts = {r["site_type"]: r["cnt"] for r in db._fetchall(conn, count_sql)}
    return jsonify({"items": rows, "type_counts": type_counts})


def api_resource_site_create():
    """新增站点"""
    user = _require_auth()
    if not user:
        return _json_auth_error()

    data = request.get_json(silent=True) or {}
    site_type = (data.get("type") or data.get("site_type") or "blog").strip().lower()
    site_name = (data.get("name") or data.get("site_name") or "").strip()
    site_url = (data.get("url") or data.get("site_url") or "").strip()
    username = (data.get("username") or "").strip()
    app_password = (data.get("token") or data.get("application_password") or "").strip()

    if not site_name:
        return jsonify({"error": "站点名称不能为空"}), 400
    if not site_url:
        return jsonify({"error": "站点地址不能为空"}), 400
    if not username:
        return jsonify({"error": "用户名不能为空"}), 400
    if not app_password:
        return jsonify({"error": "令牌不能为空"}), 400
    if site_type not in ("blog", "forum", "b2b", "qa"):
        return jsonify({"error": "站点类型必须是 blog/forum/b2b/qa"}), 400

    now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    conn = db.get_conn()
    with conn.cursor() as cur:
        cur.execute(
            """INSERT INTO resource_site (site_type, site_name, site_url, username, application_password, status, created_at, updated_at)
               VALUES (%s,%s,%s,%s,%s,1,%s,%s)""",
            (site_type, site_name, site_url, username, app_password, now, now),
        )
        site_id = cur.lastrowid
    conn.commit()

    logger.info("Resource site created: id=%d name=%s type=%s url=%s by=%s", site_id, site_name, site_type, site_url, user.get("username"))
    return jsonify({"ok": True, "id": site_id, "message": "站点已添加"})


def api_resource_site_update(site_id):
    """更新站点信息"""
    user = _require_auth()
    if not user:
        return _json_auth_error()

    data = request.get_json(silent=True) or {}
    conn = db.get_conn()

    # 先检查存在性
    existing = db._fetchall(conn, "SELECT id FROM resource_site WHERE id=%s", (site_id,))
    if not existing:
        return jsonify({"error": "站点不存在"}), 404

    sets = []
    params = []
    _fields = {
        "name": "site_name",
        "url": "site_url",
        "type": "site_type",
        "username": "username",
        "token": "application_password",
        "status": "status",
    }
    for key, col in _fields.items():
        if key in data and data[key] is not None:
            val = str(data[key]).strip()
            sets.append(f"{col}=%s")
            params.append(val)

    if not sets:
        return jsonify({"ok": True, "message": "无更新"})

    sets.append("updated_at=%s")
    params.append(datetime.now().strftime("%Y-%m-%d %H:%M:%S"))
    params.append(site_id)

    with conn.cursor() as cur:
        cur.execute(f"UPDATE resource_site SET {', '.join(sets)} WHERE id=%s", params)
    conn.commit()

    return jsonify({"ok": True, "message": "已更新"})


def api_resource_site_delete(site_id):
    """删除站点（同时清理发布记录）"""
    user = _require_auth()
    if not user:
        return _json_auth_error()

    conn = db.get_conn()
    with conn.cursor() as cur:
        cur.execute("DELETE FROM publish_record WHERE site_id=%s", (site_id,))
        cur.execute("DELETE FROM resource_site WHERE id=%s", (site_id,))
    conn.commit()

    return jsonify({"ok": True, "message": "已删除"})


def api_resource_site_test(site_id):
    """测试站点连通性 + 认证有效性"""
    user = _require_auth()
    if not user:
        return _json_auth_error()

    conn = db.get_conn()
    row = db._fetchall(
        conn,
        "SELECT site_url, username, application_password FROM resource_site WHERE id=%s",
        (site_id,),
    )
    if not row:
        return jsonify({"error": "站点不存在"}), 404

    site = row[0]
    result = wp_publisher.test_connection(site["site_url"], site["username"], site["application_password"])

    now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    test_result = "ok" if result["ok"] else "fail"
    test_error = result.get("error") or ""

    with conn.cursor() as cur:
        cur.execute(
            "UPDATE resource_site SET last_test_at=%s, last_test_result=%s, last_test_error=%s, updated_at=%s WHERE id=%s",
            (now, test_result, test_error, now, site_id),
        )
    conn.commit()

    return jsonify(result)


def api_resource_sites_batch_import():
    """批量导入站点（从 Excel 数据格式）"""
    user = _require_auth()
    if not user:
        return _json_auth_error()

    data = request.get_json(silent=True) or {}
    items = data.get("items") or data.get("sites") or []
    if not isinstance(items, list) or not items:
        return jsonify({"error": "items 必须是非空数组"}), 400

    # 调试日志：打印接收到的数据
    import logging
    logger = logging.getLogger(__name__)
    logger.warning(f"[批量导入] 收到 {len(items)} 条数据，第一条示例: {items[0] if items else 'empty'}")

    now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    conn = db.get_conn()
    created = 0
    skipped = 0
    errors = []

    for idx, item in enumerate(items):
        # 支持多种字段名映射
        raw_type = str(item.get("平台类型") or item.get("type") or "博客").strip()
        # 中文平台类型映射到英文
        type_map = {"博客": "blog", "论坛": "forum", "b2b": "b2b", "问答": "qa",
                    "Blog": "blog", "Forum": "forum", "B2B": "b2b", "QA": "qa"}
        site_type = type_map.get(raw_type, raw_type.lower())
        if site_type not in ("blog", "forum", "b2b", "qa"):
            site_type = "blog"
        site_name = str(item.get("平台名称") or item.get("name") or "").strip()
        site_url = str(item.get("平台地址") or item.get("url") or "").strip()
        username = str(item.get("用户名") or item.get("username") or "admin").strip()
        token = str(item.get("令牌") or item.get("token") or item.get("application_password") or "").strip()

        logger.warning(f"[批量导入] 第{idx+1}条: type={site_type}, name={site_name}, url={site_url}, user={username}")

        if not site_name or not site_url:
            logger.warning(f"[批量导入] 第{idx+1}条跳过: name或url为空")
            skipped += 1
            continue
        if site_type not in ("blog", "forum", "b2b", "qa"):
            site_type = "blog"

        try:
            with conn.cursor() as cur:
                cur.execute(
                    """INSERT INTO resource_site (site_type, site_name, site_url, username, application_password, status, created_at, updated_at)
                       VALUES (%s,%s,%s,%s,%s,1,%s,%s)""",
                    (site_type, site_name, site_url, username, token, now, now),
                )
                created += cur.rowcount
        except Exception as e:
            errors.append(f"{site_name}: {e}")
            skipped += 1

    conn.commit()
    return jsonify({
        "ok": True,
        "created": created,
        "skipped": skipped,
        "errors": errors[:20],  # 最多返回前 20 条错误
    })


# ── 发布功能 ─────────────────────────────────────────────────────────────


def api_resource_publish():
    """发布文章到指定 WordPress 站点。

    Request body:
        account_id: int       客户 ID
        article_id: int       文章 ID（可选）
        site_ids: [int]       目标站点 ID 列表
        title: str            文章标题
        content: str          文章正文（HTML 格式）
        status: str           publish/draft（默认 publish）
        category_ids: [int]   分类 ID 列表（可选）
    """
    user = _require_auth()
    if not user:
        return _json_auth_error()

    data = request.get_json(silent=True) or {}
    account_id = int(data.get("account_id") or 0)
    site_ids = data.get("site_ids") or []
    title = (data.get("title") or "").strip()
    content = data.get("content") or ""
    status = (data.get("status") or "publish").strip()
    category_ids = data.get("category_ids")

    if not isinstance(site_ids, list) or not site_ids:
        return jsonify({"error": "请选择至少一个目标站点"}), 400
    if not title:
        return jsonify({"error": "标题不能为空"}), 400
    if not content:
        return jsonify({"error": "正文不能为空"}), 400

    conn = db.get_conn()
    # 获取所有目标站点信息
    placeholders = ",".join(["%s"] * len(site_ids))
    
    # 处理 article_id：支持纯数字和字符串格式（如 "batch_xxx"）
    raw_article_id = data.get("article_id")
    try:
        article_id_int = int(raw_article_id) if raw_article_id else 0
    except (ValueError, TypeError):
        article_id_int = 0  # 非数字ID（如 batch_xxx）存储为0，保留原始值用于日志
    
    sites = db._fetchall(
        conn,
        f"SELECT id, site_type, site_name, site_url, username, application_password, last_test_result FROM resource_site WHERE id IN ({placeholders}) AND status=1",
        tuple(site_ids),
    )

    # 拦截未连通的站点（last_test_result='fail'），不允许发布
    blocked = [s for s in sites if s.get("last_test_result") == "fail"]
    if blocked:
        blocked_names = "、".join(s["site_name"] for s in blocked)
        return jsonify({
            "error": f"以下站点连接状态异常，不支持发布：{blocked_names}。请先测试连接恢复后再发布。",
            "blocked_sites": [{"id": s["id"], "site_name": s["site_name"]} for s in blocked],
        }), 400

    results = []
    now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

    for site in sites:
        # 发布到 WP
        wp_result = wp_publisher.create_post(
            site_url=site["site_url"],
            username=site["username"],
            app_password=site["application_password"],
            title=title,
            content=content,
            status=status,
            category_ids=category_ids,
        )

        pub_status = "published" if wp_result["ok"] else "failed"
        post_id = wp_result.get("post_id") or 0
        post_url = wp_result.get("post_url") or ""
        error_msg = wp_result.get("error") or ""
        pub_at = now if wp_result["ok"] else None

        # 发布成功但未回传落地页URL，记录警告信息
        if wp_result["ok"] and not post_url:
            error_msg = "发布成功但未获取到落地页URL"
            logger.warning("WP publish ok but no post_url: site=%s post_id=%s", site["site_name"], post_id)

        # 发布失败时更新站点连接状态为 fail
        if not wp_result["ok"]:
            try:
                with conn.cursor() as cur:
                    cur.execute(
                        "UPDATE resource_site SET last_test_result='fail', last_test_error=%s, last_test_at=%s, updated_at=%s WHERE id=%s",
                        (error_msg[:500] or "发布失败", now, now, site["id"]),
                    )
            except Exception:
                pass

        # 写入发布记录（使用转换后的整数ID）
        with conn.cursor() as cur:
            cur.execute(
                """INSERT INTO publish_record (account_id, article_id, site_id, post_id, post_url, title, status, error_message, published_at, created_at)
                   VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)""",
                (account_id, article_id_int, site["id"], post_id, post_url, title, pub_status, error_msg, pub_at, now),
            )

        results.append({
            "site_id": site["id"],
            "site_name": site["site_name"],
            "site_type": site["site_type"],
            "ok": wp_result["ok"],
            "post_id": post_id,
            "post_url": post_url,
            "error": error_msg,
        })

    conn.commit()

    success_count = sum(1 for r in results if r["ok"])
    fail_count = len(results) - success_count

    return jsonify({
        "ok": True,
        "total": len(results),
        "success": success_count,
        "failed": fail_count,
        "results": results,
    })


def api_resource_publish_records():
    """获取发布记录列表"""
    user = _require_auth()
    if not user:
        return _json_auth_error()

    account_id = request.args.get("account_id")
    site_id = request.args.get("site_id")
    page = max(1, int(request.args.get("page") or 1))
    page_size = min(100, max(10, int(request.args.get("page_size") or 20)))

    conn = db.get_conn()
    where = ["1=1"]
    params = []

    if account_id:
        where.append("pr.account_id=%s")
        params.append(int(account_id))
    if site_id:
        where.append("pr.site_id=%s")
        params.append(int(site_id))

    where_str = " AND ".join(where)
    offset = (page - 1) * page_size

    total_row = db._fetchall(conn, f"SELECT COUNT(*) AS cnt FROM publish_record pr WHERE {where_str}", params or None)
    total = total_row[0]["cnt"] if total_row else 0

    rows = db._fetchall(
        conn,
        f"""SELECT pr.id, pr.account_id, pr.site_id, pr.post_id, pr.post_url, pr.title,
                   pr.status, pr.error_message, pr.published_at, pr.created_at,
                   rs.site_name, rs.site_type
            FROM publish_record pr
            LEFT JOIN resource_site rs ON rs.id = pr.site_id
            WHERE {where_str}
            ORDER BY pr.created_at DESC
            LIMIT %s OFFSET %s""",
        (params or []) + [page_size, offset],
    )

    return jsonify({
        "items": rows,
        "total": total,
        "page": page,
        "page_size": page_size,
    })


# ── 路由注册 ────────────────────────────────────────────────────────────


def register(app):
    """注册所有路由到 Flask app。由 app.py 调用。"""

    # 端点列表：(rule, methods, view_func)
    endpoints = [
        ("/api/resource/sites", ["GET"], api_resource_sites_list),
        ("/api/resource/sites", ["POST"], api_resource_site_create),
        ("/api/resource/sites/<int:site_id>", ["PUT"], api_resource_site_update),
        ("/api/resource/sites/<int:site_id>", ["DELETE"], api_resource_site_delete),
        ("/api/resource/sites/<int:site_id>/test", ["POST"], api_resource_site_test),
        ("/api/resource/sites/batch-import", ["POST"], api_resource_sites_batch_import),
        ("/api/resource/publish", ["POST"], api_resource_publish),
        ("/api/resource/publish/records", ["GET"], api_resource_publish_records),
    ]

    for rule, methods, view_func in endpoints:
        app.add_url_rule(rule, view_func=view_func, methods=methods)
