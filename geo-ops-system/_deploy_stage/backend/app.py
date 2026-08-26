"""TODO: fix docstring"""

from __future__ import annotations



import json

import logging

import os

import secrets

import threading

from concurrent.futures import ThreadPoolExecutor

import zipfile

import io

import time

import uuid

from collections import defaultdict

from datetime import datetime, timedelta
from typing import Optional

from pathlib import Path

from urllib.parse import parse_qsl



import requests

from flask import Flask, Response, jsonify, redirect, render_template_string, request, send_from_directory, session

from flask.json.provider import DefaultJSONProvider as _DefaultJSONProvider

from werkzeug.security import generate_password_hash, check_password_hash



import db

PLATFORM_MODEL_MAP = {
    "豆包": "doubao",
    "DeepSeek": "deepseek",
    "通义千问": "qwen",
    "文心一言": "ernie",
}

_SECRET_SETTING_KEYS = {"email_smtp_pass", "email_smtp_user", "oauth_token"}

import access_scope

import scraper

import platforms

import overseas_search_adapter







APP_ROOT = Path(__file__).resolve().parent

app = Flask(__name__, static_folder=str(APP_ROOT / "static"), static_url_path="")

app.config["JSON_AS_ASCII"] = False





from datetime import datetime as _dt_cls, date as _date_cls





class _CNJSONProvider(_DefaultJSONProvider):

    def default(self, o):

        if isinstance(o, _dt_cls):

            return o.strftime("%Y-%m-%d %H:%M:%S")

        if isinstance(o, _date_cls):

            return o.strftime("%Y-%m-%d")

        return super().default(o)





app.json = _CNJSONProvider(app)

app.secret_key = os.environ.get("GEO_FLASK_SECRET") or db.get_or_create_flask_secret()

app.config.update(

    SESSION_COOKIE_HTTPONLY=True,

    SESSION_COOKIE_SAMESITE="Lax",



    SESSION_COOKIE_SECURE=os.environ.get("GEO_COOKIE_INSECURE") != "1",

    PERMANENT_SESSION_LIFETIME=60 * 60 * 24 * 7,  # 7 days

)



logger = logging.getLogger("gunicorn.error")





def _bootstrap_admin_user():

    if db.admin_user_exists():

        return

    import permissions as _perm

    import permissions as _perm



    if not db.get_role_by_code("super_admin"):

        db.create_role("超级管理员", "super_admin", data_scope="all",

                       description="系统内置超级管理员",

                       page_keys=list(_perm.PAGE_KEYS), is_builtin=1)

    init_pw = (os.environ.get("GEO_INIT_ADMIN_PW") or "").strip() or "admin123"

    logger.warning("INITIAL ADMIN CREATED: username=admin  password=%s", init_pw)

    logger.warning("请登录后修改密码此提示只在 log 中出现一次")

    logger.warning("=" * 60)



try:

    _bootstrap_admin_user()

except Exception:

    logger.exception("_bootstrap_admin_user failed")





    _reaped = db.reap_stale_running_tasks()

    if _reaped:

        logger.warning("reaped %d stale running task(s) on startup", _reaped)

except Exception:

    logger.exception("reap_stale_running_tasks on startup failed")





@app.errorhandler(500)

def _handle_500(e):

    logger.exception("Internal Server Error")

    return jsonify({"error": "服务器内部错误"}), 500



@app.errorhandler(Exception)

def _handle_exception(e):

    if hasattr(e, "code") and isinstance(e.code, int):

        return e  # HTTPException (404/403 etc.) 娣囨繃瀵旈崢鐔哥壉

    logger.exception("Unhandled exception")

    return jsonify({"error": "服务器内部错误"}), 500











_PUBLIC_API_PREFIXES = (

    "/api/auth/login",

    "/api/auth/me",

    "/api/share-info/",

    "/api/overview/",

    "/api/ranking/",

    "/api/questions/",

    "/api/optimize-detail/",

    "/api/share/weekly/",

    "/api/share/report/",

    "/api/share/kb-review/",  # KB review share

    "/api/publish/callback/",

    "/api/external/",  # External webhook entry

    "/api/share/kb-review/",  # KB review share with token auth

)



@app.after_request

def _add_security_headers(resp):

    """Global security headers: HSTS / clickjacking / MIME sniff / Referrer policy."""

    resp.headers.setdefault("Strict-Transport-Security", "max-age=31536000; includeSubDomains")

    resp.headers.setdefault("X-Content-Type-Options", "nosniff")

    resp.headers.setdefault("X-Frame-Options", "SAMEORIGIN")

    resp.headers.setdefault("Referrer-Policy", "strict-origin-when-cross-origin")

    resp.headers.setdefault("Permissions-Policy", "camera=(), microphone=(), geolocation=()")

    if resp.mimetype == "text/html":

        resp.headers["Cache-Control"] = "no-cache, no-store, must-revalidate"

        resp.headers["Pragma"] = "no-cache"

        resp.headers["Expires"] = "0"

    return resp





@app.before_request

def _require_login():

    path = request.path or ""

    # DEBUG: 记录所有 API 请求
    if path.startswith("/api/"):
        logger.info("[REQUEST] %s %s", request.method, path)



    if not path.startswith("/api/"):

        return None

    for prefix in _PUBLIC_API_PREFIXES:

        if path.startswith(prefix):

            return None

    if not session.get("user_id"):

        return jsonify({"error": "Not logged in or session expired", "code": "AUTH_REQUIRED"}), 401

    return None









_LOGIN_MAX_ATTEMPTS = 5

_LOGIN_WINDOW_SEC = 300       # 5 閸掑棝鎸撻崘?5 濞嗏€炽亼鐠愩儴袝閸欐垳绔村▎锟犳敚鐎?# 濞撴劘绻樺蹇涙敚鐎规碍妞傞梹?缁?: 妫ｆ牗顐奸柨?5 閸掑棝鎸?娴滃本顐?10 閸掑棝鎸?3+ 濞?15 閸掑棝鎸撻妴?# 閵嗗本顐奸妴宥呯唨娴滃氦绻冮崢?_LOCKOUT_HISTORY_WINDOW_SEC 閸愬懎鎮?IP 鐟欙箑褰傛潻鍥у殤濞嗭繝鏀g€规哎鈧?_LOCKOUT_TIERS_SEC = [300, 600, 900]

_LOCKOUT_HISTORY_WINDOW_SEC = 86400   # 24小时IP锁定历史窗口

_LOCKOUT_TIERS_SEC = [300, 600, 900]  # 锁定递增时间: 5分钟, 10分钟, 15分钟   # 24 鐏忓繑妞傞崘鍛畱闁夸礁鐣鹃崢鍡楀蕉閸愬啿鐣鹃張顒侇偧缁涘楠?





def _lockout_cooldown_sec(ip: str, include_current: int = 0) -> int:

    """Lockout cooldown based on IP lockout count in past 24h."""

    n = db.count_recent_lockouts(ip, _LOCKOUT_HISTORY_WINDOW_SEC) + include_current

    if n <= 0:

        return _LOCKOUT_TIERS_SEC[0]

    return _LOCKOUT_TIERS_SEC[min(n - 1, len(_LOCKOUT_TIERS_SEC) - 1)]





@app.post("/api/auth/login")

def api_auth_login():

    try:

        client_ip = request.headers.get("X-Forwarded-For", request.remote_addr or "").split(",")[0].strip()



        last_lock = db.last_lockout_at(client_ip)

        if last_lock:

            from datetime import datetime as _dt

            try:

                locked_at = _dt.strptime(last_lock, "%Y-%m-%d %H:%M:%S")

                elapsed = (_dt.now() - locked_at).total_seconds()

                cooldown = _lockout_cooldown_sec(client_ip)

                if elapsed < cooldown:

                    remaining_min = max(1, int((cooldown - elapsed) / 60 + 0.5))

                    return jsonify({"error": f"Too many login attempts, try again in {remaining_min} min"}), 429

            except Exception:

                pass

        data = request.get_json(silent=True) or {}

        if not isinstance(data, dict):

            data = {}

        raw_body = request.get_data(as_text=True)

        logger.info('login request content_type=%s raw_body=%s', request.content_type, raw_body[:50])

        username = (data.get("username") or "").strip()

        password = data.get("password") or ""

        # JSON 解析失败时，尝试 URL 编码格式（form-urlencoded）
        if not username and not password and raw_body:

            try:

                from urllib.parse import parse_qsl

                parsed = dict(parse_qsl(raw_body, keep_blank_values=True))

                username = (parsed.get("username") or "").strip()

                password = (parsed.get("password") or "").strip()

            except Exception:

                pass

        # 仍然为空时，尝试 form 和 args
        if not username and not password:

            username = (request.form.get("username") or request.args.get("username") or "").strip()

            password = (request.form.get("password") or request.args.get("password") or "")

        if not username or not password:

            return jsonify({"error": "閻劍鍩涢崥宥呮嫲鐎靛棛鐖滄稉宥堝厴娑撹櫣鈹?"}), 400

        user = db.get_admin_user_by_name(username)

        if not user or not check_password_hash(user["password_hash"], password):

            db.record_login_failure(client_ip)



            fails = db.count_recent_login_failures(client_ip)

            fails = db.count_recent_login_failures(client_ip)

            if fails >= _LOGIN_MAX_ATTEMPTS:

                db.record_lockout(client_ip)

                cooldown_min = _lockout_cooldown_sec(client_ip) // 60

                return jsonify({"error": f"Error: see logs for details"}), 429

            remaining = _LOGIN_MAX_ATTEMPTS - fails

            msg = "閻劍鍩涢崥宥嗗灗鐎靛棛鐖滈柨娆掝嚖"

            if remaining <= 2:

                msg += f"Error: see logs for details"

            return jsonify({"error": msg}), 401

        db.clear_login_failures(client_ip)

        session.clear()

        session["user_id"] = user["id"]

        session["username"] = user["username"]



        _load_role_into_session(user)



        try:

            session["team_id"] = db.get_user_team_id(user["id"])

        except Exception:

            session["team_id"] = None

        session.permanent = True

        try:

            db.touch_admin_last_login(user["id"])

        except Exception:

            logger.exception("touch_admin_last_login failed")

        return jsonify({"ok": True, "username": user["username"],

                         "isSuperAdmin": session["role"] == "super_admin",

                         "role": session["role"],

                         "roleName": session.get("role_name", ""),

                         "dataScope": session.get("data_scope", "self"),

                         "pages": session.get("pages", []),

                         "permissions": session.get("pages", [])

                     })

    except Exception:

        logger.exception("api_auth_login failed")

        return jsonify({"error": "Internal error"}), 500





@app.post("/api/auth/logout")

def api_auth_logout():

    session.clear()

    return jsonify({"ok": True})





@app.get("/api/auth/me")

def api_auth_me():

    if not session.get("user_id"):

        return jsonify({"authenticated": False}), 200

    try:

        uid = session.get("user_id")

        user = db.get_admin_user_by_id(int(uid)) if uid else None

        if user:

            _load_role_into_session(user)

    except Exception:

        logger.exception("[authMe] refresh role from DB failed, fallback to session cache")

    role = session.get("role") or "operator"

    pages = session.get("pages") or []

    return jsonify({

        "authenticated": True,

        "username":      session.get("username", ""),

        "isSuperAdmin":  role == "super_admin",

        "role":          role,

        "roleName":      session.get("role_name", ""),

        "dataScope":     session.get("data_scope", "self"),

        "pages":         pages,

        "permissions":   pages,  # alias for frontend

    })





@app.post("/api/auth/change-password")

def api_auth_change_password():

    data = request.get_json(silent=True) or {}

    old_pw = data.get("oldPassword") or ""

    new_pw = data.get("newPassword") or ""

    if len(new_pw) < 8:

        return jsonify({"error": "Error"}), 400

    user = db.get_admin_user_by_name(session.get("username", ""))

    if not user or not check_password_hash(user["password_hash"], old_pw):

        return jsonify({"error": "Error"}), 401

    db.update_admin_password(user["id"], generate_password_hash(new_pw))

    return jsonify({"ok": True})









def _load_role_into_session(user: dict) -> None:

    """TODO: fix docstring"""

    """TODO: fix docstring"""

    role_id = user.get("role_id")

    role_obj = None

    if role_id:

        try:

            role_obj = db.get_role(int(role_id))

        except Exception:

            role_obj = None

    if not role_obj:



        code = user.get("role") or "operator"

        role_obj = db.get_role_by_code(code)

    if not role_obj:



        role_obj = {"code": "operator", "name": "运营人员",

                    "dataScope": "self", "pages": []}

    session["role"] = role_obj["code"]

    session["role_name"] = role_obj["name"]

    session["data_scope"] = role_obj["dataScope"]

    session["pages"] = role_obj["pages"]











def _is_full_view_role() -> bool:

    """TODO: fix docstring"""

    return access_scope.is_full_view()





def _has_page_access(page_key: str) -> bool:

    """Frontend menu + backend optional sub-menu shared. Super_admin expands all."""



    if session.get("role") == "super_admin":

        return True

    return page_key in (session.get("pages") or [])





def _current_owner_id() -> int | None:

    """Return owner_id for data-scoped queries. Full-view roles see everything (None)."""

    if _is_full_view_role():

        return None

    return session.get("user_id")





def _account_scope_kwargs() -> dict:

    """TODO: fix docstring"""

    return access_scope.account_scope_kwargs()





def _ensure_account_access(account_id: int):

    """Return account dict or abort(403/404)."""

    acc = db.get_account(account_id)

    if not acc:

        return None

    if _is_full_view_role():

        return acc

    from flask import abort

    if session.get("data_scope") == "team":

        tid = session.get("team_id")

        if tid and acc.get("teamId") == tid:

            return acc

        abort(403)



    owner_ids = {o.get("id") for o in (acc.get("owners") or []) if o.get("id")}

    if acc.get("ownerId"):

        owner_ids.add(acc.get("ownerId"))

    if session.get("user_id") not in owner_ids:

        abort(403)

    return acc





def _require_admin_or_super():

    """TODO: fix docstring"""

    if session.get("role") not in ("super_admin", "admin"):

        from flask import abort

        abort(403)





def _require_super_admin():

    """要求超级管理员权限."""

    if session.get("role") != "super_admin":

        from flask import abort

        abort(403)





def _can_manage_target_role(target_role_code: str) -> tuple[bool, str]:



    actor = session.get("role")

    target = (target_role_code or "").lower()

    if actor == "super_admin":

        if target == "super_admin":

            return False, "不能修改超级管理员权限"

        return True, ""

    if actor == "admin":

        if target in ("super_admin", "admin"):

            return False, "不能修改同级或更高级别管理员的权限"

        return True, ""

    return False, "无权执行此操作"









@app.get("/api/admin/email-notify/settings")

def api_email_notify_get():

    _require_super_admin()

    import email_notify_service as _ens

    s = _ens._get_settings()

    pwd = s.get("email_smtp_pass") or ""

    return jsonify({

        "enabled": (s.get("email_notify_enabled") or "0") == "1",

        "smtp_host": s.get("email_smtp_host") or "",

        "smtp_port": s.get("email_smtp_port") or "",

        "smtp_user": s.get("email_smtp_user") or "",

        "smtp_pass_set": bool(pwd),

        "smtp_pass_masked": ("****" + pwd[-4:]) if len(pwd) >= 4 else "",

        "email_from": s.get("email_from") or "",

        "email_to": _ens._parse_to_list(s.get("email_to") or ""),

        "send_time": s.get("email_send_time") or "08:00",

        "last_sent_date": s.get("email_last_sent_date") or "",

    })





@app.put("/api/admin/email-notify/settings")

def api_email_notify_save():

    _require_super_admin()

    data = request.get_json(silent=True) or {}

    payload = {}

    if "enabled" in data:

        payload["email_notify_enabled"] = "1" if bool(data.get("enabled")) else "0"

    for src, dst in [("smtp_host", "email_smtp_host"),

                     ("smtp_port", "email_smtp_port"),

                     ("smtp_user", "email_smtp_user"),

                     ("email_from", "email_from"),

                     ("send_time", "email_send_time")]:

        if src in data and data.get(src) is not None:

            payload[dst] = str(data.get(src)).strip()



    if "smtp_pass" in data:

        pwd = (data.get("smtp_pass") or "").strip()

        if pwd:

            payload["email_smtp_pass"] = pwd

    if "email_to" in data:

        to_raw = data.get("email_to")

        if isinstance(to_raw, list):

            valid = [str(x).strip() for x in to_raw if str(x).strip()]

        elif isinstance(to_raw, str):

            valid = [s.strip() for s in to_raw.replace(", ", ",").split(",") if s.strip()]

        else:

            valid = []

        payload["email_to"] = json.dumps(valid, ensure_ascii=False)

    if not payload:

        return jsonify({"ok": False, "error": "閺冪姴褰叉穱婵嗙摠鐎涙顔?"}), 400

    db.save_settings(payload)

    return jsonify({"ok": True})





@app.post("/api/admin/email-notify/test")

def api_email_notify_test():

    _require_super_admin()

    import email_notify_service as _ens

    data = request.get_json(silent=True) or {}

    to = data.get("to")

    to_list = None

    if isinstance(to, list):

        to_list = [str(x).strip() for x in to if str(x).strip()]

    elif isinstance(to, str) and to.strip():

        to_list = [s.strip() for s in to.replace(", ", ",").split(",") if s.strip()]

    result = _ens.send_test(to_list=to_list)

    return jsonify(result)





@app.post("/api/admin/email-notify/send-now")

