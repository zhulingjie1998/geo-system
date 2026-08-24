"""GEO 拓词模块路由。

提供：
- 拓词任务 CRUD
- 拓词任务列表（含统计概览）
- 创建/执行拓词任务
- 拓词结果查询
- 拓词指令配置读写
"""

from __future__ import annotations

import json
import logging
import time
from datetime import datetime

from flask import jsonify, request, session

import db

logger = logging.getLogger("gunicorn.error")


# ── 辅助函数 ─────────────────────────────────────────────────────────────


def _get_now() -> str:
    return datetime.now().strftime("%Y-%m-%d %H:%M:%S")


def _require_auth():
    """检查登录态"""
    uid = session.get("user_id")
    if not uid:
        return None
    return db.get_admin_user_by_id(int(uid))


def _json_error(msg: str, code: int = 400):
    return jsonify({"error": msg}), code


def _json_ok(data=None, msg="ok"):
    payload = {"code": 200, "message": msg}
    if data is not None:
        payload["data"] = data
    return jsonify(payload)


# ── 统计概览 ─────────────────────────────────────────────────────────────


def api_geo_expansion_overview():
    """数据概览：任务总数、已完成、进行中、累计提示词"""
    user = _require_auth()
    if not user:
        return _json_error("请先登录", 401)

    conn = db.get_conn()
    cur = conn.cursor()

    # 任务总数
    cur.execute("SELECT COUNT(*) AS cnt FROM geo_expansion_task")
    total_tasks = int(cur.fetchone()["cnt"] or 0)

    # 已完成
    cur.execute("SELECT COUNT(*) AS cnt FROM geo_expansion_task WHERE status='completed'")
    completed = int(cur.fetchone()["cnt"] or 0)

    # 进行中 (pending + running)
    cur.execute(
        "SELECT COUNT(*) AS cnt FROM geo_expansion_task WHERE status IN ('pending', 'running')"
    )
    running = int(cur.fetchone()["cnt"] or 0)

    # 累计提示词（已完成任务的 total_prompts 之和）
    cur.execute(
        "SELECT COALESCE(SUM(total_prompts), 0) AS total FROM geo_expansion_task WHERE status='completed'"
    )
    total_prompts = int(cur.fetchone()["total"] or 0)

    return _json_ok({
        "totalTasks": total_tasks,
        "completed": completed,
        "running": running,
        "totalPrompts": total_prompts,
    })


# ── 任务列表 ──────────────────────────────────────────────────────────────


def api_geo_expansion_task_list():
    """拓词任务列表"""
    user = _require_auth()
    if not user:
        return _json_error("请先登录", 401)

    status_filter = (request.args.get("status") or "").strip()

    sql = """
        SELECT t.*, a.company_name as account_name, a.company_brand as brand_name
        FROM geo_expansion_task t
        LEFT JOIN account a ON t.account_id = a.id
        WHERE 1=1
    """
    params = []

    if status_filter and status_filter != "all":
        sql += " AND t.status = %s"
        params.append(status_filter)

    sql += " ORDER BY t.created_at DESC"

    rows = db._fetchall(conn=db.get_conn(), sql=sql, args=params or None)

    result = []
    for r in rows:
        result.append({
            "id": r["id"],
            "accountId": r["account_id"],
            "accountName": r.get("account_name", ""),
            "brandName": r.get("brand_name") or "",
            "promptCount": r["prompt_count"],
            "includeBrand": bool(r["include_brand"]),
            "includeComparison": bool(r["include_comparison"]),
            "extraRequirements": r.get("extra_requirements", "") or "",
            "status": r["status"],
            "totalPrompts": r.get("total_prompts", 0),
            "errorMessage": r.get("error_message", "") or "",
            "createdAt": r.get("created_at", ""),
            "updatedAt": r.get("updated_at", ""),
            "completedAt": r.get("completed_at", ""),
        })

    return _json_ok(result)


# ── 创建任务 ──────────────────────────────────────────────────────────────


