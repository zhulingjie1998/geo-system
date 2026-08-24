"""客户知识库路由（Phase 1）。

在 app.py 末尾加 `import knowledge_routes; knowledge_routes.register(app)`。
"""
from __future__ import annotations

import logging

from flask import jsonify, request, session, abort

import access_scope
import knowledge_review_service as rsvc
import knowledge_service as svc

logger = logging.getLogger("knowledge_routes")


def _require_admin():
    if session.get("is_super_admin"):
        return
    role = session.get("role", "user")
    if role in ("super_admin", "admin"):
        return
    abort(403)


def _current_user_id() -> int | None:
    return session.get("user_id")


def _guard_account(account_id, *, allow_template_read: bool = False):
    """客户归属校验。
    account_id 为空 = 系统模板(account_id IS NULL):
      allow_template_read=True 时所有管理员可读;否则仅超管(写模板)。
    account_id 有值 → 按可见客户集判定。"""
    if account_id in (None, "", 0, "0"):
        if allow_template_read or access_scope.is_full_view():
            return
        abort(403)
    if not access_scope.can_access_account(account_id):
        abort(403)


def _guard_kb_read(kb_id):
    """读取知识条目:取出后按归属校验(模板可读)。返回条目或 None(404)。"""
    row = svc.get_knowledge(kb_id)
    if not row:
        return None
    _guard_account(row.get("account_id"), allow_template_read=True)
    return row


def _guard_kb_write(kb_id):
    """改/删知识条目:模板仅超管,客户条目按归属。返回条目或 None(404)。"""
    row = svc.get_knowledge(kb_id)
    if not row:
        return None
    _guard_account(row.get("account_id"))
    return row


def _guard_review(review_id):
    """审核归属校验:不存在 → 404,越权 → 403。"""
    acct = rsvc.account_of_review(review_id)
    if acct is None:
        abort(404)
    _guard_account(acct)


def _guard_annotation(anno_id):
    """批注归属校验:不存在 → 404,越权 → 403。"""
    acct = rsvc.account_of_annotation(anno_id)
    if acct is None:
        abort(404)
    _guard_account(acct)


def _parse_account_id(raw) -> int | None:
    if raw in (None, "", "null", "None"):
        return None
    try:
        v = int(raw)
        return v if v > 0 else None
    except (TypeError, ValueError):
        return None