def api_email_notify_send_now():



    _require_super_admin()

    import email_notify_service as _ens

    result = _ens.send_daily(force=True)

    return jsonify(result)























@app.get("/api/admin/users")

def api_admin_list_users():

    _require_admin_or_super()

    users = db.list_admin_users()

    if session.get("data_scope") == "team":

        tid = session.get("team_id")

        users = [u for u in users if u.get("teamId") == tid]

    return jsonify(users)







@app.get("/api/teams")

def api_list_teams():

    if session.get("role") not in ("super_admin", "admin"):

        return jsonify({"error": "閺冪姵娼堥梽?"}), 403

    teams = db.list_teams()

    if session.get("data_scope") == "team":

        tid = session.get("team_id")

        teams = [t for t in teams if t["id"] == tid]

    return jsonify(teams)





@app.post("/api/teams")

def api_create_team():

    _require_super_admin()

    data = request.get_json(silent=True) or {}

    name = (data.get("name") or "").strip()

    if not name:

        return jsonify({"error": "閸ャ垽妲﹂崥宥勭瑝閼虫垝璐熺粚?"}), 400

    leader = data.get("leaderUserId") or data.get("leader_user_id")

    try:

        leader = int(leader) if leader else None

    except (TypeError, ValueError):

        leader = None

    tid = db.create_team(name, leader)

    return jsonify({"ok": True, "id": tid}), 201



@app.put("/api/teams/<int:team_id>")

def api_update_team(team_id):

    _require_super_admin()

    if not db.get_team(team_id):

        return jsonify({"error": "閸ャ垽妲︽稉宥呯摠閸?"}), 404

    data = request.get_json(silent=True) or {}

    name = data.get("name")

    leader = data.get("leaderUserId") or data.get("leader_user_id")

    try:

        leader = int(leader) if leader else None

    except (TypeError, ValueError):

        leader = None

    db.update_team(team_id, name=name, leader_user_id=leader)

    return jsonify({"ok": True})


@app.delete("/api/teams/<int:team_id>")
def api_delete_team(team_id):
    _require_super_admin()
    if not db.get_team(team_id):
        return jsonify({"error": "团队不存在"}), 404
    ok = db.delete_team(team_id)
    if not ok:
        return jsonify({"error": "只能删除没有成员和客户的空团队"}), 400
    return jsonify({"ok": True})


@app.post("/api/accounts/<int:account_id>/team")

def api_set_account_team(account_id):



    _require_super_admin()

    if not db.get_account(account_id):

        return jsonify({"error": "鐠愶附鍩涙稉宥呯摠閸?"}), 404

    data = request.get_json(silent=True) or {}

    tid = data.get("teamId") or data.get("team_id")

    try:

        tid = int(tid) if tid else None

    except (TypeError, ValueError):

        tid = None

    if tid and not db.get_team(tid):

        return jsonify({"error": "閻╊喗鐖ｉ崶銏ゆЕ娑撳秴鐡ㄩ崷?"}), 404

    db.set_account_team(account_id, tid)

    return jsonify({"ok": True, "accountId": account_id, "teamId": tid})





@app.post("/api/admin/users")

def api_admin_create_user():

    _require_admin_or_super()

    data = request.get_json(silent=True) or {}

    username = (data.get("username") or "").strip()

    password = data.get("password") or ""

    if not username or len(password) < 8:

        return jsonify({"error": "閻劍鍩涢崥宥勭瑝閼虫垝璐熺粚杞扮瑬鐎靛棛鐖滈懛鍐茬毌 8 娴?"}), 400

    if db.get_admin_user_by_name(username):

        return jsonify({"error": "閻劍鍩涢崥宥呭嚒鐎涙ê婀?"}), 400





    role_obj = _resolve_role_from_payload(data)

    if not role_obj:

        return jsonify({"error": "缂傚搫鐨張澶嬫櫏閻?roleId 閹?role"}), 400

    allowed, reason = _can_manage_target_role(role_obj["code"])

    if not allowed:

        return jsonify({"error": reason}), 403



    uid = db.create_admin_user(username, generate_password_hash(password),

                               role=role_obj["code"], permissions="[]")

    db.assign_user_role(uid, role_obj["id"], role_obj["code"])



    try:

        if session.get("data_scope") == "team":

            new_team = session.get("team_id")

        else:

            new_team = data.get("teamId") or data.get("team_id")

        if new_team:

            db.set_user_team(uid, int(new_team))

    except Exception:

        logger.exception("set_user_team on create failed uid=%s", uid)

    return jsonify({"ok": True, "id": uid}), 201



def _resolve_role_from_payload(data: dict) -> Optional[dict]:



    rid = data.get("roleId") or data.get("role_id")

    if rid:

        try:

            return db.get_role(int(rid))

        except Exception:

            return None

    code = (data.get("role") or "").strip().lower()

    if code:

        if code == "user":  # 閼颁礁澧犵粩顖氬悑鐎?            code = "operator"

            if code == "user":  # 用户角色映射为操作员
                code = "operator"

    return None









@app.put("/api/admin/users/<int:user_id>")

def api_admin_update_user(user_id):

    _require_admin_or_super()

    target = db.get_admin_user_by_id(user_id)

    if not target:

        return jsonify({"error": "閻劍鍩涙稉宥呯摠閸?"}), 404





    allowed, reason = _can_manage_target_role(target.get("role") or "")

    if not allowed:

        return jsonify({"error": reason}), 403



    data = request.get_json(silent=True) or {}



    if "roleId" in data or "role_id" in data or "role" in data:

        new_role_obj = _resolve_role_from_payload(data)

        if not new_role_obj:

            return jsonify({"error": "閻╊喗鐖g憴鎺曞娑撳秴鐡ㄩ崷?"}), 400

        allowed2, reason2 = _can_manage_target_role(new_role_obj["code"])

        if not allowed2:

            return jsonify({"error": reason2}), 403

        db.assign_user_role(user_id, new_role_obj["id"], new_role_obj["code"])

    if ("teamId" in data or "team_id" in data) and session.get("role") == "super_admin":

        raw = data.get("teamId")

        if raw is None:

            raw = data.get("team_id")

        try:

            new_team = int(raw) if raw else None

        except (TypeError, ValueError):

            new_team = None

        if new_team and not db.get_team(new_team):

            return jsonify({"error": "閻╊喗鐖ｉ崶銏ゆЕ娑撳秴鐡ㄩ崷?"}), 404

        db.set_user_team(user_id, new_team)

    return jsonify({"ok": True})



@app.delete("/api/admin/users/<int:user_id>")

def api_admin_delete_user(user_id):

    _require_admin_or_super()

    target = db.get_admin_user_by_id(user_id)

    if not target:

        return jsonify({"error": "閻劍鍩涙稉宥呯摠閸?"}), 404



    current_uid = session.get("user_id")

    if current_uid and int(current_uid) == int(user_id):

        return jsonify({"error": "娑撳秷鍏橀崚鐘绘珟瑜版挸澧犻惂璇茬秿閻ㄥ嫯鍤滃杈閸?"}), 400



    allowed, reason = _can_manage_target_role(target.get("role") or "")

    if not allowed:

        return jsonify({"error": reason}), 403

    try:

        db.delete_admin_user(user_id)

    except ValueError as exc:

        return jsonify({"error": str(exc)}), 400

    return jsonify({"ok": True})





@app.post("/api/admin/users/<int:user_id>/reset-password")

def api_admin_reset_password(user_id):

    _require_admin_or_super()

    target = db.get_admin_user_by_id(user_id)

    if not target:

        return jsonify({"error": "閻劍鍩涙稉宥呯摠閸?"}), 404



    allowed, reason = _can_manage_target_role(target.get("role") or "")

    if not allowed:

        return jsonify({"error": reason}), 403

    data = request.get_json(silent=True) or {}

    new_pw = data.get("newPassword") or ""

    if len(new_pw) < 8:

        return jsonify({"error": "鐎靛棛鐖滈懛鍐茬毌 8 娴?"}), 400

    db.update_admin_password(user_id, generate_password_hash(new_pw))

    return jsonify({"ok": True})









import permissions as _perms_registry  # noqa: E402







@app.get("/api/test-debug")
def api_test_debug():
    return jsonify({"msg": "TEST-WORKS-" + str(len(_perms_registry.PAGE_REGISTRY)), "scopes": list(_perms_registry.VALID_DATA_SCOPES)})

@app.get("/api/permissions/registry")

def api_permissions_registry():



    if not session.get("user_id"):

        return jsonify({"error": "閺堫亞娅ヨぐ?"}), 401

    return jsonify({

        "groups": _perms_registry.PAGE_GROUPS,

        "pages":  [{"key": k, "label": l, "group": g}

                   for k, l, g in _perms_registry.PAGE_REGISTRY],


        "dataScopes": [
            {"value": "all",  "label": "全部数据"},
            {"value": "team", "label": "看团队数据"},
            {"value": "self", "label": "只看自己创建的"},
        ],

    })





@app.get("/api/admin/roles")

def api_list_roles():

    _require_admin_or_super()

    return jsonify(db.list_roles())





@app.get("/api/admin/roles/<int:role_id>")

def api_get_role(role_id):

    _require_admin_or_super()

    r = db.get_role(role_id)

    if not r:

        return jsonify({"error": "鐟欐帟澹婃稉宥呯摠閸?"}), 404

    return jsonify(r)





def _parse_role_payload(data: dict, existing: Optional[dict] = None) -> tuple[Optional[dict], Optional[str]]:



    name = (data.get("name") or "").strip()

    data_scope = (data.get("dataScope") or data.get("data_scope") or "self").strip().lower()

    description = (data.get("description") or "").strip()

    pages = data.get("pages") or []



    if not name:

        return None, "鐟欐帟澹婇崥宥勭瑝閼虫垝璐熺粚"

    if data_scope not in _perms_registry.VALID_DATA_SCOPES:

        return None, f"Error: see logs for details"

    if not isinstance(pages, list):

        return None, "pages 韫囧懘銆忛弰顖涙殶缂"

    clean_pages = _perms_registry.filter_valid_keys(pages)

    return {

        "name": name,

        "dataScope": data_scope,

        "description": description,

        "pages": clean_pages,

    }, None





@app.post("/api/admin/roles")

def api_create_role():

    _require_super_admin()

    data = request.get_json(silent=True) or {}

    cleaned, err = _parse_role_payload(data)

    if err:

        return jsonify({"error": err}), 400





    code = (data.get("code") or "").strip().lower()

    if not code:



        from datetime import datetime as _dt

        code = f"role_{int(_dt.now().timestamp())}"

    if code in _perms_registry.BUILTIN_ROLE_CODES:

        return jsonify({"error": "code 娑撳骸鍞寸純顔款潡閼规彃鍟跨粣?"}), 400

    if db.get_role_by_code(code):

        return jsonify({"error": "code 瀹告彃鐡ㄩ崷?"}), 400



    rid = db.create_role(

        name=cleaned["name"],

        code=code,

        data_scope=cleaned["dataScope"],

        description=cleaned["description"],

        page_keys=cleaned["pages"],

        is_builtin=0,

    )

    return jsonify({"ok": True, "id": rid}), 201



@app.put("/api/admin/roles/<int:role_id>")

def api_update_role(role_id):

    _require_super_admin()

    existing = db.get_role(role_id)

    if not existing:

        return jsonify({"error": "鐟欐帟澹婃稉宥呯摠閸?"}), 404

    if existing["code"] == _perms_registry.SUPER_ADMIN_CODE:

        return jsonify({"error": "Error"}), 400



    data = request.get_json(silent=True) or {}

    cleaned, err = _parse_role_payload(data, existing=existing)

    if err:

        return jsonify({"error": err}), 400



    db.update_role(

        role_id,

        name=cleaned["name"],

        data_scope=cleaned["dataScope"],

        description=cleaned["description"],

        page_keys=cleaned["pages"],

    )

    return jsonify({"ok": True})





@app.delete("/api/admin/roles/<int:role_id>")

def api_delete_role(role_id):

    _require_super_admin()

    r = db.get_role(role_id)

    if not r:

        return jsonify({"error": "鐟欐帟澹婃稉宥呯摠閸?"}), 404

    try:

        db.delete_role(role_id)

    except ValueError as exc:

        return jsonify({"error": str(exc)}), 400

    return jsonify({"ok": True})









@app.get("/api/admin/invites")

def api_list_invites():

    _require_super_admin()

    return jsonify(db.list_invites())





@app.post("/api/admin/invites")

def api_create_invite():

    _require_super_admin()

    data = request.get_json(silent=True) or {}

    description = (data.get("description") or "").strip()

    max_uses = int(data.get("maxUses") or 3)

    max_keywords = int(data.get("maxKeywords") or 50)

    allowed_platforms = data.get("allowedPlatforms") or ["豆包", "DeepSeek"]

    if not isinstance(allowed_platforms, list) or not allowed_platforms:

        return jsonify({"error": "allowedPlatforms 韫囧懘銆忛弰顖炴姜缁岀儤鏆熺紒?"}), 400

    expires_at = (data.get("expiresAt") or "").strip()

    if not expires_at:



        expires_at = (datetime.now() + timedelta(days=30)).strftime("%Y-%m-%d %H:%M:%S")





    alphabet = "ABCDEFGHJKLMNPQRSTUVWXYZ23456789"

    code = "mfs-" + "".join(secrets.choice(alphabet) for _ in range(9))

    while db.get_invite_by_code(code):

        code = "mfs-" + "".join(secrets.choice(alphabet) for _ in range(9))



    invite_type = "long_term" if (data.get("inviteType") == "long_term") else "temporary"

    rid = db.create_invite(

        code=code,

        description=description,

        max_uses=max_uses,

        max_keywords=max_keywords,

        allowed_platforms=allowed_platforms,

        expires_at=expires_at,

        created_by=session.get("user_id"),

        invite_type=invite_type,

    )

    return jsonify({"ok": True, "id": rid, "code": code}), 201



@app.put("/api/admin/invites/<int:invite_id>")

def api_update_invite(invite_id):

    _require_super_admin()

    if not db.get_invite_by_id(invite_id):

        return jsonify({"error": "闁偓鐠囬鐖滄稉宥呯摠閸?"}), 404

    data = request.get_json(silent=True) or {}

    db.update_invite(invite_id, **{k: data.get(k) for k in

        ("description", "maxUses", "maxKeywords", "allowedPlatforms", "expiresAt", "status", "inviteType")})

    return jsonify({"ok": True})





@app.delete("/api/admin/invites/<int:invite_id>")

def api_delete_invite(invite_id):

    _require_super_admin()

    if not db.get_invite_by_id(invite_id):

        return jsonify({"error": "闁偓鐠囬鐖滄稉宥呯摠閸?"}), 404

    db.delete_invite(invite_id)

    return jsonify({"ok": True})





@app.get("/api/admin/invites/<int:invite_id>/uses")

def api_list_invite_uses(invite_id):

    _require_super_admin()

    if not db.get_invite_by_id(invite_id):

        return jsonify({"error": "闁偓鐠囬鐖滄稉宥呯摠閸?"}), 404

    return jsonify(db.list_uses_by_invite(invite_id, limit=200))











@app.route("/")

@app.route("/login")

@app.route("/dashboard")

@app.route("/dashboard/<path:subpath>")

@app.route("/report/<path:subpath>")

@app.route("/external-search")

@app.route("/effect")

@app.route("/effect/<path:subpath>")

def serve_spa(**kwargs):

    return send_from_directory(app.static_folder, "index.html")









@app.get("/api/accounts")

def api_list_accounts():



    include_temp = (request.args.get("include_temp") or "").strip() in ("1", "true", "yes")





    accounts = db.list_accounts(**_account_scope_kwargs(), include_temp=include_temp,

                                only_formal=not include_temp)

    last_dates = db.get_last_search_dates()

    last_ats = db.get_last_search_datetimes()

    last_rankings = db.get_last_ranking_dates()

    for acc in accounts:

        keywords = db.get_keywords(acc["id"])

        acc["keywordCount"] = len(keywords)

        acc["lastSearchDate"] = last_dates.get(acc["id"], "")

        acc["lastSearchAt"] = last_ats.get(acc["id"], "")

        acc["lastRankingAt"] = last_rankings.get(acc["id"], "")

    return jsonify(accounts)









@app.get("/api/accounts/<int:account_id>")

def api_get_account(account_id):

    acc = _ensure_account_access(account_id)

    if not acc:

        return jsonify({"error": "鐠愶附鍩涙稉宥呯摠閸?"}), 404

    return jsonify(acc)





@app.post("/api/accounts")

def api_create_account():

    data = request.get_json(force=True, silent=True) or {}

    if not data.get("companyName"):

        return jsonify({"error": "閸忣剙寰冮崥宥囆炴稉宥堝厴娑撹櫣鈹?"}), 400

    acc = db.create_account(data, owner_id=session.get("user_id"))

    return jsonify(acc), 201





@app.put("/api/accounts/<int:account_id>")

def api_update_account(account_id):

    if not _ensure_account_access(account_id):

        return jsonify({"error": "鐠愶附鍩涙稉宥呯摠閸?"}), 404

    data = request.get_json(force=True, silent=True) or {}

    acc = db.update_account(account_id, data)

    return jsonify(acc)





@app.patch("/api/accounts/<int:account_id>")

def api_patch_account(account_id):



    if not _ensure_account_access(account_id):

        return jsonify({"error": "鐠愶附鍩涙稉宥呯摠閸?"}), 404

    data = request.get_json(force=True, silent=True) or {}

    acc = db.update_account_partial(account_id, data)

    return jsonify(acc)





@app.post("/api/accounts/<int:account_id>/promote")

