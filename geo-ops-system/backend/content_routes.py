# -*- coding: utf-8 -*-
"""智能生文 — 路由层。

端点:
  POST /api/content/generate-topics  — 生成差异化主题列表
  POST /api/content/generate         — 生成单篇文章（同步）
  GET  /api/content/tasks            — 列出批次
  GET  /api/content/tasks/<id>       — 获取批次详情（含 drafts）
  GET  /api/content/llm-providers     — 获取可用模型列表
  GET  /api/content/drafts/<id>       — 获取单篇草稿内容
"""
from __future__ import annotations

import json
import logging

from flask import jsonify, request, session, abort

import access_scope
import content_service as svc
import db

logger = logging.getLogger(__name__)


def _require_login():
    if not session.get("user_id"):
        abort(401)


def _guard_account(account_id):
    if not access_scope.can_access_account(account_id):
        abort(403)


def register(app):
    # ============================================================
    # POST /api/content/generate-topics
    # ============================================================
    @app.post("/api/content/generate-topics")
    def content_generate_topics():
        _require_login()
        data = request.get_json(silent=True) or {}
        try:
            account_id = int(data.get("account_id"))
        except (TypeError, ValueError):
            return jsonify({"error": "account_id 必填"}), 400

        _guard_account(account_id)

        keywords = data.get("keywords") or []
        if not keywords:
            return jsonify({"error": "keywords 必填"}), 400

        kb_modules = data.get("kb_modules") or []
        count = int(data.get("count") or 1)
        prompt = data.get("prompt") or ""

        topics = svc.generate_topics(account_id, keywords, kb_modules, count, prompt)
        return jsonify({"topics": topics})

    # ============================================================
    # POST /api/content/generate
    # ============================================================
    @app.post("/api/content/generate")
    def content_generate():
        _require_login()
        data = request.get_json(silent=True) or {}
        try:
            account_id = int(data.get("account_id"))
        except (TypeError, ValueError):
            return jsonify({"error": "account_id 必填"}), 400

        _guard_account(account_id)

        instruction = (data.get("instruction") or "").strip()
        if not instruction:
            return jsonify({"error": "instruction 必填"}), 400

        model = (data.get("model") or "").strip() or None
        keyword = data.get("keyword") or ""
        topic_title = data.get("topic_title") or ""
        topic_angle = data.get("topic_angle") or ""
        supplement = data.get("supplement") or ""
        kb_module_ids = data.get("kb_module_ids") or []
        metadata = data.get("metadata") or {}

        # 注入 user_id
        metadata["user_id"] = session.get("user_id", 0)

        try:
            result = svc.generate_article(
                account_id=account_id,
                instruction=instruction,
                model=model,
                keyword=keyword,
                topic_title=topic_title,
                topic_angle=topic_angle,
                supplement=supplement,
                kb_module_ids=kb_module_ids,
                metadata=metadata,
            )
            return jsonify(result)
        except Exception as e:
            logger.exception("[content] generate failed: %s", e)
            return jsonify({"error": str(e)[:500]}), 500

    # ============================================================
    # GET /api/content/tasks — 列出批次
    # ============================================================
    @app.get("/api/content/tasks")
    def content_list_tasks():
        _require_login()
        account_id = request.args.get("account_id")
        if account_id:
            try:
                account_id = int(account_id)
            except (TypeError, ValueError):
                account_id = None

        if account_id:
            _guard_account(account_id)
            batches = svc.list_batches(account_id=account_id)
        else:
            # 超管看全部，否则只看自己有权的
            if access_scope.is_full_view():
                batches = svc.list_batches()
            else:
                ids = access_scope.accessible_account_ids()
                if ids is None:
                    batches = svc.list_batches()
                else:
                    batches = []
                    for aid in ids:
                        batches.extend(svc.list_batches(account_id=aid))
                    batches = batches[:50]

        # 附带每批次的 drafts 摘要
        result = []
        for b in batches:
            drafts = svc.list_drafts_by_batch(b["id"])
            result.append({
                "id": b["id"],
                "name": b.get("name", ""),
                "account_id": b["account_id"],
                "status": b["status"],
                "total_count": b["total_count"],
                "done_count": b.get("done_count", 0),
                "failed_count": b.get("failed_count", 0),
                "created_at": str(b.get("created_at", "")),
                "updated_at": str(b.get("updated_at", "")),
                "drafts": [
                    {
                        "id": d["id"],
                        "topic": d.get("topic", ""),
                        "title": d.get("title"),
                        "status": d.get("status"),
                        "word_count": d.get("word_count"),
                        "error_msg": d.get("error_msg"),
                    }
                    for d in drafts
                ],
            })
        return jsonify({"items": result})

    # ============================================================
    # GET /api/content/tasks/<id> — 获取批次详情
    # ============================================================
    @app.get("/api/content/tasks/<int:task_id>")
    def content_get_task(task_id):
        _require_login()
        batch = svc.get_batch(task_id)
        if not batch:
            return jsonify({"error": "not found"}), 404
        _guard_account(batch["account_id"])

        drafts = svc.list_drafts_by_batch(task_id)
        return jsonify({
            "id": batch["id"],
            "name": batch.get("name", ""),
            "account_id": batch["account_id"],
            "status": batch["status"],
            "total_count": batch["total_count"],
            "done_count": batch.get("done_count", 0),
            "failed_count": batch.get("failed_count", 0),
            "created_at": str(batch.get("created_at", "")),
            "updated_at": str(batch.get("updated_at", "")),
            "drafts": [dict(d) for d in drafts],
        })

    # ============================================================
    # GET /api/content/tasks/by-uuid/<uuid> — 按 UUID 查询
    # ============================================================
    @app.get("/api/content/tasks/by-uuid/<uuid_str>")
    def content_get_task_by_uuid(uuid_str):
        _require_login()
        # 目前不使用 UUID，返回空
        return jsonify({"error": "not found"}), 404

    # ============================================================
    # GET /api/content/tasks/<uuid>/poll — 轮询
    # ============================================================
    @app.get("/api/content/tasks/<uuid_str>/poll")
    def content_poll_task(uuid_str):
        _require_login()
        return jsonify({"error": "not found"}), 404

    # ============================================================
    # DELETE /api/content/tasks/<id>
    # ============================================================
    @app.delete("/api/content/tasks/<int:task_id>")
    def content_delete_task(task_id):
        _require_login()
        batch = svc.get_batch(task_id)
        if not batch:
            return jsonify({"error": "not found"}), 404
        _guard_account(batch["account_id"])

        with db.transaction() as conn:
            db._exec(conn, "DELETE FROM content_draft WHERE batch_id=%s", (task_id,))
            db._exec(conn, "DELETE FROM content_draft_batch WHERE id=%s", (task_id,))
        return jsonify({"ok": True})

    # ============================================================
    # GET /api/content/drafts/<id> — 获取单篇草稿
    # ============================================================
    @app.get("/api/content/drafts/<int:draft_id>")
    def content_get_draft(draft_id):
        _require_login()
        draft = svc.get_draft(draft_id)
        if not draft:
            return jsonify({"error": "not found"}), 404
        _guard_account(draft["account_id"])
        return jsonify(dict(draft))

    # ============================================================
    # GET /api/content/llm-providers — 获取可用模型
    # ============================================================
    @app.get("/api/content/llm-providers")
    def content_llm_providers():
        _require_login()
        settings = db.get_all_settings()
        model_name = settings.get("qwen_model_name") or "qwen-plus"
        return jsonify({
            "providers": [
                {
                    "id": "qwen",
                    "name": "通义千问",
                    "models": [{"value": model_name, "label": "通义千问"}],
                }
            ]
        })

    # ============================================================
    # 指令模板 CRUD（兼容前端，存储在 DB system_setting 中）
    # ============================================================
    @app.get("/api/content/templates")
    def content_list_templates():
        _require_login()
        # 模板存储在 localStorage，后端返回空列表（前端兼容）
        return jsonify({"items": []})

    @app.get("/api/content/templates/<int:template_id>")
    def content_get_template(template_id):
        _require_login()
        return jsonify({"error": "not found"}), 404

    @app.post("/api/content/templates")
    def content_create_template():
        _require_login()
        return jsonify({"error": "templates stored locally"}), 400

    @app.patch("/api/content/templates/<int:template_id>")
    def content_update_template(template_id):
        _require_login()
        return jsonify({"error": "templates stored locally"}), 400

    @app.delete("/api/content/templates/<int:template_id>")
    def content_delete_template(template_id):
        _require_login()
        return jsonify({"error": "templates stored locally"}), 400

    @app.post("/api/content/templates/ai-draft")
    def content_ai_draft_template():
        _require_login()
        return jsonify({"error": "not implemented"}), 400

    # ============================================================
    # 批量生文端点（预留）
    # ============================================================
    @app.get("/api/content/batch")
    def content_list_batches():
        _require_login()
        account_id = request.args.get("account_id")
        if account_id:
            try:
                account_id = int(account_id)
            except (TypeError, ValueError):
                account_id = None
        if account_id:
            _guard_account(account_id)
            batches = svc.list_batches(account_id=account_id)
        else:
            batches = svc.list_batches() if access_scope.is_full_view() else []
        return jsonify({"items": [dict(b) for b in batches]})

    @app.post("/api/content/batch")
    def content_create_batch():
        _require_login()
        data = request.get_json(silent=True) or {}
        try:
            account_id = int(data.get("account_id"))
        except (TypeError, ValueError):
            return jsonify({"error": "account_id 必填"}), 400
        _guard_account(account_id)

        user_id = session.get("user_id", 0)
        tasks = data.get("tasks") or []
        if not tasks:
            return jsonify({"error": "tasks 必填"}), 400

        # 创建批次
        batch_id = svc.create_batch(
            user_id=user_id,
            account_id=account_id,
            name=data.get("name") or f"批量生文 {len(tasks)}篇",
            template_id=0,
            llm_provider="qwen",
            kb_module_keys=json.dumps(data.get("kb_module_ids") or []),
            user_instruction=data.get("instruction") or "",
            word_min=data.get("word_min"),
            word_max=data.get("word_max"),
            source_kind="manual",
            source_topics=json.dumps([t.get("topic_title") for t in tasks]),
            total_count=len(tasks),
            gen_mode=data.get("gen_mode") or "type",
            focus_note=data.get("supplement") or "",
        )

        # 注入 user_id 到每个 task
        for t in tasks:
            t["user_id"] = user_id

        # 启动后台生成
        svc.start_batch_generate(batch_id=batch_id, tasks=tasks)

        return jsonify({"batch_id": batch_id, "status": "running", "total": len(tasks)})