def api_geo_expansion_task_create():
    """创建拓词任务"""
    user = _require_auth()
    if not user:
        return _json_error("请先登录", 401)

    data = request.get_json(silent=True) or {}
    account_id = data.get("accountId")
    prompt_count = data.get("promptCount")
    include_brand = data.get("includeBrand", False)
    include_comparison = data.get("includeComparison", False)
    extra_requirements = (data.get("extraRequirements") or "")[:2000]

    # 校验
    if not account_id:
        return _json_error("请选择品牌（客户）")
    if not prompt_count or not isinstance(prompt_count, int) or prompt_count < 1 or prompt_count > 500:
        return _json_error("提示词条数必须是 1-500 的整数")

    # 获取品牌名称
    acc = db._fetchone(
        db.get_conn(),
        "SELECT company_name, company_brand FROM account WHERE id = %s",
        (account_id,)
    )
    if not acc:
        return _json_error("选择的客户不存在")
    brand_name = acc.get("company_brand") or acc.get("company_name") or ""

    now = _get_now()
    conn = db.get_conn()
    cur = conn.cursor()
    cur.execute(
        """INSERT INTO geo_expansion_task
           (account_id, brand_name, prompt_count, include_brand, include_comparison,
            extra_requirements, status, created_at, updated_at)
           VALUES (%s, %s, %s, %s, %s, %s, 'pending', %s, %s)""",
        (account_id, brand_name, prompt_count,
         1 if include_brand else 0, 1 if include_comparison else 0,
         extra_requirements, now, now)
    )
    task_id = cur.lastrowid
    conn.commit()

    return _json_ok({"taskId": task_id}, "任务创建成功")


# ── 执行任务（调用大模型） ───────────────────────────────────────────────


def api_geo_expansion_task_run(task_id: int):
    """启动拓词任务（异步调用大模型）"""
    user = _require_auth()
    if not user:
        return _json_error("请先登录", 401)

    conn = db.get_conn()
    task = db._fetchone(conn, "SELECT * FROM geo_expansion_task WHERE id = %s", (task_id,))
    if not task:
        return _json_error("任务不存在")
    if task["status"] == "running":
        return _json_error("任务正在执行中")
    if task["status"] == "completed":
        return _json_error("任务已完成")

    # 更新状态为 running
    now = _get_now()
    cur = conn.cursor()
    cur.execute(
        "UPDATE geo_expansion_task SET status='running', updated_at=%s WHERE id=%s",
        (now, task_id)
    )
    conn.commit()

    # 异步执行大模型调用
    try:
        _run_expansion_task_async(task_id, task)
    except Exception as e:
        logger.exception("Expansion task %d failed", task_id)
        cur.execute(
            "UPDATE geo_expansion_task SET status='failed', error_message=%s, updated_at=%s WHERE id=%s",
            (str(e)[:500], _get_now(), task_id)
        )
        conn.commit()
        return _json_error(f"任务执行失败: {e}")

    return _json_ok({"taskId": task_id}, "任务已启动")


def _run_expansion_task_async(task_id: int, task: dict):
    """执行拓词任务：读取配置 → 调用大模型 → 保存结果"""
    from llm_qwen import call_qwen  # 使用通义千问模型

    # 读取系统设置中的拓词指令
    instruction = _get_expansion_instruction()

    # 构建提示词变量
    brand_word_ratio = "2:8" if task["include_brand"] else "0:10"
    comparison_note = (
        "允许竞品/品类对比择优问法，可生成品牌对比、产品对比类提示词" if task["include_comparison"]
        else "不生成对比词，只用面向单一选择的直接择优/推荐句式"
    )
    expansion_type = f"GEO拓词 | 品牌词比例{brand_word_ratio} | {comparison_note}"
    extra_req = task.get("extra_requirements") or "无"

    # 如果有自定义指令，替换其中的占位符变量（使用 replace 避免 JSON 中的 {} 冲突）
    if instruction:
        system_prompt = instruction
        system_prompt = system_prompt.replace("{brand}", task["brand_name"])
        system_prompt = system_prompt.replace("{count}", str(task["prompt_count"]))
        system_prompt = system_prompt.replace("{expansion_type}", expansion_type)
        system_prompt = system_prompt.replace("{additional_requirements}", extra_req)
    else:
        # 默认指令（无自定义指令时使用）
        system_prompt = f"""你是一个GEO(生成式引擎优化)专家。根据用户需求生成搜索提示词。

## 品牌信息
{task['brand_name']}

## 任务要求
生成 {task['prompt_count']} 条高质量 GEO 提示词。
品牌词/通用词比例：{brand_word_ratio}
对比要求：{comparison_note}
补充要求：{extra_req}

## 输出格式(JSON数组)
[
  {{
    "intent_category": "意图分类",
    "core_intent_word": "核心意图词",
    "prompt": "提示词"
  }}
]

只输出 JSON 数组，不要输出其他内容。"""

    # 用户提示词（简化版，因为主要信息已在 system_prompt 中）
    user_prompt = f"""请严格按上述要求生成 {task['prompt_count']} 条 GEO 提示词，输出纯 JSON 数组。"""

    # 调用大模型（需要先加载配置 settings）
    logger.info("Calling LLM for expansion task %d", task_id)
    from db import get_all_settings
    settings = get_all_settings()
    response_text = call_qwen(
        settings,
        user_prompt=user_prompt,
        system_prompt=system_prompt,
        temperature=0.7
    )

    # 解析结果
    prompts = _parse_llm_response(response_text)

    # 保存结果到数据库
    conn = db.get_conn()
    cur = conn.cursor()
    now = _get_now()

    saved_count = 0
    for idx, p in enumerate(prompts):
        cur.execute(
            """INSERT INTO geo_expansion_prompt
               (task_id, intent_category, core_intent_word, prompt_text, sort_order, created_at)
               VALUES (%s, %s, %s, %s, %s, %s)""",
            (task_id,
             p.get("intent_category", "未分类"),
             p.get("core_intent_word", ""),
             p.get("prompt", ""),
             idx + 1, now)
        )
        saved_count += 1

    # 更新任务状态
    cur.execute(
        """UPDATE geo_expansion_task
           SET status='completed', total_prompts=%s, updated_at=%s, completed_at=%s
           WHERE id=%s""",
        (saved_count, now, now, task_id)
    )
    conn.commit()

    logger.info("Expansion task %d completed: %d prompts generated", task_id, saved_count)