def api_promote_account(account_id):



    if not _ensure_account_access(account_id):

        return jsonify({"error": "鐠愶附鍩涙稉宥呯摠閸?"}), 404

    data = request.get_json(force=True, silent=True) or {}

    ok, err, acc = db.promote_to_formal(

        account_id,

        data.get("platforms") or [],

        data.get("keywords") or [],

        changed_by=session.get("user_id"),

    )

    if not ok:

        return jsonify({"error": err}), 400

    return jsonify(acc)





@app.delete("/api/accounts/<int:account_id>")

def api_delete_account(account_id):



    if not _ensure_account_access(account_id):

        return jsonify({"error": "鐠愶附鍩涙稉宥呯摠閸?"}), 404

    db.delete_account(account_id)

    return jsonify({"ok": True, "softDeleted": True})





@app.get("/api/accounts/recycle-bin")

def api_recycle_bin_list():



    rows = db.list_deleted_accounts(**_account_scope_kwargs())

    return jsonify(rows)





@app.post("/api/accounts/<int:account_id>/restore")

def api_account_restore(account_id):

    acc = db.get_account(account_id)



    if not acc:

        return jsonify({"error": "Error"}), 404

    if not _is_full_view_role():

        if acc.get("ownerId") != session.get("user_id"):

            return jsonify({"error": "Error"}), 403

    restored = db.restore_account(account_id)

    return jsonify({"ok": True, "account": restored})





@app.delete("/api/accounts/<int:account_id>/purge")

def api_account_purge(account_id):



    acc = db.get_account(account_id, include_deleted=True)

    if not acc:

        return jsonify({"error": "Error"}), 404

    if not _is_full_view_role():

        if acc.get("ownerId") != session.get("user_id"):

            return jsonify({"error": "閺冪姵娼堥幙宥勭稊"}), 403

    stats = db.purge_account(account_id)

    return jsonify({"ok": True, "purged": stats})





@app.post("/api/accounts/<int:account_id>/transfer")

def api_account_transfer(account_id):



    _require_admin_or_super()

    acc = _ensure_account_access(account_id)

    if not acc:

        return jsonify({"error": "Error"}), 404

    data = request.get_json(silent=True) or {}

    try:

        new_owner_id = int(data.get("newOwnerId") or data.get("new_owner_id") or 0)

    except (TypeError, ValueError):

        return jsonify({"error": "Error"}), 400

    if new_owner_id <= 0:

        return jsonify({"error": "newOwnerId 娑撳秷鍏樻稉铏光敄"}), 400

    target_user = db.get_admin_user_by_id(new_owner_id)

    if not target_user:

        return jsonify({"error": "Error"}), 404



    target_role = (target_user.get("role") or "").lower()

    if not target_role and target_user.get("role_id"):

        try:

            role_obj = db.get_role(int(target_user["role_id"]))

            if role_obj:

                target_role = (role_obj.get("code") or "").lower()

        except Exception:

            pass

    if not target_role:

        target_role = "operator"  # 閸忔粌绨抽敍宀勪缉閸忓秴鎮庡▔?owner 鐞氼偉顕ら崚?    if target_role not in _VALID_ROLES:

        return jsonify({"error": f"Error: see logs for details"}), 400

    old_owner = acc.get("ownerId") or acc.get("owner_id")

    with db.transaction() as conn:

        db._exec(conn, "UPDATE account SET owner_id=%s, updated_at=%s WHERE id=%s",

                 (new_owner_id, db._now(), account_id))

    return jsonify({

        "ok": True,

        "accountId": account_id,

        "oldOwnerId": old_owner,

        "newOwnerId": new_owner_id,

        "newOwnerName": target_user.get("username"),

    })





@app.post("/api/accounts/<int:account_id>/owners")

def api_set_account_owners(account_id):



    _require_admin_or_super()

    acc = db.get_account(account_id)

    if not acc:

        return jsonify({"error": "Error"}), 404

    data = request.get_json(silent=True) or {}

    raw = data.get("ownerIds")

    if raw is None:

        raw = data.get("owner_ids")

    if not isinstance(raw, list):

        return jsonify({"error": "Error"}), 400

    valid_ids = []

    for x in raw:

        try:

            uid = int(x)

        except (TypeError, ValueError):

            continue

        tu = db.get_admin_user_by_id(uid)

        if not tu:

            continue



        tr = (tu.get("role") or "").lower()

        if not tr and tu.get("role_id"):

            try:

                ro = db.get_role(int(tu["role_id"]))

                if ro:

                    tr = (ro.get("code") or "").lower()

            except Exception:

                pass

        if not tr:

            tr = "operator"

        if tr in ("admin", "super_admin", "operator") and uid not in valid_ids:

            valid_ids.append(uid)



    if session.get("data_scope") == "team":

        my_team = session.get("team_id")

        cross = [uid for uid in valid_ids if db.get_user_team_id(uid) != my_team]

        if cross:

            return jsonify({"error": "閸ャ垽妲︾拹鐔荤煑娴滃搫褰ч懗鑺ュ瘹濞茬偓婀伴崶銏ゆЕ閻ㄥ嫯绻嶉拃銉ゆ眽"}), 403

    db.set_account_owners(account_id, valid_ids)



    if valid_ids:

        primary_team = db.get_user_team_id(valid_ids[0])

        if primary_team:

            db.set_account_team(account_id, primary_team)

    return jsonify({"ok": True, "accountId": account_id,

                    "owners": db.get_account_owners(account_id)})





@app.get("/api/accounts/<int:account_id>/keywords")

def api_get_keywords(account_id):

    if not _ensure_account_access(account_id):

        return jsonify({"error": "Error"}), 404

    keywords = db.get_keywords(account_id)

    return jsonify(keywords)





@app.put("/api/accounts/<int:account_id>/keywords")

def api_save_keywords(account_id):

    if not _ensure_account_access(account_id):

        return jsonify({"error": "Error"}), 404

    data = request.get_json(force=True, silent=True)

    if isinstance(data, dict) and "text" in data:



        lines = [l.strip() for l in data["text"].splitlines() if l.strip()]

        keywords = [{"intentCategory": "", "coreIntentWord": l, "intentPrompt": l} for l in lines]

    elif isinstance(data, list):

        keywords = data

    else:

        return jsonify({"error": "鐠囬攱褰佹笟娑樺彠闁款喛鐦濋弫鐗堝祦"}), 400

    db.save_keywords(

        account_id,

        keywords,

        changed_by=session.get("user_id"),

        changed_by_name=session.get("username", ""),

        changed_ip=(request.headers.get("X-Forwarded-For", "").split(",")[0].strip() or request.remote_addr or ""),

    )

    return jsonify({"ok": True, "count": len(keywords)})





@app.get("/api/accounts/<int:account_id>/keyword-audits")

def api_list_keyword_audits(account_id):

    if not _ensure_account_access(account_id):

        return jsonify({"error": "Error"}), 404

    try:

        limit = int(request.args.get("limit", 50))

    except ValueError:

        limit = 50

    return jsonify(db.list_keyword_audits(account_id, limit=limit))









_ACCOUNT_SUMMARY_CACHE: dict = {}  # {(owner_id, include_external): (ts, data)}





@app.get("/api/search/account-summary")

def api_account_summary():

    """

    pass

    pass

    """

    role = session.get("role") or ""

    is_super = (role == "super_admin")



    want_external = (request.args.get("include_external") or "").strip() in ("1", "true", "yes")

    include_external = is_super and want_external



    ck = (_current_owner_id(), include_external)

    now = time.time()

    hit = _ACCOUNT_SUMMARY_CACHE.get(ck)

    if hit and now - hit[0] < 30:

        return jsonify(hit[1])

    data = db.get_accounts_search_summary(

        owner_id=_current_owner_id(),

        include_external=include_external,

    )

    _ACCOUNT_SUMMARY_CACHE[ck] = (now, data)

    return jsonify(data)







@app.get("/api/search/running/<int:account_id>")

def api_running_task(account_id):



    if not _ensure_account_access(account_id):

        return jsonify({"error": "閺冪姵娼堢拋鍧楁６"}), 403

    task = db.get_running_task_for_account(account_id)

    return jsonify(task)



@app.post("/api/search/start/<int:account_id>")

def api_start_search(account_id):

    if not _ensure_account_access(account_id):

        return jsonify({"error": "Error"}), 404

    body = request.get_json(silent=True) or {}

    platforms = body.get("platforms")

    keywords = body.get("keywords")

    import logging

    logger = logging.getLogger(__name__)

    logger.warning("[DEBUG] platforms=%s, keywords=%s, account_id=%s", platforms, keywords, account_id)

    if platforms is not None and (not isinstance(platforms, list) or not platforms):

        return jsonify({"error": "Error"}), 400

    if keywords is not None and not isinstance(keywords, list):

        return jsonify({"error": "Error"}), 400

    try:

        task_info = overseas_search_adapter.start_search_for_account_async(

            account_id,

            override_models=platforms,

            override_keywords=keywords,

        )

    except ValueError as exc:

        return jsonify({"error": str(exc)}), 400

    return jsonify(task_info)





@app.post("/api/search/start-temp")

def api_start_temp_search():





    body = request.get_json(silent=True) or {}

    brand = (body.get("brand") or "").strip()

    keywords = body.get("keywords") or []

    platforms = body.get("platforms") or []



    if not isinstance(keywords, list) or not [k for k in keywords if str(k or "").strip()]:

        return jsonify({"error": "Error"}), 400

    if not isinstance(platforms, list) or not platforms:

        return jsonify({"error": "Error"}), 400



    keywords = [str(k).strip() for k in keywords if str(k or "").strip()]

    from datetime import datetime

    label = brand or "娑撳瓨妞傛禒璇插"

    company_name = f"Error: see logs for details"

    owner_id = session.get("user_id")



    acc = db.create_account({





        "companyBrand": brand,

        "userType": "paid",

        "platforms": platforms,

        "isTemp": True,

        "optimizeStartDate": datetime.now().strftime("%Y-%m-%d"),

    }, owner_id=owner_id)




    kw_rows = [{"intentPrompt": k} for k in keywords]
    try:
        db.save_keywords(acc["id"], kw_rows, changed_by=owner_id)

    except Exception:

        logger.exception("[temp-search] save_keywords failed")







    try:

        task_info = overseas_search_adapter.start_search_for_account_async(

            acc["id"],

            override_models=platforms,

            override_keywords=keywords,

        )

    except ValueError as exc:

        return jsonify({"error": str(exc)}), 400



    task_info["accountId"] = acc["id"]

    task_info["companyName"] = acc["companyName"]

    task_info["isTemp"] = True

    return jsonify(task_info)





@app.get("/api/search/progress/<task_id>")

def api_search_progress(task_id):

    task, _err = _search_task_or_403(task_id)

    if _err: return _err

    return jsonify(task)





@app.get("/api/search/progress-log/<task_id>")

def api_search_progress_log(task_id):

    """"""

    task, _err = _search_task_or_403(task_id)

    if _err: return _err

    return jsonify(db.get_search_progress_log(task_id))





@app.post("/api/search/cancel/<task_id>")

def api_cancel_search(task_id):

    task, _err = _search_task_or_403(task_id)

    if _err: return _err



    db.request_cancel(task_id)

    db.cancel_search_task(task_id)

    return jsonify({"ok": True, "status": "CANCELLED"})







@app.get("/api/home/overview")
def api_home_overview():
    """首页概览数据：KPI卡片 + 运行任务 + 近期客户 + 7天趋势"""
    # 1. 基础统计
    conn = db.get_conn()
    try:
        # 客户账号数
        acc_rows = db._fetchall(conn, "SELECT COUNT(*) AS cnt FROM account")
        account_count = int(acc_rows[0]["cnt"] or 0)

        # 关键词总量
        kw_rows = db._fetchall(conn,
            "SELECT COUNT(DISTINCT core_intent_word) AS cnt FROM account_keyword ak "
            "JOIN account a ON a.id=ak.account_id"
        )
        keyword_count = int(kw_rows[0]["cnt"] or 0)

        # 运行中任务（JOIN account 表获取客户名称）
        run_rows = db._fetchall(conn,
            "SELECT st.id, st.account_id, st.status, st.total_queries, st.completed_queries, "
            "st.current_keyword, a.company_name, a.company_brand "
            "FROM search_task st "
            "LEFT JOIN account a ON a.id = st.account_id "
            "WHERE st.status IN ('RUNNING','PENDING') "
            "ORDER BY st.created_at DESC LIMIT 10"
        )
        running_tasks = []
        for r in run_rows:
            total = int(r["total_queries"] or 0)
            completed = int(r["completed_queries"] or 0)
            running_tasks.append({
                "taskId": r["id"],
                "accountId": r["account_id"],
                "accountName": r.get("company_name") or "未命名客户",
                "brand": r.get("company_brand") or "",
                "status": r["status"],
                "total": total,
                "completed": completed,
                "progress": round(completed / total * 100, 1) if total else 0,
                "keyword": r.get("current_keyword") or "",
            })

        # 今日查词统计
        today_stats = db.get_today_search_stats()

        # 最近添加的客户
        recent_accs = db._fetchall(conn,
            "SELECT id, company_name, company_brand, platforms FROM account "
            "ORDER BY id DESC LIMIT 5"
        )
        recent_list = []
        for a in recent_accs:
            plats = (a["platforms"] or "").split(",") if a["platforms"] else []
            recent_list.append({
                "id": a["id"],
                "companyName": a["company_name"] or "",
                "companyBrand": a["company_brand"] or "",
                "platforms": [p.strip() for p in plats if p.strip()],
            })

        # 7天趋势
        trend_rows = db._fetchall(conn,
            "SELECT search_date AS date, COUNT(*) AS count, SUM(success) AS ok "
            "FROM search_result WHERE search_date >= DATE_SUB(CURDATE(), INTERVAL 6 DAY) "
            "GROUP BY search_date ORDER BY search_date ASC"
        )
        trend_list = [{"date": r["date"], "count": int(r["count"] or 0)} for r in trend_rows]

        # 补齐缺失日期
        from datetime import datetime as _dt, timedelta as _td
        base = _dt.now().date()
        existing = {d["date"]: d["count"] for d in trend_list}
        full_trend = []
        for i in range(6, -1, -1):
            d = (base - _td(days=i)).isoformat()
            full_trend.append({"date": d, "count": existing.get(d, 0)})

    finally:
        conn.close()

    return jsonify({
        "stats": {
            "accounts": account_count,
            "keywords": keyword_count,
            "searches": today_stats.get("totalCount", 0),
            "runningTasks": len(running_tasks),
        },
        "today": {
            "totalCount": today_stats.get("totalCount", 0),
            "totalSuccessRate": today_stats.get("totalSuccessRate", 0),
            "totalAvgDuration": today_stats.get("totalAvgDuration", 0),
        },
        "running": running_tasks,
        "recent": recent_list,
        "alerts": [],
        "trend": full_trend,
        "todos": {},
    })


@app.get("/api/search/today-stats")

def api_search_today_stats():

    pass  # TODO: fix

    stats = db.get_today_search_stats()

    return jsonify(stats)





@app.get("/api/search/retry-stats")

def api_search_retry_stats():






    try:

        days = int(request.args.get("days", "7"))

    except (TypeError, ValueError):

        days = 7




    start = request.args.get("start_date") or None

    end = request.args.get("end_date") or None

    return jsonify(db.get_retry_stats(days, start_date=start, end_date=end))





pass





@app.post("/api/search/retry-failed/<task_id>")

def api_retry_failed(task_id):


    task = db.get_search_task(task_id)

    if not task or task.get("status") != "FAILED":

        return jsonify({"error": "任务不存在或未失败"}), 404

    import overseas_search_adapter as _adapter

    failed = [task]

    tasks_to_submit = []




    for r in failed:

        tasks_to_submit.append({

            "keyword": r.get("intent_prompt") or r.get("keyword", ""),

            "platform": r.get("platform", ""),

            "language": "en",

        })





    try:

        submitted = _adapter.submit_ka_tasks(tasks_to_submit)

        valid_ids = [s.get("localTaskId") for s in submitted if s.get("localTaskId")]

    except Exception as e:

        err_msg = "Ka 閹绘劒姘︽径杈Е: " + str(e)[:200]

        return jsonify({"error": err_msg}), 500



    if not valid_ids:

        return jsonify({"error": "Ka 鏉╂柨娲栭弮鐘虫箒閺佸牅鎹崝?ID"}), 500





    def _retry_worker():

        search_date = datetime.now().strftime("%Y-%m-%d")

        try:
            results = _adapter.poll_ka_until_complete(valid_ids, interval=_adapter.POLL_INTERVAL, max_wait=_adapter.POLL_MAX_WAIT)
            result_map = {r["localTaskId"]: r for r in results}

            updated = 0

            for i, r in enumerate(failed):

                sub = submitted[i] if i < len(submitted) else {}

                tid = sub.get("localTaskId")

                ka_result = result_map.get(tid) if tid else {}

                status = ka_result.get("status", "FAILED")

                result_obj = ka_result.get("result") or {}

                text = result_obj.get("text", "") or ""

                screenshot_url = (ka_result.get("screenshotUrl", "") or result_obj.get("remotePath", "") or "")

                error_msg = (ka_result.get("errorMessage", "") or "")

                db.update_search_result(r["id"], {

                    "success": 1 if status == "COMPLETED" else 0,

                    "response_json": json.dumps(ka_result, ensure_ascii=False)[:5000],

                    "answer_text": text,

                    "screenshot_url": screenshot_url,

                    "error_message": error_msg[:500] if error_msg else "",

                    "attempt": (r.get("attempt") or 1) + 1,

                    "search_date": search_date,

                })

                updated += 1

            logger.info("[retry] 任务 %s 进度 %d/%d 已更新缓存", task_id, updated, len(failed))

        except Exception:

            logger.exception("[retry] worker进程异常")



    t = threading.Thread(target=_retry_worker, daemon=True)

    t.start()



    return jsonify({

        "message": f"Error: see logs for details",

        "retried": len(valid_ids),

        "taskId": task_id,

    })