def register(app):
    # ═══════════ 客户列表（仅正式客户，已登录即可） ═══════════
    @app.get("/api/kb/accounts")
    def api_kb_accounts():
        # 付费客户名单，被 KB/智能生文/内容库等模块共用，已登录即可。
        # ?formal=1 仅返回正式客户(智能生文/内容库用);默认含初始客户(知识库下拉用,
        # 因为初始客户正是要在知识库里建知识库)。
        if not session.get("user_id"):
            abort(401)
        formal_only = (request.args.get("formal") or "").strip() in ("1", "true", "yes")
        accounts = access_scope.filter_accounts(
            svc.list_paid_accounts(only_formal=formal_only), "id", "account_id")
        return jsonify({"accounts": accounts})

    # ═══════════ 列表 / 统计 ═══════════
    @app.get("/api/kb")
    def api_kb_list():
        _require_admin()
        account_id = _parse_account_id(request.args.get("account_id"))
        # account_id 指定客户 → 校验归属;None → 仅系统模板,所有管理员可读
        if account_id is not None:
            _guard_account(account_id)
        include_tpl = request.args.get("include_template", "1") != "0"
        kb_type = (request.args.get("type") or "").strip() or None
        status = (request.args.get("status") or "").strip() or None
        q = (request.args.get("q") or "").strip()
        tags_raw = (request.args.get("tags") or "").strip()
        tags = [t.strip() for t in tags_raw.split(",") if t.strip()] or None
        try:
            limit = min(int(request.args.get("limit", 50)), 200)
            offset = int(request.args.get("offset", 0))
        except ValueError:
            limit, offset = 50, 0
        try:
            return jsonify(svc.list_knowledge(
                account_id=account_id,
                include_template=include_tpl,
                kb_type=kb_type,
                status=status,
                q=q,
                tags=tags,
                limit=limit,
                offset=offset,
            ))
        except Exception as e:
            logger.exception("kb list failed")
            return jsonify({"error": str(e)}), 500

    @app.get("/api/kb/stats")
    def api_kb_stats():
        _require_admin()
        account_id = _parse_account_id(request.args.get("account_id"))
        if account_id is None:
            return jsonify({"error": "account_id 必填"}), 400
        _guard_account(account_id)
        return jsonify(svc.count_by_account(account_id))

    # ═══════════ 详情 / CRUD ═══════════
    @app.post("/api/kb")
    def api_kb_create():
        _require_admin()
        data = request.get_json(silent=True) or {}
        _guard_account(_parse_account_id(data.get("account_id")))
        try:
            return jsonify(svc.create_knowledge(data, user_id=_current_user_id()))
        except ValueError as e:
            return jsonify({"error": str(e)}), 400
        except Exception as e:
            logger.exception("kb create failed")
            return jsonify({"error": str(e)}), 500

    @app.get("/api/kb/<int:kb_id>")
    def api_kb_get(kb_id):
        _require_admin()
        row = _guard_kb_read(kb_id)
        if not row:
            return jsonify({"error": "条目不存在"}), 404
        return jsonify(row)

    @app.put("/api/kb/<int:kb_id>")
    def api_kb_update(kb_id):
        _require_admin()
        if not _guard_kb_write(kb_id):
            return jsonify({"error": "条目不存在"}), 404
        data = request.get_json(silent=True) or {}
        try:
            row = svc.update_knowledge(kb_id, data)
        except ValueError as e:
            return jsonify({"error": str(e)}), 400
        if not row:
            return jsonify({"error": "条目不存在"}), 404
        return jsonify(row)

    @app.delete("/api/kb/<int:kb_id>")
    def api_kb_delete(kb_id):
        _require_admin()
        if not _guard_kb_write(kb_id):
            return jsonify({"error": "条目不存在"}), 404
        ok = svc.delete_knowledge(kb_id)
        return jsonify({"ok": ok})

    # ═══════════ 批量导入 ═══════════
    @app.post("/api/kb/import/csv")
    def api_kb_import_csv():
        _require_admin()
        account_id = _parse_account_id(
            (request.get_json(silent=True) or {}).get("account_id")
            or request.form.get("account_id")
        )
        _guard_account(account_id)
        default_type = (
            (request.get_json(silent=True) or {}).get("kb_type")
            or request.form.get("kb_type")
            or "basic"
        )
        # 支持文件上传或文本粘贴
        csv_text = ""
        if request.files.get("file"):
            f = request.files["file"]
            csv_text = f.read().decode("utf-8", errors="ignore")
        else:
            data = request.get_json(silent=True) or {}
            csv_text = (data.get("csv") or "").strip()
        if not csv_text:
            return jsonify({"error": "csv 为空"}), 400
        try:
            return jsonify(svc.import_from_csv(
                account_id, csv_text,
                default_kb_type=default_type,
                user_id=_current_user_id(),
            ))
        except Exception as e:
            logger.exception("kb import csv failed")
            return jsonify({"error": str(e)}), 500

    @app.post("/api/kb/import/text")
    def api_kb_import_text():
        _require_admin()
        data = request.get_json(silent=True) or {}
        account_id = _parse_account_id(data.get("account_id"))
        _guard_account(account_id)
        text = (data.get("text") or "").strip()
        default_type = (data.get("kb_type") or "basic").strip()
        split_mode = (data.get("split_mode") or "heading").strip()
        if not text:
            return jsonify({"error": "text 为空"}), 400
        try:
            return jsonify(svc.import_from_text(
                account_id, text,
                default_kb_type=default_type,
                split_mode=split_mode,
                user_id=_current_user_id(),
            ))
        except Exception as e:
            logger.exception("kb import text failed")
            return jsonify({"error": str(e)}), 500

    @app.post("/api/kb/import/url")
    def api_kb_import_url():
        _require_admin()
        data = request.get_json(silent=True) or {}
        account_id = _parse_account_id(data.get("account_id"))
        _guard_account(account_id)
        url = (data.get("url") or "").strip()
        kb_type = (data.get("kb_type") or "basic").strip()
        if not url:
            return jsonify({"error": "url 必填"}), 400
        try:
            return jsonify(svc.import_from_url(
                account_id, url,
                kb_type=kb_type,
                user_id=_current_user_id(),
            ))
        except ValueError as e:
            return jsonify({"error": str(e)}), 400
        except Exception as e:
            logger.exception("kb import url failed")
            return jsonify({"error": str(e)}), 500

    # ═══════════ 知识库审核 ═══════════
    @app.post("/api/kb/review")
    def api_kb_review_start():
        _require_admin()
        data = request.get_json(silent=True) or {}
        account_id = _parse_account_id(data.get("account_id"))
        kb_version_id = data.get("kb_version_id")
        if account_id is None or not kb_version_id:
            return jsonify({"error": "account_id 与 kb_version_id 必填"}), 400
        _guard_account(account_id)
        try:
            review = rsvc.get_or_create_review(account_id, int(kb_version_id), _current_user_id())
            return jsonify(review)
        except ValueError as e:
            return jsonify({"error": str(e)}), 400
        except Exception as e:
            logger.exception("kb review start failed")
            return jsonify({"error": str(e)}), 500

    @app.get("/api/kb/review/<int:review_id>")
    def api_kb_review_get(review_id):
        _require_admin()
        review = rsvc.get_review(review_id)
        if not review:
            return jsonify({"error": "审核不存在"}), 404
        _guard_account(review.get("account_id"))
        return jsonify(review)

    @app.post("/api/kb/review/<int:review_id>/annotation")
    def api_kb_review_add_anno(review_id):
        _require_admin()
        _guard_review(review_id)
        data = request.get_json(silent=True) or {}
        try:
            anno = rsvc.add_annotation(
                review_id,
                category=(data.get("category") or "").strip(),
                quote=data.get("quote") or "",
                occurrence=int(data.get("occurrence") or 0),
                reason=data.get("reason") or "",
            )
            return jsonify(anno)
        except ValueError as e:
            return jsonify({"error": str(e)}), 400
        except Exception as e:
            logger.exception("kb anno add failed")
            return jsonify({"error": str(e)}), 500

    @app.put("/api/kb/review/annotation/<int:anno_id>")
    def api_kb_review_upd_anno(anno_id):
        _require_admin()
        _guard_annotation(anno_id)
        data = request.get_json(silent=True) or {}
        try:
            anno = rsvc.update_annotation(anno_id, data)
            if anno is None:
                return jsonify({"error": "无更新或批注不存在"}), 400
            return jsonify(anno)
        except ValueError as e:
            return jsonify({"error": str(e)}), 400

    @app.delete("/api/kb/review/annotation/<int:anno_id>")
    def api_kb_review_del_anno(anno_id):
        _require_admin()
        _guard_annotation(anno_id)
        rsvc.delete_annotation(anno_id)
        return jsonify({"ok": True})

    @app.put("/api/kb/review/<int:review_id>/materials")
    def api_kb_review_materials(review_id):
        _require_admin()
        _guard_review(review_id)
        data = request.get_json(silent=True) or {}
        review = rsvc.update_materials(review_id, data.get("materials") or [])
        if not review:
            return jsonify({"error": "审核不存在"}), 404
        return jsonify(review)

    @app.post("/api/kb/review/<int:review_id>/finalize")
    def api_kb_review_finalize(review_id):
        _require_admin()
        _guard_review(review_id)
        review = rsvc.finalize_review(review_id)
        if not review:
            return jsonify({"error": "审核不存在"}), 404
        return jsonify(review)

    # ═══════════ 审核分享(只读, review 级 token, 复用 weekly 分享鉴权模式) ═══════════
    @app.get("/api/share/kb-review/<int:account_id>/<int:review_id>")
    def api_share_kb_review(account_id, review_id):
        token = request.args.get("token", "")
        authorized = bool(session.get("user_id")) or rsvc.verify_share_token(review_id, token)
        if not authorized:
            return jsonify({"error": "密钥无效或审核未定稿"}), 403
        data = rsvc.get_share_data(account_id, review_id)
        if not data:
            return jsonify({"error": "审核不存在或未定稿"}), 404
        return jsonify(data)

    logger.info("knowledge_routes registered (18 endpoints)")