def _parse_llm_response(text: str) -> list[dict]:
    """解析大模型返回的 JSON 结果"""
    # 尝试提取 JSON 数组
    text = text.strip()
    if text.startswith("```"):
        # 移除 markdown 代码块标记
        lines = text.split("\n")
        text = "\n".join(line for line in lines if not line.strip().startswith("```"))

    try:
        data = json.loads(text)
        if isinstance(data, list):
            return data
    except json.JSONDecodeError:
        pass

    # 尝试找到 JSON 数组部分
    start = text.find("[")
    end = text.rfind("]")
    if start >= 0 and end > start:
        try:
            data = json.loads(text[start:end + 1])
            if isinstance(data, list):
                return data
        except json.JSONDecodeError:
            pass

    # 如果解析失败，将文本按行分割作为单个提示词
    results = []
    for line in text.split("\n"):
        line = line.strip()
        if line and len(line) > 5:
            results.append({
                "intent_category": "未分类",
                "core_intent_word": line[:20],
                "prompt": line
            })
    return results[:500]  # 限制最多500条


# ── 任务详情（含提示词列表） ────────────────────────────────────────────


def api_geo_expansion_task_detail(task_id: int):
    """获取任务详情和生成的提示词列表"""
    user = _require_auth()
    if not user:
        return _json_error("请先登录", 401)

    conn = db.get_conn()
    task = db._fetchone(conn, "SELECT * FROM geo_expansion_task WHERE id = %s", (task_id,))
    if not task:
        return _json_error("任务不存在", 404)

    # 获取提示词列表
    prompts = db._fetchall(
        conn,
        "SELECT * FROM geo_expansion_prompt WHERE task_id = %s ORDER BY sort_order",
        (task_id,)
    )

    prompt_list = []
    for p in prompts:
        prompt_list.append({
            "id": p["id"],
            "intentCategory": p.get("intent_category", ""),
            "coreIntentWord": p.get("core_intent_word", ""),
            "promptText": p.get("prompt_text", ""),
            "sortOrder": p.get("sort_order", 0),
        })

    return _json_ok({
        "task": {
            "id": task["id"],
            "accountId": task["account_id"],
            "brandName": task["brand_name"],
            "promptCount": task["prompt_count"],
            "status": task["status"],
            "totalPrompts": task.get("total_prompts", 0),
            "createdAt": task.get("created_at", ""),
        },
        "prompts": prompt_list,
    })


# ── 删除任务 ──────────────────────────────────────────────────────────────


def api_geo_expansion_task_delete(task_id: int):
    """删除拓词任务及其结果"""
    user = _require_auth()
    if not user:
        return _json_error("请先登录", 401)

    conn = db.get_conn()
    cur = conn.cursor()

    # 删除关联的提示词
    cur.execute("DELETE FROM geo_expansion_prompt WHERE task_id = %s", (task_id,))
    # 删除任务
    cur.execute("DELETE FROM geo_expansion_task WHERE id = %s", (task_id,))
    conn.commit()

    return _json_ok(msg="删除成功")


# ── 导出 Excel ────────────────────────────────────────────────────────────