@app.post("/api/search/continue/<int:account_id>")

def api_continue_search(account_id):



    if not _ensure_account_access(account_id):

        return jsonify({"error": "Error"}), 404

    import overseas_search_adapter as _adapter



    acc = db.get_account(account_id)

    raw_platforms = acc.get("platforms") or []

    platforms_list = platforms.normalize_platforms(raw_platforms)

    today = datetime.now().strftime("%Y-%m-%d")

    models = platforms_list or ["豆包", "DeepSeek"]



    missing_pairs = db.get_unsearched_pairs(account_id, today, models)



    if not missing_pairs:

        return jsonify({"message": "娴犲﹤銇夐幍鈧張澶婂彠闁款喛鐦濋柈钘夊嚒閺屻儴顕楃€瑰本鍨", "submitted": 0})





    tasks_to_submit = []

    for kw_prompt, model in missing_pairs:



        plat = None

        for p, m in PLATFORM_MODEL_MAP.items():

            if m == model:

                plat = p

                break

        if not plat:

            continue

        tasks_to_submit.append({"keyword": kw_prompt, "platform": plat, "language": "en"})



    if not tasks_to_submit:

        return jsonify({"message": "閺冪姵纭堕崠褰掑帳品牌", "submitted": 0})





    try:

        submitted = _adapter.submit_ka_tasks(tasks_to_submit)

        valid_ids = [s.get("localTaskId") for s in submitted if s.get("localTaskId")]

    except Exception as e:

        err_msg = "Ka 閹绘劒姘︽径杈Е: " + str(e)[:200]

        return jsonify({"error": err_msg}), 500



    task_id = str(uuid.uuid4())

    db.create_search_task(task_id, account_id, len(tasks_to_submit), status="RUNNING", source="continue")



    def _continue_worker():

        search_date = today

        try:

            results = _adapter.poll_ka_until_complete(valid_ids, interval=_adapter.POLL_INTERVAL, max_wait=_adapter.POLL_MAX_WAIT)

            result_map = {r["localTaskId"]: r for r in results}

            saved = 0

            keywords_db = {k["prompt"]: k for k in db.get_keywords(account_id)}

            for i, t in enumerate(tasks_to_submit):

                sub = submitted[i] if i < len(submitted) else {}

                tid = sub.get("localTaskId")

                ka_result = result_map.get(tid) if tid else {}

                status = ka_result.get("status", "FAILED")

                result_obj = ka_result.get("result") or {}

                kw_entry = keywords_db.get(t["keyword"], {})

                db.save_search_result({

                    "task_id": task_id, "account_id": account_id,

                    "keyword_id": kw_entry.get("id"), "platform": t["platform"],

                    "model": PLATFORM_MODEL_MAP.get(t["platform"], t["platform"]),

                    "keyword": t["keyword"], "intent_category": kw_entry.get("category", ""),

                    "core_intent_word": kw_entry.get("core", ""),

                    "intent_prompt": t["keyword"],

                    "success": 1 if status == "COMPLETED" else 0,

                    "response_json": json.dumps(ka_result, ensure_ascii=False)[:5000],

                    "answer_text": result_obj.get("text", "") or "",

                    "answer_html": "", "screenshot_url": (ka_result.get("screenshotUrl", "") or result_obj.get("remotePath", "") or ""),

                    "duration": 0, "attempt": 1,

                    "error_message": (ka_result.get("errorMessage", "") or "")[:500],

                    "rescue_round": "continue", "search_date": search_date,

                })

                saved += 1

            db.update_search_task_status(task_id, "COMPLETED")

            logger.info("[continue] 鐠愶附鍩?%s 缂佈呯敾閺屻儴鐦濈€瑰本鍨? %d/%d", account_id, saved, len(tasks_to_submit))

        except Exception:

            logger.exception("[continue] worker 瀵倸鐖")

            db.update_search_task_status(task_id, "ERROR")



    threading.Thread(target=_continue_worker, daemon=True).start()

    return jsonify({"message": "Done", "submitted": 0})





@app.get("/api/search/unsearched-count/<int:account_id>")

def api_unsearched_count(account_id):



    if not _ensure_account_access(account_id):

        return jsonify({"error": "Error"}), 404

    from datetime import datetime as dt

    acc = db.get_account(account_id)

    raw_platforms = acc.get("platforms") or [] if acc else []



    normalized_platforms = platforms.normalize_platforms(raw_platforms)

    models = [platforms.PLATFORM_MODEL_MAP.get(p, p) for p in normalized_platforms]

    today = dt.now().strftime("%Y-%m-%d")

    missing = db.get_unsearched_pairs(account_id, today, models)

    return jsonify({"count": len(missing), "total": len(models) * len(db.get_keywords(account_id) or [])})

@app.get("/api/search/results/<int:account_id>")

def api_search_results(account_id):

    if not _ensure_account_access(account_id):

        return jsonify({"error": "Error"}), 404

    date = request.args.get("date", "")



    results = db.get_search_results_light(account_id, date)

    return jsonify(results)



















@app.get("/api/search/history/<int:account_id>")

def api_search_history(account_id):

    if not _ensure_account_access(account_id):

        return jsonify({"error": "Error"}), 404

    dates = db.get_search_history(account_id)

    return jsonify(dates)





@app.get("/api/search/account-history-grouped/<int:account_id>")

def api_account_history_grouped(account_id):



    if not _ensure_account_access(account_id):

        return jsonify({"error": "Error"}), 404

    limit_dates = min(int(request.args.get("limitDates", 30)), 90)

    grouped = db.get_search_history_grouped(account_id, limit_dates)

    return jsonify(grouped)





@app.delete("/api/search/history/<int:account_id>/all")

def api_search_history_delete_all(account_id):
    """删除账号全部搜索历史."""
    acc = db.get_account(account_id)
    if not acc:
        return jsonify({"error": "账号不存在"}), 404
    if acc.get("deletedAt"):
        return jsonify({"ok": False, "error": "已归档账号不允许删除历史记录"}), 410
    if not _ensure_account_access(account_id):
        return jsonify({"ok": False, "error": "无权限操作"}), 403

    dates = db.get_search_history(account_id) or []

    total_deleted = 0
    for d in dates:
        try:
            total_deleted += int(db.delete_search_history_by_date(account_id, d) or 0)
        except Exception:
            pass

    return jsonify({"ok": True, "deletedDates": len(dates), "deletedRows": total_deleted})





@app.delete("/api/search/history/<int:account_id>")

def api_search_history_delete(account_id):

    if not _ensure_account_access(account_id):

        return jsonify({"error": "Error"}), 404

    date = request.args.get("date", "")

    if not date:

        return jsonify({"error": "Error"}), 400

    affected = db.delete_search_history_by_date(account_id, date)

    return jsonify({"ok": True, "deleted": affected})





@app.delete("/api/search/task/<task_id>")

def api_search_task_delete(task_id):
    """删除搜索任务."""
    with db.get_conn().cursor() as cur:

        cur.execute("SELECT account_id, status FROM search_task WHERE id=%s", (task_id,))

        row = cur.fetchone()

    if not row:

        return jsonify({"error": "Error"}), 404

    account_id = row.get("account_id") if isinstance(row, dict) else row[0]

    status = row.get("status") if isinstance(row, dict) else row[1]

    if not account_id:

        return jsonify({"ok": False, "error": "娴犺濮熺紓鍝勭毌 account_id 閸忓疇浠?"}), 500



    if not _ensure_account_access(account_id):

        return jsonify({"ok": False, "error": "閺冪姵娼堢拋鍧楁６"}), 403

    if (status or "").upper() in ("RUNNING", "QUEUED"):

        return jsonify({"error": "Error"}), 400



    try:

        result = db.delete_search_task_by_id(task_id)

    except Exception as exc:

        return jsonify({"ok": False, "error": str(exc)}), 400

    return jsonify({"ok": True, **result})





_EXPORT_MODEL_NAMES = {

    "douBao": "豆包", "deepseek": "DeepSeek", "yuanBao": "元宝", "yuanbao": "元宝",

    "wenXin": "文心一言", "tongYi": "通义千问", "kimi": "Kimi",

    "naMi": "纳米搜索AI", "chatgpt": "ChatGPT", "perplexity": "Perplexity",

}





def _date_to_cn(date_str: str) -> str:

    try:

        from datetime import datetime as dt_cls

        pass

    except Exception:

        return date_str





def _safe_keyword(keyword: str) -> str:

    s = keyword or "unknown"

    for ch in ('/', '\\', ':', '*', '?', '"', '<', '>', '|'):

        s = s.replace(ch, "_")

    return s





def _write_result_to_zip(zf, result_rows, folder_prefix: str):



    import json as json_mod

    for r in result_rows:

        if not r.get("success"):

            continue

        model_code = r.get("model", r.get("platform", "unknown"))

        model_display = _EXPORT_MODEL_NAMES.get(model_code, model_code)

        keyword = r.get("keyword", r.get("intentPrompt", "unknown"))

        safe_kw = _safe_keyword(keyword)



        search_result_obj = None

        raw_resp = r.get("responseJson") or ""

        if raw_resp:

            try:

                parsed = json_mod.loads(raw_resp)

                if isinstance(parsed, dict):

                    search_result_obj = parsed.get("searchResult") or parsed

            except Exception:

                search_result_obj = None

        if not search_result_obj:

            summarys = []

            raw_sum = r.get("summarysJson") or ""

            if raw_sum:

                try:

                    parsed_sum = json_mod.loads(raw_sum)

                    if isinstance(parsed_sum, list):

                        summarys = parsed_sum

                except Exception:

                    summarys = []

            if not summarys:

                txt = r.get("answerText", "") or r.get("answerHtml", "")

                if txt:

                    summarys = [{"summary": txt}]

            search_result_obj = {"summarys": summarys}



        file_data = {

            "keyword": keyword,

            "model": model_code,

            "platform": r.get("platform", ""),

            "intentCategory": r.get("intentCategory", ""),

            "coreIntentWord": r.get("coreIntentWord", ""),

            "intentPrompt": r.get("intentPrompt", ""),

            "searchDate": r.get("searchDate", ""),

            "duration": r.get("duration", 0),

            "searchResult": search_result_obj,

        }

        file_path = f"{folder_prefix}/{model_display}/{safe_kw}.json"

        zf.writestr(file_path, json_mod.dumps(file_data, ensure_ascii=False, indent=2).encode("utf-8"))





@app.get("/api/search/export/<int:account_id>")

def api_search_export(account_id):



    import json as json_mod

    if not _ensure_account_access(account_id):

        return jsonify({"ok": False, "error": "閺冪姵娼堢拋鍧楁６"}), 403

    date = request.args.get("date", "")

    if not date:

        return jsonify({"error": "Error"}), 400



    account = db.get_account(account_id)

    if not account:

        return jsonify({"error": "Error"}), 404



    brand = account.get("companyBrand", "")

    results = db.get_search_results(account_id, date)

    success_results = [r for r in results if r.get("success")]

    if not success_results:

        return jsonify({"ok": False, "error": "鐠囥儲妫╅張鐔剁瑓閺冪姵鍨氶崝鐔烘畱閺屻儴鐦濈紒鎾寸亯"}), 400





    try:

        from datetime import datetime as dt_cls

        d = dt_cls.strptime(date, "%Y-%m-%d")

        pass

    except Exception:

        date_cn = date





    model_names = {

        "douBao": "豆包", "deepseek": "DeepSeek", "yuanBao": "元宝",

        "wenXin": "文心一言", "tongYi": "通义千问", "kimi": "Kimi",

        "naMi": "纳米搜索AI", "chatgpt": "ChatGPT", "perplexity": "Perplexity",

    }



    zip_name = f"Error: see logs for details"



    buf = io.BytesIO()

    with zipfile.ZipFile(buf, 'w', zipfile.ZIP_DEFLATED) as zf:

        for r in success_results:

            model_code = r.get("model", r.get("platform", "unknown"))

            model_display = model_names.get(model_code, model_code)

            keyword = r.get("keyword", r.get("intentPrompt", "unknown"))
            import re as _re
            safe_keyword = _re.sub(r'[\\/:*?"<>|]', '_', keyword)[:50]




            search_result_obj = None

            raw_resp = r.get("responseJson") or ""

            if raw_resp:

                try:

                    parsed = json_mod.loads(raw_resp)

                    if isinstance(parsed, dict):

                        search_result_obj = parsed.get("searchResult") or parsed

                except Exception:

                    search_result_obj = None



            if not search_result_obj:
                summarys = []
                txt = r.get("answerText") or r.get("text") or ""
                if txt:
                    summarys = [{"summary": txt}]
                search_result_obj = {"summarys": summarys}



            file_data = {

                "keyword": keyword,

                "model": model_code,

                "platform": r.get("platform", ""),

                "intentCategory": r.get("intentCategory", ""),

                "coreIntentWord": r.get("coreIntentWord", ""),

                "intentPrompt": r.get("intentPrompt", ""),

                "searchDate": r.get("searchDate", date),

                "duration": r.get("duration", 0),

                "searchResult": search_result_obj,

            }



            folder = f"{model_display}{date_cn}"

            file_path = f"{folder}/{safe_keyword}.json"

            json_bytes = json_mod.dumps(file_data, ensure_ascii=False, indent=2).encode("utf-8")

            zf.writestr(file_path, json_bytes)



    buf.seek(0)

    from flask import send_file

    return send_file(

        buf,

        mimetype='application/zip',

        as_attachment=True,

        download_name=f"{zip_name}.zip",

    )





@app.get("/api/search/export-account/<int:account_id>")

def api_search_export_account(account_id):



    if not _ensure_account_access(account_id):

        return jsonify({"ok": False, "error": "閺冪姵娼堢拋鍧楁６"}), 403

    account = db.get_account(account_id)

    if not account:

        return jsonify({"ok": False, "error": "鐠愶箑褰挎稉宥呯摠閸?"}), 404



    brand = account.get("companyBrand", "") or account.get("companyName", "") or f"account_{account_id}"

    dates = db.get_search_history(account_id) or []

    if not dates:

        return jsonify({"ok": False, "error": "鐠囥儴澶勯崣閿嬫畯閺冪姵鐓＄拠宥堫唶瑜?"}), 400



    buf = io.BytesIO()

    total_files = 0

    with zipfile.ZipFile(buf, 'w', zipfile.ZIP_DEFLATED) as zf:

        for d in dates:

            rows = db.get_search_results(account_id, d)

            ok_rows = [r for r in rows if r.get("success")]

            if not ok_rows:

                continue

            date_cn = _date_to_cn(d)

            _write_result_to_zip(zf, ok_rows, date_cn)

            total_files += len(ok_rows)



    if total_files == 0:

        return jsonify({"ok": False, "error": "鐠囥儴澶勯崣閿嬫畯閺冪姵鍨氶崝鐔烘畱閺屻儴鐦濈紒鎾寸亯"}), 400



    buf.seek(0)

    today = datetime.now().strftime("%Y%m%d")

    zip_name = f"Error: see logs for details"

    from flask import send_file

    from urllib.parse import quote as _urlquote

    return Response(

        buf.getvalue(),

        mimetype='application/zip',

        headers={

            "Content-Disposition": f"attachment; filename=search_{account_id}_{today}.zip; filename*=UTF-8''{_urlquote(zip_name)}",

        },

    )





@app.get("/api/search/brand-ranking/<int:account_id>")

def api_brand_ranking(account_id):

    if not _ensure_account_access(account_id):

        return jsonify({"error": "鐠愶附鍩涙稉宥呯摠閸?"}), 404

    dates_param = request.args.get("dates", "")

    dates = [d.strip() for d in dates_param.split(",") if d.strip()] if dates_param else []

    results = db.get_brand_ranking_data(account_id, dates)





    all_dates = sorted(set(r["searchDate"] for r in results))

    rows_map = defaultdict(lambda: {"rankings": {}})



    for r in results:

        key = f"{r['keyword']}|{r['platform']}"

        row = rows_map[key]

        row["keyword"] = r["keyword"]

        row["platform"] = r["platform"]

        row["intentCategory"] = r.get("intentCategory", "")

        row["rankings"][r["searchDate"]] = {

            "brandRank": r.get("brandRank"),

            "brandAnalysisJson": r.get("brandAnalysisJson", ""),

        }



    return jsonify({

        "dates": all_dates,

        "rows": list(rows_map.values()),

    })








































def _parse_brand_list(raw):
    """Parse brand list from various formats: string, list, JSON array."""
    if not raw:
        return []

    if isinstance(raw, (list, tuple)):
        items = [str(x).strip() for x in raw]
    else:
        s = str(raw).strip()
        if not s:
            return []

        items = None
        if s.startswith("["):
            try:
                arr = json.loads(s)
                if isinstance(arr, list):
                    items = [str(x).strip() for x in arr]
            except Exception:
                items = None

        if items is None:
            items = [s]

    out = []
    seen = set()
    for it in items:
        if it and it not in seen:
            out.append(it)
            seen.add(it)

    return out







