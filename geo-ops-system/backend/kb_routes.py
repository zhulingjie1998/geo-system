"""kb_routes.py — 客户知识库 v2 routes (基础资料 + 多版本 + AI 生成 + 人工迭代)

挂载方式：在 app.py 末尾加 `kb_routes.register(app)`
"""

from __future__ import annotations

import json
import logging
import threading
from flask import jsonify, request, session, abort

import access_scope
import db
import kb_service as svc
import llm_claude
import llm_qwen

logger = logging.getLogger("kb_routes")

# 入口 A/B(从竞争分析报告 / 上传报告导入)的内存任务态。
# 注:与 DB 持久化的 kb_gen_task 是两套存储,前端轮询 /api/kb/task/<id> 走 DB,
# 此 dict 仅供这两条旧路径自身记录,跨 worker 不可见(历史遗留,按现状保留)。
_gen_tasks: dict = {}


def _require_login():
    if not session.get("user_id"):
        abort(401)


def _guard_account(account_id):
    """客户归属校验:无权访问 → 403。"""
    if not access_scope.can_access_account(account_id):
        abort(403)


def _guard_version(kb_id):
    """取 KB 版本并校验归属;不存在返回 None(调用方 404),越权 abort(403)。"""
    v = svc.get_version(kb_id)
    if not v:
        return None
    _guard_account(v.get("account_id"))
    return v


def _guard_source(src_id):
    """取资料并校验归属;不存在返回 None,越权 abort(403)。"""
    s = svc.get_source_text(src_id)
    if not s:
        return None
    _guard_account(s.get("account_id"))
    return s


