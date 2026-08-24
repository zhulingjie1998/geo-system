"""email_account_routes.py — 邮件发送账号 CRUD + 切换激活。

挂载方式：在 app.py 末尾加 `import email_account_routes; email_account_routes.register(app)`
"""
from __future__ import annotations

import logging
from datetime import datetime
from flask import jsonify, request, session, abort

import db

logger = logging.getLogger("email_account_routes")


def _require_admin():
    role = (session.get("role") or "").lower()
    if role in ("admin", "super_admin"):
        return
    if session.get("is_super_admin"):
        return
    abort(403)


def _now() -> str:
    return datetime.now().strftime("%Y-%m-%d %H:%M:%S")


def _row(r: dict) -> dict:
    if not r:
        return None
    # smtp_pass 脱敏：只返回 *** 提示已配置；前端编辑时单独询问是否替换
    pwd = r.get("smtp_pass") or ""
    return {
        "id": r["id"],
        "email": r["email"],
        "displayName": r.get("display_name") or "",
        "smtpHost": r.get("smtp_host") or "",
        "smtpPort": int(r.get("smtp_port") or 465),
        "smtpUser": r.get("smtp_user") or "",
        "smtpPassMasked": ("******" + pwd[-2:]) if pwd else "",
        "smtpPassConfigured": bool(pwd),
        "isActive": bool(int(r.get("is_active") or 0)),
        "remark": r.get("remark") or "",
        "createdAt": r.get("created_at") or "",
        "updatedAt": r.get("updated_at") or "",
    }