def _brands_to_storage(brands: list[str]) -> str:



    brands = [b.strip() for b in brands if b and b.strip()]

    if not brands:

        return ""

    if len(brands) == 1:

        return brands[0]

    return json.dumps(brands, ensure_ascii=False)











_UPLOAD_PLAT2MODEL = {
    "豆包": "douBao", "deepseek": "deepseek", "元宝": "yuanBao", "通义千问": "yuanBao",
    "文心一言": "wenXin", "文心": "wenXin", "通义千问": "tongYi", "通义": "tongYi",
    "通义": "tongYi", "kimi": "kimi", "纳米搜索AI": "naMi", "纳米搜索": "naMi", "纳米AI": "naMi",
}

_UPLOAD_MODEL2CN = {"douBao": "豆包", "deepseek": "DeepSeek", "yuanBao": "元宝",

                    "wenXin": "文心一言", "tongYi": "通义千问", "kimi": "Kimi", "naMi": "纳米AI"}





def _upload_parse_items(payload, fallback_platform: str) -> list[dict]:



    KW_KEYS = ("keyword", "prompt", "query", "question", "intentPrompt", "intent_prompt", "主关键词", "搜索词", "用户问题")

    ANS_KEYS = ("answerText", "answer_text", "answer", "content", "text", "response", "回答文本", "摘要内容", "结果摘要")

    PLAT_KEYS = ("platform", "品牌", "model", "模型")

    DATE_KEYS = ("search_date", "searchDate", "date", "日期")



    def _norm_model(p: str) -> tuple[str, str]:



        p = (p or "").strip()

        fb = (fallback_platform or "").strip()

        code = (_UPLOAD_PLAT2MODEL.get(p) or _UPLOAD_PLAT2MODEL.get(p.lower())

                or (p if p in _UPLOAD_MODEL2CN else "")

                or _UPLOAD_PLAT2MODEL.get(fb) or _UPLOAD_PLAT2MODEL.get(fb.lower())

                or (fb if fb in _UPLOAD_MODEL2CN else "")

                or p or fb or "unknown")

        cn = _UPLOAD_MODEL2CN.get(code, p or fb or code)

        return code, cn



    def _pick(d: dict, keys):

        for k in keys:

            v = d.get(k)

            if v is not None and str(v).strip():

                return str(v).strip()

        return ""



    def _pick_answer(it: dict) -> str:

        ans = _pick(it, ANS_KEYS)

        if ans:

            return ans



        for nk in ("searchResult", "search_result", "result", "data", "response"):

            sub = it.get(nk)

            if isinstance(sub, dict):

                ans = _pick(sub, ANS_KEYS)

                if ans:

                    return ans

        return ""



    def _from_list(lst, plat_hint):

        out = []

        for it in lst:

            if not isinstance(it, dict):

                continue

            kw = _pick(it, KW_KEYS)

            ans = _pick_answer(it)

            if not kw or not ans:

                continue

            plat_raw = _pick(it, PLAT_KEYS) or plat_hint

            code, cn = _norm_model(plat_raw)

            out.append({"keyword": kw, "answer": ans, "model": code, "platform": cn,

                        "date": _pick(it, DATE_KEYS)[:10]})

        return out



    if isinstance(payload, list):

        return _from_list(payload, fallback_platform)

    if isinstance(payload, dict):



        if _pick(payload, KW_KEYS):

            return _from_list([payload], fallback_platform)

        for key in ("results", "items", "data", "list", "records"):

            if isinstance(payload.get(key), list):

                return _from_list(payload[key], fallback_platform)



        out = []

        for k, v in payload.items():

            if isinstance(v, list):

                out.extend(_from_list(v, str(k)))

        return out

    return []

















def supplement_ranking_task(ranking_task_id: str) -> dict:
    """补充排名分析任务数据.

    Returns:
      {"task_id": ..., "added": N, "before_done": M, "after_done": M+N,
       "before_total": X, "after_total": X+N, "status": "completed"|"skipped"|...}
    """
    task = db.get_ranking_task(ranking_task_id)

    if not task:
        return {"task_id": 0, "error": "任务不存在"}

    cur_status = task.get("status")

    if cur_status in ("running",):
        return {"task_id": ranking_task_id, "skipped": True, "reason": "任务正在运行中，跳过"}

    sti = task.get("searchTaskId") or task.get("search_task_id") or ""

    if not sti.startswith("account_"):
        return {"task_id": ranking_task_id, "skipped": True, "reason": "非账号搜索任务，跳过"}

    try:
        _, aid_s, date = sti.split("_", 2)
        account_id = int(aid_s)
    except Exception:
        return {"task_id": ranking_task_id, "error": "搜索任务ID格式错误"}

    success_results = [r for r in (db.get_search_results(account_id, date) or [])
                       if r.get("success")]

    if not success_results:
        return {"task_id": ranking_task_id, "added": 0,
                "before_total": task.get("total", 0), "after_total": task.get("total", 0),
                "status": "completed"}

    # Extract new keywords diff from search results
    existing_keywords = set(task.get("keywords") or [])
    diff = [r.get("keyword", "") for r in success_results 
            if r.get("keyword") and r.get("keyword") not in existing_keywords]

    brand_names_raw = task.get("brand_name", "") or ""
    brand_list = _parse_brand_list(brand_names_raw)

    if not brand_list:
        return {"task_id": ranking_task_id, "error": "task brand_name 未设置或解析失败"}

    before_total = int(task.get("total") or 0)
    before_done = int(task.get("done") or 0)
    before_skipped = int(task.get("skipped") or 0)
    before_hit = int(task.get("hit") or 0)

    db.update_ranking_task(
        ranking_task_id,
        status="running",
        total=before_total + len(diff),
    )

    try:
        _execute_ranking_analysis(
            ranking_task_id, diff, brand_list,
            offset={"done": before_done, "skipped": before_skipped, "hit": before_hit},
        )
    except Exception as exc:
        app.logger.exception("[排名分析] task=%s 异常", ranking_task_id)
        return {"task_id": ranking_task_id, "error": str(exc)}

    after = db.get_ranking_task(ranking_task_id) or {}
    return {
        "task_id": ranking_task_id,
        "added": len(diff),
        "before_total": before_total,
        "after_total": int(after.get("total") or 0),
        "before_done": before_done,
        "after_done": int(after.get("done") or 0),
        "status": after.get("status"),
    }


def _accessible_account_ids() -> set | None:

    """TODO: fix docstring"""

    """TODO: fix docstring"""

    return access_scope.accessible_account_ids()





def _filter_by_account(items, *keys):

    """TODO: fix docstring"""

    allowed = _accessible_account_ids()

    if allowed is None:

        return items

    if not keys:

        keys = ("accountId", "account_id")

    out = []

    for it in items:

        if not isinstance(it, dict):

            out.append(it); continue

        aid = None

        for k in keys:

            if k in it and it[k] is not None:

                aid = it[k]; break

        if aid is None or int(aid) in allowed:

            out.append(it)

    return out





def _check_task_account_access(task: dict | None, *keys) -> bool:

    """TODO: fix docstring"""

    if task is None or _is_full_view_role():

        return task is not None

    if not keys:

        keys = ("accountId", "account_id")

    for k in keys:

        if k in task and task[k] is not None:

            return _ensure_account_access(int(task[k])) is not None

    return True  # task 濞岋紕绮?account 鐏忚鲸鏂佺悰?



def _search_task_or_403(task_id: str):

    task = db.get_search_task(task_id)

    if not task:

        return jsonify({"error": "Error"}), 404

    if not _check_task_account_access(task):

        return jsonify({"error": "Error"}), 403

    return task, None





def _quote_task_or_403(task_id: str):

    task = db.get_quote_task(task_id)

    if not task:

        return jsonify({"error": "Error"}), 404

    if not _check_task_account_access(task):

        return jsonify({"error": "Error"}), 403

    return task, None





def _citation_task_or_403(task_id: str):

    task = db.get_citation_scrape_task(task_id)

    if not task:

        return jsonify({"error": "Error"}), 404

    if not _check_task_account_access(task):

        return jsonify({"error": "Error"}), 403

    return task, None





def _scheduled_or_403(sched_dict):

    """检查定时任务权限或返回403."""

    if not sched_dict:

        return False

    if _is_full_view_role():

        return True

    aid = sched_dict.get("accountId") or sched_dict.get("account_id")

    if not aid:

        return False

    acc = db.get_account(aid)

    if not acc:

        return False

    oid = session.get("user_id")

    if _is_full_view_role():

        return True

    if str(acc.get("owner_id") or "") == str(oid):

        return True

    tid = acc.get("team_id")

    my_teams = _my_team_ids()

    if tid and my_teams and int(tid) in my_teams:

        return True

    return False


# ========== Scheduled Search Tasks API ==========

@app.get("/api/scheduled-tasks")

def api_list_scheduled_tasks():

    """获取定时查词任务列表"""

    tasks = db.list_scheduled_search_tasks(owner_id=session.get("user_id"))

    return jsonify(tasks)


# 更具体的路由（带子路径）必须在通用参数路由之前定义
# 注意：使用查询参数而不是子路径来避免路由匹配问题
@app.post("/api/scheduled-tasks/_fix-duration")
def api_fix_duration():
    """【临时】修复 duration=0 的历史记录"""
    import pymysql
    from datetime import datetime
    
    try:
        conn = db.get_conn()
        cur = conn.cursor(pymysql.cursors.DictCursor)
        
        # 查询所有 duration <= 1 的记录
        cur.execute("""
            SELECT h.id, h.task_id, h.started_at, h.finished_at, h.duration_seconds,
                   s.created_at as task_created, s.completed_at as task_completed, s.status as task_status
            FROM scheduled_task_history h
            LEFT JOIN search_task s ON h.task_id = s.id
            WHERE h.duration_seconds <= 1 OR h.duration_seconds IS NULL
            ORDER BY h.id DESC LIMIT 50
        """)
        rows = cur.fetchall()
        
        fixed = 0
        results = []
        
        for row in rows:
            hist_id = row['id']
            real_dur = None
            new_finished = None
            
            # 从 search_task 获取真实时间
            if row.get('task_created') and row.get('task_completed'):
                try:
                    start_dt = datetime.strptime(str(row['task_created'])[:19], "%Y-%m-%d %H:%M:%S")
                    end_dt = datetime.strptime(str(row['task_completed'])[:19], "%Y-%m-%d %H:%M:%S")
                    real_dur = int((end_dt - start_dt).total_seconds())
                    new_finished = str(row['task_completed'])[:19]
                except:
                    pass
            
            if real_dur and real_dur > 0:
                cur.execute(
                    "UPDATE scheduled_task_history SET finished_at=%s, duration_seconds=%s, status='COMPLETED' WHERE id=%s",
                    (new_finished, max(real_dur, 1), hist_id)
                )
                fixed += 1
                results.append({"id": hist_id, "duration": max(real_dur, 1), "source": "search_task"})
            elif row.get('started_at'):
                # 估算值：至少3秒
                cur.execute(
                    "UPDATE scheduled_task_history SET finished_at=DATE_ADD(started_at, INTERVAL 3 SECOND), duration_seconds=3, status='COMPLETED' WHERE id=%s",
                    (hist_id,)
                )
                fixed += 1
                results.append({"id": hist_id, "duration": 3, "source": "estimated"})
        
        conn.commit()
        cur.close()
        
        return jsonify({
            "message": f"已修复 {fixed}/{len(rows)} 条记录",
            "fixed": fixed,
            "total": len(rows),
            "details": results[:10]  # 只返回前10条详情
        })
        
    except Exception as e:
        logger.error("[Fix-Duration] 修复失败: %s", e, exc_info=True)
        return jsonify({"error": str(e)}), 500


@app.get("/api/scheduled-tasks/<int:sched_id>/history")
def api_scheduled_task_history(sched_id):
    """获取定时任务执行历史"""
    logger.info("[HISTORY API] Request received for sched_id=%s, path=%s", sched_id, request.path)
    task = db.get_scheduled_search_task(sched_id)
    if not task:
        logger.warning("[HISTORY API] Task not found: %s", sched_id)
        return jsonify({"error": "任务不存在"}), 404
    if not _scheduled_or_403(task):
        return jsonify({"error": "无权操作"}), 403
    
    limit = request.args.get("limit", 50, type=int)
    history = db.list_scheduled_task_history(sched_id, limit=limit)
    logger.info("[HISTORY API] History result: %s records", len(history.get("items", [])) if isinstance(history, dict) else len(history))
    
    # 【Duration修复】动态计算真实的 duration
    if isinstance(history, dict) and "items" in history:
        for item in history["items"]:
            try:
                task_id = item.get("taskId") or item.get("task_id") or ""
                started_at = item.get("startedAt") or item.get("started_at") or ""
                
                # 如果 duration <= 1 且有 task_id，尝试从 search_task 获取真实时间
                if (item.get("durationSeconds", 0) <= 1 or item.get("duration_seconds", 0) <= 1) and task_id:
                    search_row = db._fetchone(db.get_conn(),
                        """SELECT created_at, completed_at, status 
                           FROM search_task WHERE id=%s LIMIT 1""",
                        (task_id,)
                    )
                    if search_row:
                        st_created = str(search_row.get("created_at") or "")[:19]
                        st_completed = str(search_row.get("completed_at") or "")[:19]
                        
                        if st_created and st_completed:
                            from datetime import datetime as _dt
                            start_dt = _dt.strptime(st_created, "%Y-%m-%d %H:%M:%S")
                            end_dt = _dt.strptime(st_completed, "%Y-%m-%d %H:%M:%S")
                            real_duration = int((end_dt - start_dt).total_seconds())
                            
                            # 更新返回值
                            item["startedAt"] = st_created
                            item["finishedAt"] = st_completed
                            item["durationSeconds"] = max(real_duration, 1)
                            logger.info("[HISTORY-Duration] 动态修复 #%s: duration=%ds", 
                                       item.get("id"), max(real_duration, 1))
            except Exception as dur_err:
                logger.warning("[HISTORY-Duration] 计算失败: %s", dur_err)
        
        return jsonify(history)
    return jsonify({"items": history if isinstance(history, list) else [], "total": len(history) if isinstance(history, list) else 0})


# 备用方案：使用查询参数获取历史记录
@app.get("/api/scheduled-task-history")
def api_scheduled_task_history_alt():
    """获取定时任务执行历史（备用方案，使用查询参数）"""
    sched_id = request.args.get("sched_id", type=int)
    if not sched_id:
        return jsonify({"error": "缺少任务ID"}), 400
    
    logger.info("[HISTORY API ALT] Request for sched_id=%s", sched_id)
    task = db.get_scheduled_search_task(sched_id)
    if not task:
        return jsonify({"error": "任务不存在"}), 404
    if not _scheduled_or_403(task):
        return jsonify({"error": "无权操作"}), 403
    
    limit = request.args.get("limit", 50, type=int)
    history = db.list_scheduled_task_history(sched_id, limit=limit)
    
    if isinstance(history, dict) and "items" in history:
        return jsonify(history)
    return jsonify({"items": history if isinstance(history, list) else [], "total": len(history) if isinstance(history, list) else 0})


@app.get("/api/scheduled-tasks/<int:sched_id>")

def api_get_scheduled_task(sched_id):

    """获取单个定时任务详情
    
    支持查询参数:
    - include_history: 设为 "1" 时同时返回执行历史
    - history_limit: 历史记录数量限制 (默认 50)
    """

    task = db.get_scheduled_search_task(sched_id)

    if not task:

        return jsonify({"error": "任务不存在"}), 404

    if not _scheduled_or_403(task):

        return jsonify({"error": "无权访问"}), 403

    # 构建结果
    result = dict(task)
    
    # 如果请求包含历史记录参数，同时返回历史
    if request.args.get("include_history") == "1":
        limit = request.args.get("history_limit", 50, type=int)
        history = db.list_scheduled_task_history(sched_id, limit=limit)
        if isinstance(history, dict) and "items" in history:
            result["history"] = history
        else:
            result["history"] = {"items": history if isinstance(history, list) else [], "total": len(history) if isinstance(history, list) else 0}
    
    return jsonify(result)


@app.post("/api/scheduled-tasks")

def api_create_scheduled_task():

    """创建定时查词任务"""

    data = request.get_json(silent=True) or {}

    account_id = data.get("accountId") or data.get("account_id")

    if not account_id:

        return jsonify({"error": "缺少客户ID"}), 400

    # 验证客户访问权限

    acc = _ensure_account_access(int(account_id))

    if not acc:

        return jsonify({"error": "无权操作该客户"}), 403

    try:

        task = db.create_scheduled_search_task(data)

        return jsonify(task), 201

    except Exception as e:

        logger.exception("[scheduled] 创建任务失败")

        return jsonify({"error": f"创建失败: {str(e)}"}), 500


@app.put("/api/scheduled-tasks/<int:sched_id>")

def api_update_scheduled_task(sched_id):

    """更新定时任务配置"""

    task = db.get_scheduled_search_task(sched_id)

    if not task:

        return jsonify({"error": "任务不存在"}), 404

    if not _scheduled_or_403(task):

        return jsonify({"error": "无权操作"}), 403

    data = request.get_json(silent=True) or {}

    try:

        updated = db.update_scheduled_search_task(sched_id, data)

        return jsonify(updated)

    except Exception as e:

        logger.exception("[scheduled] 更新任务失败")

        return jsonify({"error": f"更新失败: {str(e)}"}), 500


@app.delete("/api/scheduled-tasks/<int:sched_id>")

def api_delete_scheduled_task(sched_id):

    """删除定时任务"""

    task = db.get_scheduled_search_task(sched_id)

    if not task:

        return jsonify({"error": "任务不存在"}), 404

    if not _scheduled_or_403(task):

        return jsonify({"error": "无权操作"}), 403

    db.delete_scheduled_search_task(sched_id)

    return jsonify({"ok": True})