def api_geo_expansion_task_export(task_id: int):
    """导出任务结果为 Excel"""
    user = _require_auth()
    if not user:
        return _json_error("请先登录", 401)

    conn = db.get_conn()
    task = db._fetchone(conn, "SELECT * FROM geo_expansion_task WHERE id = %s", (task_id,))
    if not task:
        return _json_error("任务不存在", 404)

    prompts = db._fetchall(
        conn,
        "SELECT intent_category, core_intent_word, prompt_text FROM geo_expansion_prompt WHERE task_id = %s ORDER BY sort_order",
        (task_id,)
    )

    # 生成 CSV 格式（前端可下载）
    import io
    import csv

    output = io.StringIO()
    writer = csv.writer(output)
    writer.writerow(["序号", "意图分类", "核心意图词", "提示词"])
    for i, p in enumerate(prompts, 1):
        writer.writerow([i, p.get("intent_category", ""), p.get("core_intent_word", ""), p.get("prompt_text", "")])

    from flask import Response
    return Response(
        output.getvalue(),
        mimetype="text/csv",
        headers={"Content-Disposition": f"attachment; filename=expansion_task_{task_id}.csv"}
    )


# ── 拓词指令配置 ─────────────────────────────────────────────────────────


def api_geo_expansion_instruction_get():
    """获取 GEO 拓词指令配置"""
    user = _require_auth()
    if not user:
        return _json_error("请先登录", 401)

    instruction = _get_expansion_instruction()
    return _json_ok({"instruction": instruction or ""})


def api_geo_expansion_instruction_set():
    """设置 GEO 拓词指令配置"""
    user = _require_auth()
    if not user:
        return _json_error("请先登录", 401)

    data = request.get_json(silent=True) or {}
    instruction = data.get("instruction", "")

    if len(instruction) > 50000:
        return _json_error("指令内容不能超过 50000 字符")

    conn = db.get_conn()
    cur = conn.cursor()
    now = _get_now()

    # 使用 UPSERT
    cur.execute(
        """INSERT INTO system_setting (setting_key, setting_value, updated_at)
           VALUES ('geo_expansion_instruction', %s, %s)
           ON DUPLICATE KEY UPDATE setting_value=%s, updated_at=%s""",
        (instruction, now, instruction, now)
    )
    conn.commit()

    return _json_ok(msg="保存成功")


def _get_expansion_instruction() -> str | None:
    """从数据库读取拓词指令"""
    row = db._fetchone(
        db.get_conn(),
        "SELECT setting_value FROM system_setting WHERE setting_key = 'geo_expansion_instruction'"
    )
    return row["setting_value"] if row else None


# ── 客户列表（用于创建任务时选择品牌） ───────────────────────────────────


def api_geo_expansion_accounts():
    """获取客户列表（含品牌名）供下拉选择"""
    user = _require_auth()
    if not user:
        return _json_error("请先登录", 401)

    rows = db._fetchall(
        db.get_conn(),
        """SELECT id, company_name, company_brand
           FROM account
           WHERE status = 'formal' AND (deleted_at IS NULL OR deleted_at = '')
           ORDER BY company_name ASC"""
    )

    result = []
    for r in rows:
        result.append({
            "id": r["id"],
            "name": r.get("company_name", ""),
            "brandName": r.get("company_brand") or r.get("company_name", ""),
        })

    return _json_ok(result)


# ── 路由注册 ──────────────────────────────────────────────────────────────


def register(app):
    """注册所有路由到 Flask app。由 app.py 调用。"""
    endpoints = [
        # 概览
        ("/api/geo-expansion/overview", ["GET"], api_geo_expansion_overview),

        # 任务 CRUD
        ("/api/geo-expansion/tasks", ["GET"], api_geo_expansion_task_list),
        ("/api/geo-expansion/tasks", ["POST"], api_geo_expansion_task_create),
        ("/api/geo-expansion/tasks/<int:task_id>", ["GET"], api_geo_expansion_task_detail),
        ("/api/geo-expansion/tasks/<int:task_id>", ["DELETE"], api_geo_expansion_task_delete),
        ("/api/geo-expansion/tasks/<int:task_id>/run", ["POST"], api_geo_expansion_task_run),
        ("/api/geo-expansion/tasks/<int:task_id>/export", ["GET"], api_geo_expansion_task_export),

        # 辅助接口
        ("/api/geo-expansion/accounts", ["GET"], api_geo_expansion_accounts),

        # 指令配置
        ("/api/geo-expansion/instruction", ["GET"], api_geo_expansion_instruction_get),
        ("/api/geo-expansion/instruction", ["PUT"], api_geo_expansion_instruction_set),
    ]

    for rule, methods, view_func in endpoints:
        app.add_url_rule(rule, view_func=view_func, methods=methods)