def register(app):

    @app.get("/api/email-accounts")
    def api_email_accounts_list():
        _require_admin()
        rows = db._fetchall(db.get_conn(),
            "SELECT * FROM email_account ORDER BY is_active DESC, id ASC")
        active_id = db.get_all_settings().get("email_active_account_id")
        return jsonify({
            "items": [_row(r) for r in rows],
            "activeId": int(active_id) if active_id else None,
        })

    @app.post("/api/email-accounts")
    def api_email_accounts_create():
        _require_admin()
        data = request.get_json(force=True, silent=True) or {}
        email = (data.get("email") or "").strip()
        smtp_user = (data.get("smtpUser") or email).strip()
        smtp_pass = (data.get("smtpPass") or "").strip()
        smtp_host = (data.get("smtpHost") or "").strip()
        smtp_port = int(data.get("smtpPort") or 465)
        display_name = (data.get("displayName") or "").strip()
        remark = (data.get("remark") or "").strip()
        if not email:
            return jsonify({"error": "email 必填"}), 400
        if not smtp_pass:
            return jsonify({"error": "smtpPass(授权码) 必填"}), 400
        if not smtp_host:
            # 智能推断常见服务商
            if email.endswith("@126.com"): smtp_host = "smtp.126.com"
            elif email.endswith("@163.com"): smtp_host = "smtp.163.com"
            elif email.endswith("@qq.com"): smtp_host = "smtp.qq.com"
            elif email.endswith("@gmail.com"): smtp_host = "smtp.gmail.com"
            elif email.endswith("@outlook.com") or email.endswith("@hotmail.com"): smtp_host = "smtp.office365.com"
            else: smtp_host = ""
        if not smtp_host:
            return jsonify({"error": "smtpHost 必填（无法从邮箱后缀自动推断）"}), 400
        conn = db.get_conn()
        cur = conn.cursor()
        try:
            cur.execute(
                "INSERT INTO email_account (email,display_name,smtp_host,smtp_port,smtp_user,smtp_pass,is_active,remark,created_at,updated_at) "
                "VALUES (%s,%s,%s,%s,%s,%s,1,%s,%s,%s) "
                "ON DUPLICATE KEY UPDATE display_name=VALUES(display_name),smtp_host=VALUES(smtp_host),"
                " smtp_port=VALUES(smtp_port),smtp_user=VALUES(smtp_user),smtp_pass=VALUES(smtp_pass),"
                " remark=VALUES(remark),updated_at=VALUES(updated_at)",
                (email, display_name, smtp_host, smtp_port, smtp_user, smtp_pass, remark, _now(), _now()))
            conn.commit()
            new_id = cur.lastrowid or db._fetchone(conn, "SELECT id FROM email_account WHERE email=%s", (email,))["id"]
        finally:
            cur.close()
        row = db._fetchone(conn, "SELECT * FROM email_account WHERE id=%s", (new_id,))
        return jsonify(_row(row))

    @app.put("/api/email-accounts/<int:aid>")
    def api_email_accounts_update(aid):
        _require_admin()
        data = request.get_json(force=True, silent=True) or {}
        sets, params = [], []
        if "displayName" in data:
            sets.append("display_name=%s"); params.append((data.get("displayName") or "").strip())
        if "smtpHost" in data:
            sets.append("smtp_host=%s"); params.append((data.get("smtpHost") or "").strip())
        if "smtpPort" in data:
            sets.append("smtp_port=%s"); params.append(int(data.get("smtpPort") or 465))
        if "smtpUser" in data:
            sets.append("smtp_user=%s"); params.append((data.get("smtpUser") or "").strip())
        if "smtpPass" in data and data.get("smtpPass"):
            # 仅当传了非空才覆盖密码，避免编辑时把已存密码清空
            sets.append("smtp_pass=%s"); params.append(str(data.get("smtpPass")).strip())
        if "remark" in data:
            sets.append("remark=%s"); params.append((data.get("remark") or "").strip())
        if "isActive" in data:
            sets.append("is_active=%s"); params.append(1 if data.get("isActive") else 0)
        if not sets:
            return jsonify({"error": "无可更新字段"}), 400
        sets.append("updated_at=%s"); params.append(_now())
        params.append(aid)
        conn = db.get_conn()
        cur = conn.cursor()
        try:
            cur.execute(f"UPDATE email_account SET {','.join(sets)} WHERE id=%s", tuple(params))
            conn.commit()
        finally:
            cur.close()
        row = db._fetchone(conn, "SELECT * FROM email_account WHERE id=%s", (aid,))
        if not row:
            return jsonify({"error": "账号不存在"}), 404
        return jsonify(_row(row))

    @app.delete("/api/email-accounts/<int:aid>")
    def api_email_accounts_delete(aid):
        _require_admin()
        conn = db.get_conn()
        cur = conn.cursor()
        try:
            cur.execute("DELETE FROM email_account WHERE id=%s", (aid,))
            conn.commit()
        finally:
            cur.close()
        # 若删的恰好是当前激活账号，把 active_id 清空
        active = db.get_all_settings().get("email_active_account_id")
        if active and int(active) == aid:
            with db.transaction() as c:
                db._exec(c, "UPDATE system_setting SET setting_value='' WHERE setting_key='email_active_account_id'")
        return jsonify({"ok": True})

    @app.post("/api/email-accounts/<int:aid>/activate")
    def api_email_accounts_activate(aid):
        """把指定账号设为当前发送邮箱（切换激活）。"""
        _require_admin()
        row = db._fetchone(db.get_conn(), "SELECT id,is_active FROM email_account WHERE id=%s", (aid,))
        if not row:
            return jsonify({"error": "账号不存在"}), 404
        with db.transaction() as conn:
            # 先把该账号 is_active=1（其它账号 is_active 不动，可同时保留多个"可用"账号，但只有 active_id 指向的才被发件 service 使用）
            db._exec(conn, "UPDATE email_account SET is_active=1, updated_at=%s WHERE id=%s", (_now(), aid))
            # 写 system_setting 指向当前激活
            db._exec(conn,
                "INSERT INTO system_setting (setting_key,setting_value,updated_at) VALUES ('email_active_account_id',%s,%s) "
                "ON DUPLICATE KEY UPDATE setting_value=VALUES(setting_value),updated_at=VALUES(updated_at)",
                (str(aid), _now()))
        return jsonify({"ok": True, "activeId": aid})

    @app.post("/api/email-accounts/<int:aid>/test")
    def api_email_accounts_test(aid):
        """测试连通：尝试 SMTP 登录，不实际发邮件。"""
        _require_admin()
        row = db._fetchone(db.get_conn(),
            "SELECT smtp_host,smtp_port,smtp_user,smtp_pass FROM email_account WHERE id=%s", (aid,))
        if not row:
            return jsonify({"error": "账号不存在"}), 404
        import smtplib
        try:
            with smtplib.SMTP_SSL(row["smtp_host"], int(row["smtp_port"]), timeout=15) as smtp:
                smtp.login(row["smtp_user"], row["smtp_pass"])
            return jsonify({"ok": True, "msg": "SMTP 登录成功"})
        except Exception as e:
            return jsonify({"ok": False, "error": str(e)[:300]}), 200