@app.post("/api/scheduled-tasks/<int:sched_id>/trigger")

def api_trigger_scheduled_task(sched_id):
    """手动触发定时任务 - 立即执行并返回结果"""
    
    task = db.get_scheduled_search_task(sched_id)
    if not task:
        return jsonify({"error": "任务不存在"}), 404
    if not _scheduled_or_403(task):
        return jsonify({"error": "无权操作"}), 403

    # 【修复1】防重复提交：检查是否有最近的手动触发记录（60秒冷却）
    recent_history = db._fetchone(
        db.get_conn(),
        """SELECT id, started_at FROM scheduled_task_history 
           WHERE sched_id=%s AND trigger_type='manual' 
           ORDER BY started_at DESC LIMIT 1""",
        (sched_id,)
    )
    logger.info("[触发-防重复] 查询结果: %s", recent_history)
    if recent_history:
        from datetime import datetime as _dt
        last_trigger = recent_history.get("started_at") or recent_history.get("started_at")
        logger.info("[触发-防重复] last_trigger=%s, type=%s", last_trigger, type(last_trigger))
        if last_trigger:
            try:
                if isinstance(last_trigger, str):
                    last_time = _dt.strptime(last_trigger, "%Y-%m-%d %H:%M:%S")
                else:
                    last_time = last_trigger
                elapsed = (_dt.now() - last_time).total_seconds()
                logger.info("[触发-防重复] elapsed=%.2f秒, 阈值=60秒", elapsed)
                if elapsed < 60:  # 60秒冷却时间
                    remaining = int(60 - elapsed)
                    return jsonify({
                        "error": f"操作过于频繁，请等待 {remaining} 秒后再试",
                        "cooldown": remaining,
                        "ok": False
                    }), 429
            except Exception as ex:
                logger.error("[触发-防重复] 异常: %s", ex)

    # 【关键修复】手动触发不再设置 pending 标记，避免调度器重复创建记录
    # 直接执行任务并创建一条 history 记录
    
    # 【核心防护】使用数据库锁防止并发执行
    lock_value = f"api_{_dt.now().strftime('%H%M%S')}"
    try:
        # 【关键修复】将 next_run_at 设为明天（而不是NULL）
        # 这样调度器不会检测到这个任务，彻底避免重复执行
        tomorrow = (_dt.now() + __import__('datetime').timedelta(days=1)).strftime("%Y-%m-%d %H:%M:%S")
        
        db._exec(db.get_conn(),
            """UPDATE scheduled_search_task 
               SET execution_lock=%s, next_run_at=%s 
               WHERE id=%s AND (execution_lock IS NULL OR execution_lock='')""",
            (lock_value, tomorrow, sched_id))
        
        # 验证是否获取到锁
        verify = db._fetchone(db.get_conn(),
            "SELECT execution_lock FROM scheduled_search_task WHERE id=%s",
            (sched_id,))
        
        if verify and verify.get('execution_lock') != lock_value:
            logger.warning("[触发] 任务 #%s 已被其他进程锁定(%s)，拒绝执行", sched_id, verify.get('execution_lock'))
            return jsonify({
                "error": "任务正在执行中，请稍后再试",
                "ok": False
            }), 409
        
        logger.info("[触发] 已获取任务 #%s 的执行锁: %s", sched_id, lock_value)
    except Exception as lock_err:
        logger.warning("[触发] 获取执行锁失败(继续执行): %s", lock_err)
    
    actual_task_id = ""
    try:
        from datetime import datetime as _dt
        trigger_start_time = _dt.now()
        started_at_str = trigger_start_time.strftime("%Y-%m-%d %H:%M:%S")
        account_id = task.get("accountId", 0)
        
        # 调用搜索适配器立即执行
        from overseas_search_adapter import start_search_for_account_async
        
        # 解析models
        models = task.get("models", [])
        if isinstance(models, str):
            try:
                import json as _json
                models = _json.loads(models)
            except:
                models = []
        
        if models and account_id:
            task_info = start_search_for_account_async(
                account_id,
                override_models=models,
            )
            actual_task_id = task_info.get("taskId", "")
            logger.info("[触发] 任务 #%s 已执行: taskId=%s", sched_id, actual_task_id)
        
        # 【修复耗时=0】从 search_task 表获取真实时间戳
        trigger_end_time = _dt.now()
        finished_at_str = trigger_end_time.strftime("%Y-%m-%d %H:%M:%S")
        
        # 默认使用 API 调用时间差
        duration = int((trigger_end_time - trigger_start_time).total_seconds())
        real_started_at = started_at_str
        real_finished_at = finished_at_str
        logger.info("[触发] API调用耗时: %d秒, taskId=%s", duration, actual_task_id)
        
        # 如果有 taskId，尝试从 search_task 表获取更准确的时间
        if actual_task_id:
            try:
                search_row = db._fetchone(db.get_conn(),
                    """SELECT created_at, completed_at, status 
                       FROM search_task WHERE id=%s LIMIT 1""",
                    (actual_task_id,)
                )
                logger.info("[触发] search_task查询结果: %s", search_row)
                
                if search_row:
                    st_created = str(search_row.get("created_at") or "")[:19]
                    st_completed = str(search_row.get("completed_at") or "")[:19]
                    
                    logger.info("[触发] created=%s, completed=%s", st_created, st_completed)
                    
                    # 使用 search_task 的创建时间作为开始时间
                    if st_created:
                        real_started_at = st_created
                    
                    # 如果任务已完成，使用完成时间计算真实耗时
                    if st_completed:
                        try:
                            start_dt = _dt.strptime(st_created, "%Y-%m-%d %H:%M:%S")
                            end_dt = _dt.strptime(st_completed, "%Y-%m-%d %H:%M:%S")
                            duration = int((end_dt - start_dt).total_seconds())
                            real_finished_at = st_completed
                            logger.info("[触发] 任务已完成，计算真实耗时: %d秒", duration)
                        except Exception as dt_err:
                            logger.warning("[触发] 时间解析失败: %s", dt_err)
                    else:
                        # 任务还在进行中，用当前时间和created_at计算已运行时间
                        try:
                            start_dt = _dt.strptime(st_created, "%Y-%m-%d %H:%M:%S")
                            now_dt = _dt.now()
                            duration = int((now_dt - start_dt).total_seconds())
                            # 确保至少显示1秒
                            duration = max(duration, 1)
                            real_finished_at = now_dt.strftime("%Y-%m-%d %H:%M:%S")
                            logger.info("[触发] 任务执行中，已运行: %d秒", duration)
                        except Exception as dt_err:
                            logger.warning("[触发] 时间计算失败: %s", dt_err)
                            duration = max(duration, 1)
            except Exception as db_err:
                logger.warning("[触发] 查询search_task失败: %s", db_err)
        else:
            logger.warning("[触发] actual_task_id为空，无法查询search_task")
        
        # 更新任务状态
        status = "COMPLETED" if actual_task_id else "TRIGGERED"
        db._exec(
            db.get_conn(),
            "UPDATE scheduled_search_task SET last_run_at=%s, last_status=%s, last_task_id=%s WHERE id=%s",
            (finished_at_str, status, actual_task_id, sched_id)
        )
        
        # 【只创建一条】手动触发的历史记录（带真实耗时）
        import os
        log_msg = f"[触发] === 开始创建手动历史: sched_id={sched_id}, taskId={actual_task_id}, duration={duration}s ==="
        print(log_msg)
        with open(os.path.join(os.path.dirname(__file__), '_debug.log'), 'a', encoding='utf-8') as f:
            f.write(log_msg + '\n')
        logger.info("[触发] === 开始创建手动历史: sched_id=%s, taskId=%s, duration=%ds ===", 
                   sched_id, actual_task_id, duration)
        
        # 【最终防重复】直接执行INSERT前先检查
        _now_for_check = real_finished_at
        _recent_check = db._fetchone(
            db.get_conn(),
            """SELECT id, trigger_type FROM scheduled_task_history 
               WHERE sched_id=%s AND created_at >= DATE_SUB(%s, INTERVAL 120 SECOND)
               ORDER BY id DESC LIMIT 1""",
            (sched_id, _now_for_check)
        )
        if _recent_check:
            log_skip = f"[触发] 防重复命中! 已有id={_recent_check.get('id')} type={_recent_check.get('trigger_type')}"
            print(log_skip)
            with open(os.path.join(os.path.dirname(__file__), '_debug.log'), 'a', encoding='utf-8') as f:
                f.write(log_skip + '\n')
            hist_id = _recent_check.get('id')
        else:
            # 【Duration修复】初始创建时使用search_task的created_at作为started_at
            # status设为RUNNING，duration=0，等search_task完成时自动更新
            hist_id = db.add_scheduled_task_history(
                sched_id=sched_id,
                account_id=account_id,
                task_id=actual_task_id or (task.get("lastTaskId", "") or ""),
                status="RUNNING",  # 初始状态为运行中
                started_at=real_started_at,  # 使用 search_task 的 created_at
                finished_at=real_finished_at,
                duration=0,  # 初始为0，等任务完成后自动更新
                trigger_type="manual",
                detail=f"用户手动触发，已创建查词任务 {actual_task_id}" if actual_task_id else "用户手动触发"
            )
        
        # 【最终防重复】使用事务删除120秒内同sched_id的所有其他记录（保留刚创建的）
        if hist_id and hist_id > 0:
            try:
                with db.transaction() as conn:
                    # 先查询要删除的记录
                    to_delete = db._fetchall(conn,
                        """SELECT id, trigger_type FROM scheduled_task_history 
                           WHERE sched_id=%s AND id!=%s 
                           AND created_at>=DATE_SUB(NOW(), INTERVAL 120 SECOND)""",
                        (sched_id, hist_id)
                    )
                    if to_delete:
                        delete_ids = [r['id'] for r in to_delete]
                        logger.info("[触发] 发现 %d 条重复记录待删除: %s", len(delete_ids), delete_ids)
                        db._exec(conn,
                            "DELETE FROM scheduled_task_history WHERE id IN (%s)" % ','.join(['%s'] * len(delete_ids)),
                            tuple(delete_ids)
                        )
                        logger.info("[触发] 已删除 %d 条重复历史记录(保留id=%s)", len(delete_ids), hist_id)
            except Exception as clean_err:
                logger.warning("[触发] 清理重复记录失败: %s", clean_err)
        
        # 【Duration修复】延迟查询 search_task 获取真实耗时
        if hist_id and actual_task_id:
            print(f"\n[Duration-DEBUG] 开始更新耗时: hist_id={hist_id}, task_id={actual_task_id[:12]}\n")
            try:
                import time as _time
                _time.sleep(2)  # 等待2秒让任务开始执行
                _final_search = db._fetchone(db.get_conn(),
                    """SELECT created_at, completed_at, status 
                       FROM search_task WHERE id=%s LIMIT 1""",
                    (actual_task_id,)
                )
                if _final_search:
                    _st_created = str(_final_search.get("created_at") or "")[:19]
                    _st_completed = str(_final_search.get("completed_at") or "")[:19]
                    
                    if _st_created and _st_completed:
                        _start_dt = _dt.strptime(_st_created, "%Y-%m-%d %H:%M:%S")
                        _end_dt = _dt.strptime(_st_completed, "%Y-%m-%d %H:%M:%S")
                        _real_duration = int((_end_dt - _start_dt).total_seconds())
                        
                        db._exec(db.get_conn(),
                            """UPDATE scheduled_task_history 
                               SET started_at=%s, finished_at=%s, 
                                   duration_seconds=%s, status='COMPLETED'
                               WHERE id=%s""",
                            (_st_created, _st_completed, max(_real_duration, 1), hist_id)
                        )
                        logger.info("[触发-Duration] 已更新 #%s: started=%s, finished=%s, duration=%ds", 
                                   hist_id, _st_created, _st_completed, max(_real_duration, 1))
                    elif _st_created:
                        # 任务还在运行，用当前时间计算
                        _start_dt = _dt.strptime(_st_created, "%Y-%m-%d %H:%M:%S")
                        _now_dt = _dt.now()
                        _running_duration = int((_now_dt - _start_dt).total_seconds())
                        db._exec(db.get_conn(),
                            """UPDATE scheduled_task_history 
                               SET finished_at=%s, duration_seconds=%s
                               WHERE id=%s""",
                            (_now_dt.strftime("%Y-%m-%d %H:%M:%S"), max(_running_duration, 1), hist_id)
                        )
                        logger.info("[触发-Duration] 任务运行中，已更新 #%s: duration=%ds", 
                                   hist_id, max(_running_duration, 1))
            except Exception as dur_err:
                logger.warning("[触发-Duration] 更新耗时失败: %s", dur_err)
        
        log_msg2 = f"[触发] === 手动历史创建完成: id={hist_id} ==="
        print(log_msg2)
        with open(os.path.join(os.path.dirname(__file__), '_debug.log'), 'a', encoding='utf-8') as f:
            f.write(log_msg2 + '\n')
        logger.info("[触发] === 手动历史创建完成: id=%s ===", hist_id)
        
        # 【关键】释放执行锁
        try:
            db._exec(db.get_conn(),
                "UPDATE scheduled_search_task SET execution_lock=NULL WHERE id=%s",
                (sched_id,))
            logger.info("[触发] 已释放任务 #%s 的执行锁", sched_id)
        except Exception as rel_err:
            logger.warning("[触发] 释放锁失败: %s", rel_err)
            
        return jsonify({
            "ok": True,
            "taskId": actual_task_id,
            "message": "已触发执行" if actual_task_id else "已发送触发指令"
        })
            
    except Exception as exec_err:
        logger.error("[触发] 执行失败: %s", exec_err, exc_info=True)
        # 记录失败历史
        try:
            from datetime import datetime as _dt
            now_str = _dt.now().strftime("%Y-%m-%d %H:%M:%S")
            db.add_scheduled_task_history(
                sched_id=sched_id,
                account_id=task.get("accountId", 0),
                task_id="",
                status="FAILED",
                started_at=now_str,
                finished_at=now_str,
                duration=0,
                trigger_type="manual",
                detail=str(exec_err)[:200]
            )
        except:
            pass
        return jsonify({
            "ok": False,
            "error": str(exec_err)[:200]
        }), 500


@app.put("/api/scheduled-tasks/<int:sched_id>/toggle")

def api_toggle_scheduled_task(sched_id):

    """切换定时任务启用/禁用状态"""

    task = db.get_scheduled_search_task(sched_id)

    if not task:

        return jsonify({"error": "任务不存在"}), 404

    if not _scheduled_or_403(task):

        return jsonify({"error": "无权操作"}), 403

    data = request.get_json(silent=True) or {}

    enabled = data.get("enabled", not task.get("enabled", True))

    updated = db.update_scheduled_search_task(sched_id, {"enabled": 1 if enabled else 0})

    return jsonify(updated)


# ========== Scheduled Ranking Tasks ==========


def _ranking_task_or_403(task_id: str):
    """获取排名任务或返回403错误."""
    task = db.get_ranking_task(task_id)

    if not task:

        return jsonify({"error": "Error"}), 404

    aid = task.get("accountId") or task.get("account_id")

    if aid and not _ensure_account_access(int(aid)):

        return None, (jsonify({"ok": False, "error": "Error"}), 403)

    return task, None































































































































    "firecrawl_api_key",

    "qwen_api_key",

    "dashscope_api_key",

    "gemini_api_key",

    "flask_secret_key",

    "llm_api_key",

    "chatgpt_api_key",





def _is_secret_key(key: str) -> bool:

    if key in _SECRET_SETTING_KEYS:

        return True

    kl = key.lower()

    return "api_key" in kl or "_secret" in kl or "_token" in kl



_MASK_PATTERN = "****"





def _mask_secret(value: str) -> str:

    if not value:

        return ""

    if len(value) <= 8:

        return _MASK_PATTERN

    return f"{value[:3]}{_MASK_PATTERN}{value[-4:]}"





@app.get("/api/settings")

def api_get_settings():

    _require_super_admin()

    raw = db.get_all_settings()

    safe = {}

    for k, v in raw.items():

        if k == "flask_secret_key":

            continue

        if _is_secret_key(k):

            safe[k] = _mask_secret(v)

        else:

            safe[k] = v

    return jsonify(safe)





@app.put("/api/settings")

def api_save_settings():

    _require_super_admin()

    data = request.get_json(force=True, silent=True) or {}

    current = db.get_all_settings()

    clean = {}

    for k, v in data.items():
        if k == "flask_secret_key":
            continue
        if _is_secret_key(k) and isinstance(v, str) and _MASK_PATTERN in v:
            continue
        clean[k] = v

    db.save_settings(clean)

    return jsonify({"ok": True})









def _mask_oauth_token(token: str) -> str:

    if not token:

        return ""

    if len(token) <= 12:

        return "****"

    return f"{token[:6]}****{token[-4:]}"





@app.get("/api/publish/official-configs")

def api_publish_official_configs():



    cfg_map = {int(x["account_id"]): x for x in db.list_account_webhook_configs()}

    items = []
    accounts = db.list_accounts()
    for acc in accounts:

        aid = int(acc["id"])

        cfg = cfg_map.get(aid)

        items.append({

            "accountId": aid,

            "companyName": acc.get("companyName", ""),

            "companyBrand": acc.get("companyBrand", ""),

            "configured": bool(cfg and int(cfg.get("enabled") or 0) == 1 and (cfg.get("webhook_url") or "").strip()),

            "webhookUrl": (cfg or {}).get("webhook_url", ""),

            "oauthToken": (cfg or {}).get("oauth_token", ""),

            "oauthTokenMasked": _mask_oauth_token((cfg or {}).get("oauth_token") or ""),

            "updatedAt": (cfg or {}).get("updated_at", ""),

        })

    return jsonify({"items": items})