def register(app):
    @app.get("/api/kb/source/list")
    def kb_source_list():
        _require_login()
        try:
            account_id = int(request.args.get("account_id"))
        except (TypeError, ValueError):
            return jsonify({"error": "account_id 必填"}), 400
        _guard_account(account_id)
        kb_version_id = request.args.get("kb_version_id")
        kvid = int(kb_version_id) if kb_version_id else None
        rows = svc.list_sources(account_id, kvid)
        return jsonify({"items": rows})

    @app.post("/api/kb/source/upload")
    def kb_source_upload():
        _require_login()
        try:
            account_id = int(request.form.get("account_id"))
        except (TypeError, ValueError):
            return jsonify({"error": "account_id 必填"}), 400
        _guard_account(account_id)
        kvid_raw = request.form.get("kb_version_id")
        kb_version_id = int(kvid_raw) if kvid_raw else None
        files = request.files.getlist("files")
        if not files:
            return jsonify({"error": "未上传文件"}), 400

        results = []
        errors = []
        for f in files:
            try:
                row = svc.save_uploaded_file(account_id, kb_version_id,
                                              f.filename, f.read())
                results.append(row)
            except Exception as e:
                errors.append({"file_name": f.filename, "error": str(e)})

        # 上传完成后，自动为每个成功保存的资料启动智能识别离线任务
        recognize_tasks = []
        for row in results:
            src_id = row.get("id")
            if not src_id:
                continue
            try:
                # 创建离线任务
                import uuid as _uuid
                task_id = str(_uuid.uuid4())
                file_name = row.get("file_name") or ""
                hint = f"智能识别中：{file_name}"
                _task_create(task_id, account_id, hint=hint)
                db._exec(db.get_conn(),
                    "UPDATE kb_gen_task SET task_type='recognize', source_id=%s WHERE id=%s",
                    (src_id, task_id))
                db.get_conn().commit()

                # 先等解析完成，再触发识别
                threading.Thread(
                    target=_do_parse_then_recognize,
                    args=(task_id, src_id, file_name),
                    daemon=True,
                ).start()
                recognize_tasks.append({"task_id": task_id, "source_id": src_id, "file_name": file_name})
            except Exception as e:
                logger.exception("auto recognize trigger failed src=%s", src_id)

        return jsonify({"saved": results, "errors": errors, "recognize_tasks": recognize_tasks})

    @app.get("/api/kb/source/<int:src_id>/text")
    def kb_source_text(src_id):
        _require_login()
        row = _guard_source(src_id)
        if not row:
            return jsonify({"error": "资料不存在"}), 404
        return jsonify(row)

    @app.delete("/api/kb/source/<int:src_id>")
    def kb_source_delete(src_id):
        _require_login()
        if not _guard_source(src_id):
            return jsonify({"error": "资料不存在"}), 404
        ok = svc.delete_source(src_id)
        return jsonify({"ok": ok})

    @app.post("/api/kb/source/<int:src_id>/reparse")
    def kb_source_reparse(src_id):
        _require_login()
        if not _guard_source(src_id):
            return jsonify({"error": "资料不存在"}), 404
        try:
            return jsonify(svc.reparse_source(src_id))
        except Exception as e:
            logger.exception("kb source reparse failed")
            return jsonify({"error": str(e)}), 500

    @app.post("/api/kb/source/<int:src_id>/recognize")
    def kb_source_recognize(src_id):
        """触发 Qwen3.7 智能识别，创建离线任务。"""
        _require_login()
        row = _guard_source(src_id)
        if not row:
            return jsonify({"error": "资料不存在"}), 404
        try:
            result = svc.recognize_source(src_id)
        except ValueError as e:
            return jsonify({"error": str(e)}), 400
        except Exception as e:
            logger.exception("kb source recognize failed")
            return jsonify({"error": str(e)}), 500

        # 创建离线任务（复用 kb_gen_task 表，task_type='recognize'）
        import uuid
        task_id = str(uuid.uuid4())
        account_id = row.get("account_id")
        file_name = row.get("file_name") or ""
        hint = f"智能识别中：{file_name}"
        _task_create(task_id, account_id, hint=hint)
        # 标记任务类型和关联资料
        db._exec(db.get_conn(),
            "UPDATE kb_gen_task SET task_type='recognize', source_id=%s WHERE id=%s",
            (src_id, task_id))
        db.get_conn().commit()

        # 后台轮询识别状态，完成后更新任务
        threading.Thread(
            target=_do_recognize_wait,
            args=(task_id, src_id),
            daemon=True,
        ).start()

        return jsonify({"task_id": task_id, "source_id": src_id, "ai_status": "running"})

    @app.get("/api/kb/source/<int:src_id>/ai-text")
    def kb_source_ai_text(src_id):
        """获取资料的 AI 识别文本。"""
        _require_login()
        if not _guard_source(src_id):
            return jsonify({"error": "资料不存在"}), 404
        row = svc.get_source_ai_text(src_id)
        if not row:
            return jsonify({"error": "资料不存在"}), 404
        return jsonify(row)

    # ─── 知识库版本 ───
    @app.get("/api/kb/versions")
    def kb_versions():
        _require_login()
        try:
            account_id = int(request.args.get("account_id"))
        except (TypeError, ValueError):
            return jsonify({"error": "account_id 必填"}), 400
        _guard_account(account_id)
        rows = svc.list_versions(account_id)
        return jsonify({"items": rows})

    @app.get("/api/kb/version/<int:kb_id>")
    def kb_version_detail(kb_id):
        _require_login()
        row = _guard_version(kb_id)
        if not row:
            return jsonify({"error": "版本不存在"}), 404
        return jsonify(row)

    @app.get("/api/kb/current")
    def kb_current():
        _require_login()
        try:
            account_id = int(request.args.get("account_id"))
        except (TypeError, ValueError):
            return jsonify({"error": "account_id 必填"}), 400
        _guard_account(account_id)
        # follow_share=1(智能生文等只读方):本账号无 KB 且数据共享勾了 kb → 用来源账号的 KB
        eff_id = account_id
        if (request.args.get("follow_share") or "").strip() in ("1", "true"):
            eff_id = svc.resolve_kb_account(account_id)
        row = svc.get_current_version(eff_id)
        if not row:
            return jsonify({"item": None})
        if eff_id != account_id:
            src_acc = db.get_account(eff_id) or {}
            row["sharedFrom"] = {"accountId": eff_id, "companyName": src_acc.get("companyName", "")}
        return jsonify({"item": row})

    @app.post("/api/kb/version/<int:kb_id>/set-current")
    def kb_set_current(kb_id):
        _require_login()
        v = _guard_version(kb_id)
        if not v:
            return jsonify({"error": "版本不存在"}), 404
        ok = svc.set_current_version(v["account_id"], kb_id)
        return jsonify({"ok": ok})

    @app.delete("/api/kb/version/<int:kb_id>")
    def kb_version_delete(kb_id):
        _require_login()
        if not _guard_version(kb_id):
            return jsonify({"error": "版本不存在"}), 404
        ok = svc.delete_version(kb_id)
        return jsonify({"ok": ok})

    @app.post("/api/kb/version/<int:kb_id>/proofread")
    def kb_proofread(kb_id):
        """用最新规则库(account_writing_lesson)校对该知识库版本,返回逐条冲突。"""
        _require_login()
        if not _guard_version(kb_id):
            return jsonify({"error": "版本不存在"}), 404
        try:
            return jsonify(svc.proofread_against_rules(kb_id))
        except ValueError as e:
            return jsonify({"error": str(e)}), 400
        except Exception as e:
            logger.exception("kb proofread failed")
            return jsonify({"error": "校对失败: " + str(e)}), 500

    # ─── 生成 / 迭代（异步任务，DB 持久化跨 worker + 跨刷新可见）───
    import db

    def _now():
        from datetime import datetime
        return datetime.now().strftime("%Y-%m-%d %H:%M:%S")

    def _task_create(task_id, account_id, hint=""):
        conn = db.get_conn()
        db._exec(conn,
            """INSERT INTO kb_gen_task (id, account_id, status, hint, created_at, updated_at)
               VALUES (%s, %s, 'running', %s, %s, %s)""",
            (task_id, int(account_id), hint or "", _now(), _now()))
        conn.commit()

    def _task_done(task_id, kb_id, version):
        conn = db.get_conn()
        db._exec(conn,
            """UPDATE kb_gen_task
               SET status='done', kb_id=%s, version=%s, updated_at=%s
               WHERE id=%s""",
            (int(kb_id), int(version), _now(), task_id))
        conn.commit()

    def _task_fail(task_id, err):
        conn = db.get_conn()
        db._exec(conn,
            """UPDATE kb_gen_task SET status='failed', error=%s, updated_at=%s WHERE id=%s""",
            (str(err)[:500], _now(), task_id))
        conn.commit()

    def _task_get(task_id):
        return db._fetchone(db.get_conn(),
            """SELECT id, account_id, status, hint, kb_id, version, error,
                      created_at, updated_at, task_type, source_id
               FROM kb_gen_task WHERE id=%s""", (task_id,))

    def _do_generate(task_id, account_id, instruction, source_ids,
                     reference_brand_report_id=None, reference_uploaded_report=None):
        try:
            r = svc.generate_kb_first(
                account_id, instruction, source_ids,
                reference_brand_report_id=reference_brand_report_id,
                reference_uploaded_report=reference_uploaded_report,
            )
            _task_done(task_id, r["id"], r["version"])
        except Exception as e:
            logger.exception("kb generate failed")
            _task_fail(task_id, str(e))

    def _do_refine(task_id, prev_kb_id, new_instruction, edited_content, additional_source_ids):
        try:
            r = svc.refine_kb(prev_kb_id, new_instruction, edited_content, additional_source_ids)
            _task_done(task_id, r["id"], r["version"])
        except Exception as e:
            logger.exception("kb refine failed")
            _task_fail(task_id, str(e))

    def _do_expand(task_id, prev_kb_id, new_instruction, additional_source_ids, add_count):
        try:
            r = svc.expand_kb(prev_kb_id, new_instruction, additional_source_ids, add_count)
            _task_done(task_id, r["id"], r["version"])
        except Exception as e:
            logger.exception("kb expand failed")
            _task_fail(task_id, str(e))

    def _do_generate_qwen(task_id, account_id, instruction, source_ids, model=None):
        """使用 Qwen 模型生成知识库的异步执行函数。"""
        try:
            r = svc.generate_kb_first_qwen(
                account_id, instruction, source_ids,
                model=model,
            )
            _task_done(task_id, r["id"], r["version"])
        except Exception as e:
            logger.exception("kb qwen generate failed")
            _task_fail(task_id, str(e))

    def _do_recognize_wait(task_id, src_id):
        """轮询资料识别状态，完成后更新离线任务为 done。"""
        import time
        max_wait = 600  # 最多等 10 分钟
        interval = 3
        elapsed = 0
        while elapsed < max_wait:
            row = svc.get_source_ai_text(src_id)
            if not row:
                _task_fail(task_id, "资料不存在")
                return
            ai_status = row.get("ai_status") or "pending"
            if ai_status == "done":
                # 更新任务 hint 并标记完成
                file_name = row.get("file_name") or ""
                db._exec(db.get_conn(),
                    "UPDATE kb_gen_task SET status='done', hint=%s, updated_at=%s WHERE id=%s",
                    (f"智能识别完成：{file_name}", _now(), task_id))
                db.get_conn().commit()
                return
            if ai_status == "failed":
                ai_text = row.get("ai_text") or "识别失败"
                _task_fail(task_id, ai_text[:500])
                return
            # 更新 updated_at 防止被僵尸清理
            db._exec(db.get_conn(),
                "UPDATE kb_gen_task SET updated_at=%s WHERE id=%s",
                (_now(), task_id))
            db.get_conn().commit()
            time.sleep(interval)
            elapsed += interval
        _task_fail(task_id, "识别超时（10 分钟）")

    def _do_parse_then_recognize(task_id, src_id, file_name):
        """等待资料解析完成后自动触发 Qwen 智能识别。"""
        import time
        max_wait_parse = 300  # 最多等解析 5 分钟
        interval = 3
        elapsed = 0

        # 阶段 1：等待解析完成
        while elapsed < max_wait_parse:
            row = svc.get_source_text(src_id)
            if not row:
                _task_fail(task_id, "资料不存在")
                return
            parser_status = row.get("parser_status") or "pending"
            if parser_status == "done":
                break
            if parser_status == "failed":
                _task_fail(task_id, f"文件解析失败：{row.get('parser_error') or '未知错误'}")
                return
            # 更新 updated_at 防止僵尸清理
            db._exec(db.get_conn(),
                "UPDATE kb_gen_task SET updated_at=%s WHERE id=%s",
                (_now(), task_id))
            db.get_conn().commit()
            time.sleep(interval)
            elapsed += interval
        else:
            _task_fail(task_id, "文件解析超时（5 分钟）")
            return

        # 阶段 2：触发智能识别
        try:
            svc.recognize_source(src_id)
        except Exception as e:
            _task_fail(task_id, f"触发识别失败：{e}")
            return

        # 阶段 3：轮询识别完成
        max_wait_recognize = 600  # 最多等识别 10 分钟
        elapsed = 0
        while elapsed < max_wait_recognize:
            row = svc.get_source_ai_text(src_id)
            if not row:
                _task_fail(task_id, "资料不存在")
                return
            ai_status = row.get("ai_status") or "pending"
            if ai_status == "done":
                db._exec(db.get_conn(),
                    "UPDATE kb_gen_task SET status='done', hint=%s, updated_at=%s WHERE id=%s",
                    (f"智能识别完成：{file_name}", _now(), task_id))
                db.get_conn().commit()
                return
            if ai_status == "failed":
                ai_text = row.get("ai_text") or "识别失败"
                _task_fail(task_id, ai_text[:500])
                return
            db._exec(db.get_conn(),
                "UPDATE kb_gen_task SET updated_at=%s WHERE id=%s",
                (_now(), task_id))
            db.get_conn().commit()
            time.sleep(interval)
            elapsed += interval
        _task_fail(task_id, "识别超时（10 分钟）")

    @app.post("/api/kb/generate")
    def kb_generate():
        """生成 KB v1。

        支持 multipart/form-data（含可选 ref_report_file）或 application/json。
        字段：
          - account_id (int)
          - instruction (str, 可空)
          - source_ids (list[int])  必须 > 0
          - reference_brand_report_id (int, 可空) 该客户已完成 brand 报告 id
          - ref_report_file (file, 可空) 上传外部分析报告 HTML/PDF/DOCX
        """
        _require_login()
        # 支持两种 content-type
        if request.content_type and request.content_type.startswith("multipart/"):
            try:
                account_id = int(request.form.get("account_id"))
            except (TypeError, ValueError):
                return jsonify({"error": "account_id 必填"}), 400
            instruction = (request.form.get("instruction") or "").strip()
            sids_raw = request.form.get("source_ids") or ""
            try:
                source_ids = [int(x) for x in json.loads(sids_raw) if str(x).isdigit()]
            except Exception:
                source_ids = [int(x) for x in sids_raw.split(",") if x.strip().isdigit()]
            ref_id_raw = request.form.get("reference_brand_report_id")
            reference_brand_report_id = int(ref_id_raw) if ref_id_raw and ref_id_raw.isdigit() else None
            f = request.files.get("ref_report_file")
            reference_uploaded_report = (f.filename, f.read()) if f and f.filename else None
        else:
            data = request.get_json(silent=True) or {}
            try:
                account_id = int(data.get("account_id"))
            except (TypeError, ValueError):
                return jsonify({"error": "account_id 必填"}), 400
            instruction = (data.get("instruction") or "").strip()
            source_ids = [int(x) for x in (data.get("source_ids") or []) if str(x).isdigit()]
            ref_id = data.get("reference_brand_report_id")
            reference_brand_report_id = int(ref_id) if ref_id else None
            reference_uploaded_report = None  # JSON 模式不支持文件

        _guard_account(account_id)
        if not source_ids:
            return jsonify({"error": "未选择资料"}), 400

        import uuid
        task_id = str(uuid.uuid4())
        # 拼 hint 用品牌名优先：「极核 · 知识库 生成中（素材 N 份 + 报告）」
        try:
            acc = db.get_account(account_id)
            primary = ""
            if acc:
                cb = acc.get("companyBrand") or ""
                if isinstance(cb, list):
                    primary = cb[0] if cb else ""
                elif isinstance(cb, str) and cb.strip().startswith("["):
                    try:
                        arr = json.loads(cb)
                        primary = arr[0] if arr else ""
                    except Exception:
                        primary = cb
                else:
                    primary = str(cb or "")
                primary = primary or acc.get("companyName") or ""
        except Exception:
            primary = ""
        ref_hint = ""
        if reference_brand_report_id:
            ref_hint += " + 已有报告"
        if reference_uploaded_report:
            ref_hint += " + 上传报告"
        prefix = f"{primary} · 知识库" if primary else "知识库"
        hint = f"{prefix} 生成中（素材 {len(source_ids)} 份{ref_hint}）"
        _task_create(task_id, account_id, hint=hint)
        threading.Thread(
            target=_do_generate,
            args=(task_id, account_id, instruction, source_ids,
                  reference_brand_report_id, reference_uploaded_report),
            daemon=True,
        ).start()
        return jsonify({"task_id": task_id, "status": "running"})

    @app.post("/api/kb/generate-qwen")
    def kb_generate_qwen():
        """使用通义千问 (Qwen) 生成知识库 v1。

        接口与 /api/kb/generate 类似，但使用 Qwen 模型。
        字段：
          - account_id (int) 必填
          - instruction (str, 可空) 补充说明
          - source_ids (list[int]) 资料 ID 列表
          - model (str, 可选) 覆盖默认模型，如 qwen-max、qwen-plus
        """
        _require_login()
        data = request.get_json(silent=True) or {}
        try:
            account_id = int(data.get("account_id"))
        except (TypeError, ValueError):
            return jsonify({"error": "account_id 必填"}), 400
        instruction = (data.get("instruction") or "").strip()
        source_ids = [int(x) for x in (data.get("source_ids") or []) if str(x).isdigit()]
        model = (data.get("model") or "").strip() or None

        _guard_account(account_id)
        if not source_ids:
            return jsonify({"error": "未选择资料"}), 400

        import uuid
        task_id = str(uuid.uuid4())

        try:
            acc = db.get_account(account_id)
            primary = (acc.get("companyBrand") or "") if acc else ""
            if isinstance(primary, list):
                primary = primary[0] if primary else ""
            primary = primary or (acc.get("companyName") or "") if acc else ""
        except Exception:
            primary = ""

        prefix = f"{primary} · 知识库" if primary else "知识库"
        hint = f"{prefix} AI 生成中（Qwen · 素材 {len(source_ids)} 份）"
        _task_create(task_id, account_id, hint=hint)

        threading.Thread(
            target=_do_generate_qwen,
            args=(task_id, account_id, instruction, source_ids, model),
            daemon=True,
        ).start()
        return jsonify({"task_id": task_id, "status": "running", "provider": "qwen"})

    @app.post("/api/kb/llm/test")
    def kb_llm_test():
        """用系统设置里的 LLM 配置做一个最小连通性测试。"""
        _require_login()
        try:
            data = request.get_json(silent=True) or {}
            mode = (data.get("mode") or db.get_setting("llm_api_mode", "qwen") or "qwen").strip().lower()
            prompt = data.get("prompt") or "请只返回一句话：连接测试成功"
            settings = db.get_all_settings()
            model = data.get("model") or settings.get(f"{mode}_model_name") or settings.get("llm_model_name") or "qwen-plus"
            text = svc.call_llm_by_settings(settings, prompt, max_tokens=80, timeout=30, mode=mode, model=model)
            return jsonify({"ok": True, "provider": mode, "model": model, "text": text[:500]})
        except Exception as e:
            logger.exception("kb llm test failed")
            return jsonify({"ok": False, "error": str(e)}), 500

    @app.post("/api/kb/refine/<int:prev_kb_id>")
    def kb_refine(prev_kb_id):
        _require_login()
        data = request.get_json(silent=True) or {}
        new_instruction = (data.get("instruction") or "").strip()
        edited_content = data.get("content") or ""
        additional_source_ids = [int(x) for x in (data.get("additional_source_ids") or []) if str(x).isdigit()]
        if not new_instruction:
            return jsonify({"error": "新要求 instruction 必填"}), 400

        import uuid
        task_id = str(uuid.uuid4())
        # refine 通过 prev_kb 反查 account_id
        prev = svc.get_version(prev_kb_id)
        if not prev:
            return jsonify({"error": "原版本不存在"}), 404
        acct_id = (prev or {}).get("account_id") or 0
        _guard_account(acct_id)
        try:
            acc = db.get_account(acct_id)
            primary = ""
            if acc:
                cb = acc.get("companyBrand") or ""
                if isinstance(cb, list):
                    primary = cb[0] if cb else ""
                elif isinstance(cb, str) and cb.strip().startswith("["):
                    try:
                        arr = json.loads(cb)
                        primary = arr[0] if arr else ""
                    except Exception:
                        primary = cb
                else:
                    primary = str(cb or "")
                primary = primary or acc.get("companyName") or ""
        except Exception:
            primary = ""
        prefix = f"{primary} · 知识库" if primary else "知识库"
        prev_v = (prev or {}).get('version', '')
        _task_create(task_id, acct_id, hint=f"{prefix} 优化中（基于 v{prev_v}）")
        threading.Thread(target=_do_refine,
                         args=(task_id, prev_kb_id, new_instruction, edited_content, additional_source_ids),
                         daemon=True).start()
        return jsonify({"task_id": task_id, "status": "running"})

    @app.post("/api/kb/expand/<int:prev_kb_id>")
    def kb_expand(prev_kb_id):
        """AI 扩充:在当前版本基础上新增 N 个全新模块。"""
        _require_login()
        data = request.get_json(silent=True) or {}
        new_instruction = (data.get("instruction") or "").strip()
        additional_source_ids = [int(x) for x in (data.get("additional_source_ids") or []) if str(x).isdigit()]
        try:
            add_count = max(1, min(int(data.get("add_count") or 3), 10))
        except (TypeError, ValueError):
            add_count = 3
        prev = svc.get_version(prev_kb_id)
        if not prev:
            return jsonify({"error": "当前版本不存在"}), 404
        acct_id = (prev or {}).get("account_id") or 0
        _guard_account(acct_id)
        import uuid
        task_id = str(uuid.uuid4())
        prev_v = (prev or {}).get("version", "")
        _task_create(task_id, acct_id, hint=f"知识库 扩充中（+{add_count} 模块，基于 v{prev_v}）")
        threading.Thread(target=_do_expand,
                         args=(task_id, prev_kb_id, new_instruction, additional_source_ids, add_count),
                         daemon=True).start()
        return jsonify({"task_id": task_id, "status": "running"})

    @app.get("/api/kb/task/<task_id>")
    def kb_task_status(task_id):
        _require_login()
        t = _task_get(task_id)
        if not t:
            return jsonify({"status": "not_found"}), 404
        _guard_account(t.get("account_id"))
        # 兼容旧前端字段名
        return jsonify({
            "status": t["status"],
            "kb_id": t.get("kb_id"),
            "version": t.get("version"),
            "error": t.get("error") or "",
            "hint": t.get("hint") or "",
            "account_id": t.get("account_id"),
            "created_at": t.get("created_at"),
            "updated_at": t.get("updated_at"),
        })

    @app.get("/api/kb/active-tasks")
    def kb_active_tasks():
        """返回当前账户（或全部）正在运行的 KB 任务，前端刷新后用于恢复进度 dialog。"""
        _require_login()
        acct = request.args.get("account_id")
        if acct and str(acct).isdigit():
            _guard_account(int(acct))
            rows = db._fetchall(db.get_conn(),
                """SELECT id, account_id, status, hint, kb_id, version, error,
                          created_at, updated_at, task_type, source_id
                   FROM kb_gen_task
                   WHERE status='running' AND account_id=%s
                   ORDER BY created_at DESC""", (int(acct),))
        else:
            rows = db._fetchall(db.get_conn(),
                """SELECT id, account_id, status, hint, kb_id, version, error,
                          created_at, updated_at, task_type, source_id
                   FROM kb_gen_task
                   WHERE status='running'
                   ORDER BY created_at DESC LIMIT 20""")
            # 无客户筛选时,只保留有权访问的客户任务
            rows = access_scope.filter_accounts(rows, "account_id")
        # 自动清理 30 分钟还没完成的（视为僵尸 — worker 挂或超时）
        from datetime import datetime, timedelta
        cutoff = (datetime.now() - timedelta(minutes=30)).strftime("%Y-%m-%d %H:%M:%S")
        alive = []
        for r in rows:
            if (r.get("updated_at") or "") < cutoff:
                # 标记 failed 不返回
                try:
                    db._exec(db.get_conn(),
                        "UPDATE kb_gen_task SET status='failed', error='超时 30 分钟无更新（视为崩溃）', updated_at=%s WHERE id=%s",
                        (datetime.now().strftime("%Y-%m-%d %H:%M:%S"), r["id"]))
                    db.get_conn().commit()
                except Exception:
                    pass
                continue
            alive.append(r)
        return jsonify({"items": alive})

    @app.post("/api/kb/save-human")
    def kb_save_human():
        """人工编辑直接保存为新版本（不调 LLM）"""
        _require_login()
        data = request.get_json(silent=True) or {}
        try:
            prev_kb_id = int(data.get("prev_kb_id"))
        except (TypeError, ValueError):
            return jsonify({"error": "prev_kb_id 必填"}), 400
        if not _guard_version(prev_kb_id):
            return jsonify({"error": "原版本不存在"}), 404
        content = data.get("content") or ""
        comment = data.get("comment") or ""
        if not content.strip():
            return jsonify({"error": "content 必填"}), 400
        try:
            r = svc.save_human_edit(prev_kb_id, content, comment)
            return jsonify(r)
        except Exception as e:
            logger.exception("kb save human failed")
            return jsonify({"error": str(e)}), 500

    @app.post("/api/kb/import-human")
    def kb_import_human():
        """把离线定稿的 KB markdown 直接导入为该客户的新版本（无需前一版）。"""
        _require_login()
        data = request.get_json(silent=True) or {}
        try:
            account_id = int(data.get("account_id"))
        except (TypeError, ValueError):
            return jsonify({"error": "account_id 必填"}), 400
        _guard_account(account_id)
        content = data.get("content") or ""
        comment = data.get("comment") or ""
        if not content.strip():
            return jsonify({"error": "content 必填"}), 400
        try:
            r = svc.import_human_kb(account_id, content, comment)
            return jsonify(r)
        except Exception as e:
            logger.exception("kb import human failed")
            return jsonify({"error": str(e)}), 500

    @app.get("/api/kb/customer-overview")
    def kb_customer_overview():
        """所有客户 + KB 摘要，「查看已有 KB」dialog 用。按可见客户过滤。"""
        _require_login()
        rows = access_scope.filter_accounts(svc.customer_kb_overview(), "account_id", "id")
        return jsonify({"items": rows})

    # ─── 入口 A/B：从竞争分析报告导入 12 类资料清单 ───
    def _do_from_brand_report(task_id, account_id, report_id):
        try:
            r = svc.kb_from_brand_report(account_id, report_id)
            _gen_tasks[task_id] = {"status": "done", "kb_id": r["id"], "version": r["version"]}
        except Exception as e:
            logger.exception("kb from brand report failed")
            _gen_tasks[task_id] = {"status": "failed", "error": str(e)[:500]}

    def _do_from_uploaded_report(task_id, account_id, file_name, file_bytes):
        try:
            r = svc.kb_from_uploaded_report(account_id, file_name, file_bytes)
            _gen_tasks[task_id] = {"status": "done", "kb_id": r["id"], "version": r["version"]}
        except Exception as e:
            logger.exception("kb from uploaded report failed")
            _gen_tasks[task_id] = {"status": "failed", "error": str(e)[:500]}

    @app.get("/api/kb/brand-reports")
    def kb_list_brand_reports():
        """方式 A 用：列该账户已完成的 brand 报告，前端下拉选择。"""
        _require_login()
        try:
            account_id = int(request.args.get("account_id"))
        except (TypeError, ValueError):
            return jsonify({"error": "account_id 必填"}), 400
        _guard_account(account_id)
        rows = svc.list_brand_reports(account_id)
        return jsonify({"items": rows})

    @app.post("/api/kb/from-brand-report")
    def kb_from_brand_report():
        """方式 A：从已完成 brand 报告导入 12 类资料清单为新版本。"""
        _require_login()
        data = request.get_json(silent=True) or {}
        try:
            account_id = int(data.get("account_id"))
            report_id = int(data.get("report_id"))
        except (TypeError, ValueError):
            return jsonify({"error": "account_id 与 report_id 必填"}), 400
        _guard_account(account_id)

        import uuid
        task_id = str(uuid.uuid4())
        _gen_tasks[task_id] = {"status": "running"}
        threading.Thread(target=_do_from_brand_report,
                         args=(task_id, account_id, report_id), daemon=True).start()
        return jsonify({"task_id": task_id, "status": "running"})

    @app.post("/api/kb/from-uploaded-report")
    def kb_from_uploaded_report():
        """方式 B：用户上传外部分析报告（HTML/PDF/DOCX），LLM 抽取 12 类清单后入库。"""
        _require_login()
        try:
            account_id = int(request.form.get("account_id"))
        except (TypeError, ValueError):
            return jsonify({"error": "account_id 必填"}), 400
        _guard_account(account_id)
        f = request.files.get("file")
        if not f:
            return jsonify({"error": "未上传文件"}), 400
        file_name = f.filename or "uploaded_report"
        file_bytes = f.read()

        import uuid
        task_id = str(uuid.uuid4())
        _gen_tasks[task_id] = {"status": "running"}
        threading.Thread(target=_do_from_uploaded_report,
                         args=(task_id, account_id, file_name, file_bytes), daemon=True).start()
        return jsonify({"task_id": task_id, "status": "running"})

    # ─── 导出 PDF / DOCX ───
    from flask import Response

    @app.get("/api/kb/version/<int:kb_id>/export.pdf")
    def kb_export_pdf(kb_id):
        _require_login()
        if not _guard_version(kb_id):
            return jsonify({"error": "版本不存在"}), 404
        try:
            data, fname = svc.export_kb_pdf(kb_id)
        except Exception as e:
            logger.exception("kb pdf export failed")
            return jsonify({"error": str(e)}), 500
        from urllib.parse import quote
        return Response(data, mimetype="application/pdf",
            headers={"Content-Disposition":
                f"attachment; filename=KB.pdf; filename*=UTF-8''{quote(fname)}"})

    @app.get("/api/kb/version/<int:kb_id>/export.docx")
    def kb_export_docx(kb_id):
        _require_login()
        if not _guard_version(kb_id):
            return jsonify({"error": "版本不存在"}), 404
        try:
            data, fname = svc.export_kb_docx(kb_id)
        except Exception as e:
            logger.exception("kb docx export failed")
            return jsonify({"error": str(e)}), 500
        from urllib.parse import quote
        return Response(data, mimetype=
            "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
            headers={"Content-Disposition":
                f"attachment; filename=KB.docx; filename*=UTF-8''{quote(fname)}"})

    # ─── 知识库解析指令（系统设置用） ───
    @app.get("/api/kb/default-instruction")
    def kb_default_instruction():
        """返回默认的知识库解析指令模板，包含资料识别指令 + 知识库生成指令。"""
        _require_login()
        recognize_prompt = getattr(svc, "_RECOGNIZE_SYSTEM_PROMPT", "")
        combined = ""
        if recognize_prompt:
            combined += (
                "# ═══ 资料智能识别指令 ═══\n"
                "# 以下指令在 AI 识别基础资料时作为系统提示词使用\n\n"
                + recognize_prompt.strip()
                + "\n\n"
            )
        combined += (
            "# ═══ 知识库生成指令 ═══\n"
            "# 以下指令在 AI 生成/优化知识库时作为系统提示词使用\n\n"
            + svc.KB_PROMPT_FIRST
        )
        return jsonify({"instruction": combined})

    logger.info("kb_routes registered (18 endpoints)")