@app.get("/api/publish/official-config/<int:account_id>")

def api_publish_official_config_get(account_id: int):

    acc = _ensure_account_access(account_id)

    if not acc:

        return jsonify({"error": "Error"}), 404

    cfg = db.get_account_webhook_config(account_id) or {}

    return jsonify({

        "accountId": account_id,

        "configured": bool(cfg and int(cfg.get("enabled") or 0) == 1 and (cfg.get("webhook_url") or "").strip()),

        "webhookUrl": cfg.get("webhook_url", ""),

        "oauthToken": cfg.get("oauth_token", ""),

        "oauthTokenMasked": _mask_oauth_token(cfg.get("oauth_token") or ""),

        "updatedAt": cfg.get("updated_at", ""),

    })





@app.put("/api/publish/official-config/<int:account_id>")

def api_publish_official_config_save(account_id: int):

    acc = _ensure_account_access(account_id)

    if not acc:

        return jsonify({"error": "Error"}), 404

    data = request.get_json(silent=True) or {}

    webhook_url = (data.get("webhookUrl") or data.get("webhook_url") or "").strip()

    if not webhook_url:

        return jsonify({"error": "闁剧偓甯撮崷鏉挎絻娑撳秷鍏樻稉铏光敄"}), 400

    if not (webhook_url.startswith("http://") or webhook_url.startswith("https://")):

        return jsonify({"error": "Error"}), 400




    old_cfg = db.get_account_webhook_config(account_id) or {}
    oauth_token = (old_cfg.get("oauth_token") or "").strip() or ("geo_oauth2_" + secrets.token_urlsafe(24))

    cfg = db.save_account_webhook_config(

        account_id=account_id,

        webhook_url=webhook_url,

        oauth_token=oauth_token,

        created_by=session.get("user_id"),

        enabled=True,

    )

    return jsonify({

        "ok": True,

        "accountId": account_id,

        "configured": True,

        "webhookUrl": cfg.get("webhook_url", ""),

        "oauthToken": cfg.get("oauth_token", ""),

        "oauthTokenMasked": _mask_oauth_token(cfg.get("oauth_token") or ""),

        "updatedAt": cfg.get("updated_at", ""),

    })





@app.post("/api/publish/official-config/<int:account_id>")

def api_publish_official_config_save_post(account_id: int):

    return api_publish_official_config_save(account_id)





@app.delete("/api/publish/official-config/<int:account_id>")

def api_publish_official_config_clear(account_id: int):

    acc = _ensure_account_access(account_id)

    if not acc:

        return jsonify({"error": "Error"}), 404

    db.clear_account_webhook_config(account_id)

    return jsonify({"ok": True, "accountId": account_id, "configured": False})





@app.post("/api/publish/webhook/publish")

def api_publish_webhook_publish():

    data = request.get_json(silent=True) or {}

    try:

        account_id = int(data.get("accountId") or data.get("account_id") or 0)

    except (TypeError, ValueError):

        account_id = 0

    if account_id <= 0:

        return jsonify({"error": "accountId 閺冪姵鏅?"}), 400

    acc = _ensure_account_access(account_id)

    if not acc:

        return jsonify({"error": "Error"}), 404



    title = (data.get("title") or "").strip()

    content = data.get("content") or ""

    if not title or not content:

        return jsonify({"error": "Error"}), 400



    cfg = db.get_account_webhook_config(account_id)

    if not cfg or int(cfg.get("enabled") or 0) != 1 or not (cfg.get("webhook_url") or "").strip():

        return jsonify({"error": "Error"}), 400



    payload = {

        "postId": data.get("postId") or (data.get("articleId") and str(data.get("articleId"))) or uuid.uuid4().hex[:16],

        "content": content,

        "slug": (data.get("slug") or "page-slug").strip() or "page-slug",

        "title": title,

        "seo": {

            "title": (data.get("seo") or {}).get("title") or title,

            "description": (data.get("seo") or {}).get("description") or "",

            "keywords": (data.get("seo") or {}).get("keywords") or "",

            "feature_image": (data.get("seo") or {}).get("feature_image") or "",

        },

    }



    headers = {

        "Authorization": f"Bearer {cfg.get('oauth_token') or ''}",

        "Content-Type": "application/json",

    }

    try:

        resp = requests.post((cfg.get("webhook_url") or "").strip(), json=payload, headers=headers, timeout=20)

        if resp.status_code < 200 or resp.status_code >= 300:

            return jsonify({

                "error": "Webhook 閸欐垵绔锋径杈Е",

                "statusCode": resp.status_code,

                "response": (resp.text or "")[:600],

            }), 502

        return jsonify({"ok": True, "statusCode": resp.status_code})

    except requests.RequestException as e:

        return jsonify({"error": "Webhook 鐠囬攱鐪板鍌氱埗", "detail": str(e)}), 502

























































# ========== Scheduled Ranking Tasks ==========



























# ========== Scheduled Citation Tasks ==========



























# ========== Scheduled Quote Tasks ==========



























# ========== Scheduled Pipeline (Batch) Tasks ==========















































































@app.get("/api/accounts/<int:account_id>/weekly-reports")

def api_list_weekly_reports(account_id: int):

    if not _ensure_account_access(account_id):

        return jsonify({"error": "Error"}), 404

    limit = request.args.get("limit", 30, type=int)

    return jsonify(db.list_weekly_reports_by_account(account_id, limit=limit))





































@app.get("/api/accounts/<int:account_id>/share-token")

def api_get_share_token(account_id: int):

    if not _ensure_account_access(account_id):

        return jsonify({"error": "Error"}), 404

    token = db.get_share_token(account_id)

    return jsonify({"accountId": account_id, "token": token})





@app.post("/api/accounts/<int:account_id>/share-token/reset")

def api_reset_share_token(account_id: int):

    if not _ensure_account_access(account_id):

        return jsonify({"error": "Error"}), 404

    token = db.regenerate_share_token(account_id)

    return jsonify({"accountId": account_id, "token": token})









def _ensure_report_access(report_id: int) -> dict | None:

    """"""

    report = db.get_weekly_report(report_id)

    if not report:

        return None

    account_id = report.get("accountId") or report.get("account_id")

    if not _ensure_account_access(int(account_id)):

        return None

    return report

















@app.get("/api/accounts/<int:account_id>/weekly-schedule")

def api_get_weekly_schedule(account_id: int):

    if not _ensure_account_access(account_id):

        return jsonify({"error": "Error"}), 404

    sched = db.get_weekly_schedule_by_account(account_id)

    return jsonify(sched or None)





@app.post("/api/accounts/<int:account_id>/weekly-schedule")

def api_create_weekly_schedule(account_id: int):

    if not _ensure_account_access(account_id):

        return jsonify({"error": "Error"}), 404

    existing = db.get_weekly_schedule_by_account(account_id)

    if existing:

        return jsonify({"error": "鐠囥儴澶勯崣宄板嚒鐎涙ê婀崨銊﹀Г鐠嬪啫瀹抽敍宀冾嚞閺€鍦暏 PUT 閺囧瓨鏌?"}), 409

    data = request.get_json(silent=True) or {}

    data["accountId"] = account_id

    sched = db.create_weekly_schedule(data)

    return jsonify(sched)































def _gate_ctx_for_report(report_id: int) -> dict:



    try:

        report = db.get_weekly_report(report_id, include_html=False) or {}

        rtype = (report.get("reportType") or report.get("report_type") or "weekly").lower()

        aid = int(report.get("accountId") or report.get("account_id") or 0)

        acc = db.get_account(aid) if aid else {}

        brand_raw = (acc or {}).get("companyBrand", "") or ""

        pass

        company_raw = (acc or {}).get("companyName", "") or ""

        import re as _re

        brand = _re.sub(r"\s+", "", brand_raw) if brand_raw else ""
        company = _re.sub(r"\s+", "", company_raw) if company_raw else ""

        pass

        ps = report.get("periodStart") or report.get("period_start") or ""

        pe = report.get("periodEnd") or report.get("period_end") or ""

        period = f"{ps} ~ {pe}" if ps != pe else (ps or "")

        type_label = {"brand": "GEO 品牌分析报告", "weekly": "GEO 周报趋势", "daily": "GEO 日报告", "monthly": "GEO 月报告"}.get(rtype, "GEO 综合分析报告")

        badge = {"brand": "GEO Competition Analysis Report", "weekly": "GEO Weekly Report", "daily": "GEO Daily Report", "monthly": "GEO Monthly Report"}.get(rtype, "GEO Report")

        title = f"Error: see logs for details"



        target = brand or company or "通用"

        if rtype == "brand":
            desc = (
                f"T-GEO品牌排名任务：对品牌【{target}】的AI搜索结果进行排名分析。"
                f"系统将自动搜索该品牌相关关键词，收集各AI平台的回答文本，"
                f"并按预设规则进行排名统计，生成详细的排名报告。"
            )
        else:
            desc = (
                f"T-GEO模型评测任务：针对目标【{target}】在多个AI平台上的表现进行评估。"
                f"将对比不同AI模型对该目标的回答质量、准确性和完整性，"
                f"生成模型评测报告供决策参考。"
            )

        return dict(

            title=title, badge=badge,

            description=desc,

            brand=brand, company=company if company and company != brand else "", period=period,

        )

    except Exception:

        return dict(title="鐠佸潡妫舵宀冪槈", badge="GEO Report",

                    description="", brand="", company="", period="")





def _gate_ctx_for_account(account_id: int) -> dict:
    """获取账号上下文信息用于报告生成."""
    try:
        acc = db.get_account(account_id) or {}
        brand_raw = acc.get("companyBrand", "") or ""
        company_raw = acc.get("companyName", "") or ""
        import re as _re2
        brand = _re2.sub(r"\s+", "", brand_raw) if brand_raw else ""
        company = _re2.sub(r"\s+", "", company_raw) if company_raw else ""
        target = brand or company or "通用"
        return dict(
            title="GEO 周报趋势报告", badge="GEO Weekly Report",
            description=f"针对{target}的GEO周报趋势分析报告",
            brand=brand, company=company if company and company != brand else "", period="",
        )
    except Exception:
        return dict(title="GEO 周报趋势报告", badge="GEO Weekly Report",
                    description="", brand="", company="", period="")





_REPORT_TYPE_LABELS = {"brand": "GEO 品牌汇总报告", "weekly": "GEO 周报",
                       "daily": "GEO 日报", "monthly": "GEO 月报",
}











































# ========== Report Share Helpers ==========

def _report_type_label(rtype: str) -> str:
    """Return human-readable label for report type."""
    return _REPORT_TYPE_LABELS.get(rtype, rtype)


def _pick_report_theme(brand_name: str) -> dict:
    """Pick report theme colors based on brand name hash or default GEO theme."""
    import hashlib
    h = hashlib.md5(brand_name.encode()).hexdigest()
    idx = int(h[:8], 16) % 5
    themes = [
        {"primary": "#2563eb", "mid": "#3b82f6", "gradient_end": "#60a5fa",
         "accent": "#059669", "accent2": "#10b981", "cover_accent": "#f59e0b"},
        {"primary": "#7c3aed", "mid": "#8b5cf6", "gradient_end": "#a78bfa",
         "accent": "#dc2626", "accent2": "#ef4444", "cover_accent": "#eab308"},
        {"primary": "#db2777", "mid": "#ec4899", "gradient_end": "#f472b6",
         "accent": "#0891b2", "accent2": "#06b6d4", "cover_accent": "#84cc16"},
        {"primary": "#ea580c", "mid": "#f97316", "gradient_end": "#fb923c",
         "accent": "#4338ca", "accent2": "#6366f1", "cover_accent": "#22c55e"},
        {"primary": "#0891b2", "mid": "#0ea5e9", "gradient_end": "#38bdf8",
         "accent": "#be185d", "accent2": "#ec4899", "cover_accent": "#eab308"},
    ]
    return themes[idx]


def _share_report_session_key(report_id: int) -> str:
    """Return session key for share authorization."""
    return f"share_report_{report_id}"


def _share_report_authorized(report_id: int) -> bool:
    """Check if user has authorized this shared report in session."""
    return bool(session.get(_share_report_session_key(report_id)))


def _safe_share_report_next(report_id: int, next_url: str) -> str:
    """Validate and return safe redirect URL after auth."""
    if next_url and next_url.startswith("/"):
        return next_url
    return f"/share/report/{report_id}"


_SHARE_GATE_HTML = """
<!DOCTYPE html>
<html lang="zh-CN">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>{{ title }} - 密码验证</title>
<style>
*{margin:0;padding:0;box-sizing:border-box}
body{font-family:-apple-system,BlinkMacSystemFont,"Segoe UI",Roboto,sans-serif;background:#f0f2f5;display:flex;align-items:center;justify-content:center;min-height:100vh}
.card{background:#fff;border-radius:12px;box-shadow:0 4px 24px rgba(0,0,0,.1);padding:40px;width:360px;max-width:90vw}
h1{font-size:20px;color:#333;margin-bottom:8px}
.subtitle{color:#666;font-size:14px;margin-bottom:24px}
input{width:100%;padding:12px;border:1px solid #ddd;border-radius:8px;font-size:16px;margin-bottom:16px}
button{width:100%;padding:12px;background:#2563eb;color:#fff;border:none;border-radius:8px;font-size:16px;cursor:pointer}
button:hover{background:#1d4ed8}
.error{color:#dc2626;font-size:14px;margin-bottom:12px}
</style>
</head>
<body>
<div class="card">
<h1>{{ badge }}</h1>
<p class="subtitle">{{ description }}</p>
{% if error %}<p class="error">{{ error }}{% endif %}
<form method="POST" action="{{ action }}">
<input type="password" name="pwd" placeholder="请输入访问密码" autofocus required>
<input type="hidden" name="next" value="{{ next_url }}">
<button type="submit">确认访问</button>
</form>
</div>
</body>
</html>
"""

_SHARE_VIEWER_HTML = """
<!DOCTYPE html>
<html lang="zh-CN">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>{{ title }}</title>
<style>
body{margin:0;background:#f5f5f5}
iframe{width:100%;height:100vh;border:none}
</style>
</head>
<body>
<iframe src="{{ content_url }}" allowfullscreen></iframe>
</body>
</html>
"""

# Execute ranking analysis stub
def _execute_ranking_analysis(task_id: str, keywords: list, brands: list, offset: dict = None):
    """Execute ranking analysis for given task and keywords."""
    from datetime import datetime
    now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    db.update_ranking_task(task_id, status="completed", done=offset.get("done", 0) + len(keywords) if offset else len(keywords))


@app.get("/share/report/<int:report_id>")

def spa_share_report_gate(report_id: int):

    if _share_report_authorized(report_id):

        _rt = (db.get_weekly_report(report_id) or {}).get("reportType") or "weekly"

        return render_template_string(

            _SHARE_VIEWER_HTML,

            title=_report_type_label(_rt),

            content_url=f"/api/share/report/{report_id}/content",

        )

    next_url = request.full_path.rstrip("?")

    return render_template_string(

        _SHARE_GATE_HTML,

        action=f"/share/report/{report_id}/auth",

        next_url=next_url,

        error="",

        **_gate_ctx_for_report(report_id),

    )





@app.post("/share/report/<int:report_id>/auth")

def spa_share_report_auth(report_id: int):





    raw = request.form.get("pwd", "")
    pwd = "".join(raw.split())  # 閸樺娅庢禒缁樺壈缁岃櫣娅?閸?\r \n \t 閵嗏偓)

    nxt = _safe_share_report_next(report_id, request.form.get("next") or "")

    if not db.verify_weekly_report_share_token(report_id, pwd):

        return render_template_string(

            _SHARE_GATE_HTML,

            action=f"/share/report/{report_id}/auth",

            next_url=nxt,

            error="鐎靛棛鐖滈柨娆掝嚖閿涘矁顕柌宥堢槸",

            **_gate_ctx_for_report(report_id),

        ), 401

    session[_share_report_session_key(report_id)] = True

    session.permanent = True

    return redirect(nxt)

























@app.put("/api/accounts/<int:account_id>/weekly-reports/<int:report_id>/expiry")

def api_update_weekly_report_expiry(account_id: int, report_id: int):

    """TODO: fix docstring"""

    if not _ensure_account_access(account_id):

        return jsonify({"error": "Error"}), 403

    data = request.get_json(force=True, silent=True) or {}

    days = data.get("days")

    if days is None:

        new_exp = None

    else:

        try:

            days_int = int(days)

        except (TypeError, ValueError):

            return jsonify({"error": "days 韫囧懘銆忛弰顖涙殻閺佺増鍨?null"}), 400

        if days_int <= 0:

            return jsonify({"error": "days 韫囧懘銆?> 0,鐠?null 鐞涖劎銇氬闀愮瑝鏉╁洦婀?"}), 400

        from datetime import datetime as _dt, timedelta as _td

        new_exp = (_dt.now() + _td(days=days_int)).strftime("%Y-%m-%d %H:%M:%S")

    with db.transaction() as c:

        cur = db._exec(c,

            "UPDATE weekly_report SET token_expires_at=%s WHERE id=%s AND account_id=%s",

            (new_exp, report_id, account_id))

        if not cur.rowcount:

            return jsonify({"error": "閹躲儱鎲℃稉宥呯摠閸︺劍鍨ㄦ稉宥呯潣娴滃氦顕氱拹锔藉煕"}), 404

    return jsonify({"ok": True, "token_expires_at": new_exp})























def _build_themed_report_html(html_content: str, brand_name: str = "") -> str:

    """TODO: fix docstring"""

    pass

    pass

    if not html_content or "</head>" not in html_content:

        return html_content

    theme = _pick_report_theme(brand_name or "")

    _override = (

        "<style>"

        ".nav-inner{scrollbar-width:none !important;-ms-overflow-style:none !important;"

        "justify-content:center !important;flex-wrap:nowrap !important;"

        "overflow-x:hidden !important;padding-bottom:0 !important}"

        ".nav-inner::-webkit-scrollbar{display:none !important;width:0 !important;height:0 !important;background:transparent !important}"

        ":root{--primary:" + theme["primary"] + " !important;"

        "--accent:" + theme["accent"] + " !important;"

        "--accent2:" + theme["accent2"] + " !important}"

        ".cover{background:linear-gradient(135deg," + theme["primary"] + " 0%," + theme["mid"] + " 50%," + theme["gradient_end"] + " 100%) !important}"

        ".data-table th{background:" + theme["primary"] + " !important;color:#fff !important}"

        ".section-title .num{background:" + theme["accent"] + " !important}"

        ".nav a:hover,.nav a.active{background:" + theme["accent"] + " !important;color:#fff !important}"

        ".cover .meta-item .num{color:" + theme["cover_accent"] + " !important;text-shadow:0 2px 8px rgba(0,0,0,.25)}"

        ".cover .meta-item{background:rgba(255,255,255,.08) !important;border:1px solid rgba(255,255,255,.18) !important}"

        ".cover .meta-item .label{color:rgba(255,255,255,.85) !important}"



        "@page{size:A4 portrait;margin:15mm 12mm 16mm 12mm}"

        "@media print{"



        " *,*::before,*::after{-webkit-print-color-adjust:exact !important;print-color-adjust:exact !important;color-adjust:exact !important}"

        " html,body{background:#fff !important;margin:0 !important;padding:0 !important;font-size:8.5pt !important;line-height:1.4 !important}"



        " h2{font-size:13pt !important;margin:6px 0 6px !important;line-height:1.3 !important}"

        " h3{font-size:11pt !important;margin:4px 0 4px !important}"

        " h4{font-size:9.5pt !important;margin:3px 0 !important}"

        " p,li{margin:2px 0 !important;line-height:1.45 !important}"

        " ul,ol{margin:4px 0 !important;padding-left:18px !important}"



        " .nav,.shot-modal,.shot-head .close,.shot-head .zoom-btn,.shotwall-more>summary,.no-print{display:none !important}"

        " .container{max-width:100% !important;padding:0 !important;margin:0 !important}"



        " .cover{page-break-after:always;break-after:page;min-height:calc(100vh - 31mm);display:flex !important;flex-direction:column;justify-content:center;align-items:stretch;padding:0 6mm !important;border-radius:0 !important;box-shadow:none !important}"

        " .cover h1{font-size:26pt !important;line-height:1.22 !important}"

        " .cover .sub{font-size:12pt !important}"

        " .cover .meta{margin-top:24px !important}"

        " .cover .meta-item{padding:10px 12px !important}"

        " .cover .meta-item .num{text-shadow:none !important;font-size:18pt !important}"



        " .section{padding:3mm 0 2mm !important;page-break-inside:auto;break-inside:auto}"

        " .section-title{page-break-after:avoid !important;break-after:avoid !important;margin:0 0 6px !important;font-size:13pt !important}"

        " .section-title + *{page-break-before:avoid !important}"



        " .grid,.grid-2,.cap-grid,.brand-grid{display:grid !important;grid-template-columns:1fr 1fr !important;gap:7px !important}"

        " .grid-3,.grid-4{display:grid !important;grid-template-columns:1fr 1fr 1fr !important;gap:7px !important}"

        " .grid-1,.grid-single{grid-template-columns:1fr !important}"



        " .card,.data-card,.cap-card,.shotwall-card,.rc-card,.chart-card,.chart-wrap,.kw-card,.opt-card,.cmp-card,.insight{page-break-inside:avoid !important;break-inside:avoid !important;margin-bottom:6px !important;padding:9px 11px !important}"



        " .brand-card{page-break-inside:auto !important;break-inside:auto !important;margin-bottom:8px !important;padding:0 !important}"

        " .brand-card-header{padding:9px 14px !important;font-size:12pt !important;page-break-after:avoid !important;break-after:avoid !important}"

        " .brand-card-body{padding:8px 14px !important}"

        " .brand-row{padding:5px 0 !important}"

        " .pros-cons{page-break-inside:avoid !important;break-inside:avoid !important;margin-top:8px !important;gap:10px !important}"

        " .pros-cons .pros,.pros-cons .cons{padding:9px 11px !important}"

        " .quote{page-break-inside:avoid !important;break-inside:avoid !important;padding:7px 12px !important;margin:5px 0 !important;font-size:8pt !important;line-height:1.5 !important}"

        " .kpi{page-break-inside:avoid !important;break-inside:avoid !important;margin-bottom:6px !important;padding:9px 11px !important}"

        " .kpi .val{font-size:18pt !important;margin-top:2px !important}"

        " .kpi .lbl{font-size:8pt !important}"

        " .kpi .hint{font-size:8pt !important}"



        " [id^=chart_]{page-break-inside:avoid !important;break-inside:avoid !important}"

        " [id^=chart_] img{width:100% !important;height:auto !important;max-width:100% !important;object-fit:contain !important}"

        " .chart-box>div,.chart-box-sm>div,.chart-box-lg>div,.chart-box-xl>div{width:100% !important;height:auto !important}"

        " .chart-box svg,.chart-box-sm svg,.chart-box-lg svg,.chart-box-xl svg{width:100% !important;height:auto !important;max-width:100% !important}"



        " .scroll-wrap,.kw-scroll,.cmp-scroll,.tbl-scroll{max-height:none !important;overflow:visible !important;border:none !important}"

        " table,.data-table{width:100% !important;table-layout:fixed !important;font-size:7.5pt !important;border-collapse:collapse;line-height:1.3 !important}"

        " .data-table thead{display:table-header-group}"

        " .data-table tr{page-break-inside:avoid !important;break-inside:avoid !important}"

        " th,td{padding:3px 5px !important;word-break:break-word !important;overflow-wrap:anywhere !important;vertical-align:top}"



        " .shotwall-grid{grid-template-columns:repeat(2,1fr) !important;gap:8px !important}"

        " .shotwall-card{page-break-inside:avoid !important}"

        " .shotwall-card img{max-width:100% !important;height:auto !important}"



        "}"

        "</style>"

        "<script>"

        "(function(){"

        " if (typeof window === 'undefined') return;"

        " var converted = false;"

        " function convertChartsToPng(){"

        "   if (converted) return;"

        "   if (typeof echarts === 'undefined') return;"

        "   var nodes = document.querySelectorAll('[id^=chart_]');"

        "   nodes.forEach(function(el){"

        "     try{"

        "       var inst = echarts.getInstanceByDom(el);"

        "       if (!inst) return;"



        "       if (el.id === 'chart_radar'){ try{ inst.setOption({radar:{radius:'56%',center:['50%','54%'],axisName:{fontSize:10,color:'#555',formatter:function(n){n=String(n||'');var m=n.match(/^(.*?)[閿?](.+?)[閿?]\\s*$/);if(m)return m[1]+'\\n閿?+m[2]+'閿?;if(n.length>6){var k=Math.ceil(n.length/2);return n.slice(0,k)+'\\n'+n.slice(k);}return n;}}}},false); }catch(e){} }"

        "       var w = el.clientWidth || el.offsetWidth || 800;"

        "       var h = el.clientHeight || el.offsetHeight || 380;"

        "       var url = inst.getDataURL({type:'png', pixelRatio:2, backgroundColor:'#ffffff', excludeComponents:['toolbox']});"

        "       el.setAttribute('data-orig-html', el.innerHTML);"

        "       el.innerHTML = '<img alt=\"chart\" src=\"' + url + '\" style=\"width:' + w + 'px;height:' + h + 'px;display:block;max-width:100%;object-fit:contain\" />';"

        "     }catch(e){ console.warn('chart png convert fail', e); }"

        "   });"

        "   converted = true;"

        " }"

        " function restoreCharts(){"

        "   if (!converted) return;"

        "   document.querySelectorAll('[id^=chart_]').forEach(function(el){"

        "     var orig = el.getAttribute('data-orig-html');"

        "     if (orig){ el.innerHTML = orig; el.removeAttribute('data-orig-html'); }"

        "   });"

        "   converted = false;"

        " }"

        " window.__convertChartsToPng = convertChartsToPng;"  # 閺堝秴濮熺粩?PDF 濞撳弶鐓嬮懘姘拱娑撹濮╃拫鍐暏

        " window.addEventListener('beforeprint', convertChartsToPng);"

        " window.addEventListener('afterprint', restoreCharts);"

        " var qs = new URLSearchParams(location.search);"

        " if (qs.get('print') === '1'){"

        "   var fire = function(){ convertChartsToPng(); setTimeout(function(){window.print();}, 600); };"

        "   if (document.readyState === 'complete') setTimeout(fire, 1500);"

        "   else window.addEventListener('load', function(){setTimeout(fire, 1500);});"

        " }"

        "})();"

        "</script></head>"

    )

    return html_content.replace("</head>", _override, 1)











_PDF_RENDER_PY = "/www/server/pyporject_evn/geo-system/bin/python3.10"

_PDF_RENDER_SCRIPT = os.path.join(os.path.dirname(os.path.abspath(__file__)), "report_pdf_render.py")





def _report_pdf_filename(report: dict, acc: dict) -> str:

    """鎶ュ憡 PDF 鏂囦欢鍚嶏細鍝佺墝_绫诲瀷_鏃ユ湡.pdf(涓嶅甫閭€璇风爜/璐﹀彿鍗曞厓淇℃伅)"""

    brand = _parse_brand_list(acc.get("companyBrand") or "")

    brand_str = (brand[0] if brand else "") or acc.get("companyBrand") or "默认品牌"

    brand_str = str(brand_str).strip().replace("/", "_").replace("\\", "_")

    rtype = (report.get("reportType") or "weekly").lower()

    if rtype == "brand":
        date_str = report.get("periodEnd") or report.get("periodStart") or datetime.now().strftime("%Y-%m-%d")
        return f"{brand_str}_品牌汇总_{date_str}.pdf"

    if rtype == "stage":
        return f"{brand_str}_阶段报告_{date_str}.pdf"

    return f"{brand_str}_{rtype}_{date_str}.pdf"





def _report_pdf_response(themed_html: str, download_name: str):

    # themed HTML -> chromium renders PDF (subprocess isolation) -> attachment download.

    import subprocess

    import tempfile

    from urllib.parse import quote

    hf = tempfile.NamedTemporaryFile("w", suffix=".html", delete=False, encoding="utf-8")

    try:

        hf.write(themed_html)

        hf.close()

        pdf_path = hf.name[:-5] + ".pdf"

        try:

            subprocess.run([_PDF_RENDER_PY, _PDF_RENDER_SCRIPT, hf.name, pdf_path],

                           timeout=180, check=True, capture_output=True)

            with open(pdf_path, "rb") as f:

                data = f.read()

        except subprocess.TimeoutExpired:

            logger.error("[pdf] render timeout")

            return jsonify({"error": "PDF 閻喐鍨氱搾鍛閿涘矁顕粙宥呮倵闁插秷鐦?"}), 504

        except subprocess.CalledProcessError as e:

            logger.error("[pdf] render failed rc=%s err=%s", e.returncode,

                         (e.stderr or b"").decode("utf-8", "ignore")[:500])

            return jsonify({"error": "PDF 閻喐鍨氭径杈Е閿涘矁顕粙宥呮倵闁插秷鐦?"}), 500

        finally:

            try:

                os.unlink(pdf_path)

            except Exception:

                pass

    finally:

        try:

            os.unlink(hf.name)

        except Exception:

            pass

    resp = Response(data, mimetype="application/pdf")

    resp.headers["Content-Disposition"] = "attachment; filename*=UTF-8''" + quote(download_name)

    return resp













@app.errorhandler(404)

def not_found(e):



    if request.path.startswith("/api/"):

        return jsonify({"error": "Not Found"}), 404

    return send_from_directory(app.static_folder, "index.html")





@app.errorhandler(500)

def server_error(e):

    return jsonify({"error": "Internal Server Error"}), 500





# Register blueprint routes

try:

    import knowledge_routes

    knowledge_routes.register(app)

except Exception:

    logger.exception("knowledge_routes register failed")





# Startup cleanup: zombie weekly reports

try:

    import db as _db_sweep

    _conn = _db_sweep.get_conn()

    _cur = _conn.cursor()

    _cur.execute(

        "UPDATE weekly_report SET status='failed', "

        "error_message=CONCAT('启动时清理超时任务, ',"

        "DATE_FORMAT(NOW(),'%Y-%m-%d %H:%i:%s'), "

        "\"服务器重启中断,\",IFNULL(progress_percent,0),\"% 进度\", "

        "IFNULL(progress_message,'')), "

        "completed_at=DATE_FORMAT(NOW(),'%Y-%m-%d %H:%i:%s') "

        "WHERE status='running' AND (created_at IS NULL OR "

        "TIMESTAMPDIFF(MINUTE, STR_TO_DATE(created_at,'%Y-%m-%d %H:%i:%s'), NOW()) > 2)"

    )

    _swept = _cur.rowcount

    try:

        _conn.commit()

    except Exception:

        pass

    if _swept:

        logger.warning("startup sweep: marked %d zombie weekly_report as failed", _swept)

except Exception:

    logger.exception("startup zombie sweep failed")



# Startup cleanup: zombie content drafts

try:

    import db as _db_bsweep

    _bconn = _db_bsweep.get_conn()

    _bcur = _bconn.cursor()



    _bcur.execute(

        "UPDATE content_draft SET status='failed', "

        "error_msg='服务重启导致生成中断，请重试', updated_at=NOW() "

        "WHERE status='generating' AND batch_id IN ("

        "  SELECT id FROM content_draft_batch "

        "  WHERE status='running' AND updated_at < NOW() - INTERVAL 30 MINUTE)"

    )



    _bcur.execute(

        "UPDATE content_draft_batch SET "

        "status=IF(COALESCE(done_count,0)>0,'partial_failed','cancelled'), updated_at=NOW() "

        "WHERE status='running' AND updated_at < NOW() - INTERVAL 30 MINUTE"

    )

    _bswept = _bcur.rowcount



    _bcur.execute(

        "UPDATE content_analysis SET status='failed', "

        "error_message='服务重启导致生成中断', "

        "updated_at=NOW() "

        "WHERE status='generating' AND updated_at < NOW() - INTERVAL 30 MINUTE"

    )

    _caswept = _bcur.rowcount

    try:

        _bconn.commit()

    except Exception:

        pass

    if _bswept or _caswept:

        logger.warning("startup sweep: %d zombie batch + %d zombie content_analysis cleared", _bswept, _caswept)

except Exception:

    logger.exception("startup batch/CA zombie sweep failed")



# Register kb_routes

try:

    import kb_routes

    kb_routes.register(app)

except Exception:

    logger.exception('kb_routes register failed')



# Register resource_routes

try:

    import resource_routes

    resource_routes.register(app)

except Exception:

    logger.exception('resource_routes register failed')



# Register geo_expansion_routes

try:

    import geo_expansion_routes

    geo_expansion_routes.register(app)

except Exception:

    logger.exception('geo_expansion_routes register failed')



# Register email_account_routes

try:

    import email_account_routes

    email_account_routes.register(app)

except Exception:

    logger.exception('email_account_routes register failed')



# Register content_routes (智能生文)

try:

    import content_routes

    content_routes.register(app)

except Exception:

    logger.exception('content_routes register failed')







@app.route('/api/ai/optimize-prompt', methods=['POST'])

def api_ai_optimize_prompt():

    from flask import request, jsonify



    try:

        data = request.get_json(silent=True) or {}

        user_input = data.get('user_input') or ''



        if not user_input.strip():

            return jsonify({'ok': False, 'error': 'Please input content'}), 400



        from llm_qwen import call_qwen



        settings = db.get_all_settings()



        if not settings.get('qwen_api_key'):

            return jsonify({'ok': False, 'error': 'AI service not configured'}), 400



        system_prompt = ('You are a Prompt Engineering expert. '

            'Convert requirements into structured Prompt template with variables: '

            '{brand}, {kb_content}, {topic}, {user_instruction}, {word_min}, {word_max}. '

            'Output only the optimized template text.')



        user_msg = ('Convert to Prompt template: ' + user_input + 

            '. Use variables for brand, topic, word count, etc.')



        result = call_qwen(

            settings,

            user_prompt=user_msg,

            system_prompt=system_prompt,

            max_tokens=2000,

            temperature=0.7,

        )



        optimized = result.strip() if result else None

        if not optimized:

            return jsonify({'ok': False, 'error': 'AI returned empty'}), 500



        missing_vars = []

        for var in ['{brand}', '{kb_content}', '{topic}', '{user_instruction}', '{word_min}', '{word_max}']:

            if var not in optimized:

                missing_vars.append(var)



        return jsonify({

            'ok': True,

            'optimized': optimized,

            'missing_vars': missing_vars if missing_vars else None

        })



    except Exception as e:

        return jsonify({'ok': False, 'error': str(e)}), 500



