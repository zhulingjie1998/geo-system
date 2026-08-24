"""email_notify_service.py — GEO 系统每日邮件报告

职责：
  1. 采集"今日待执行的定时任务" + "昨日系统执行情况" + "异常清单"
  2. 用 jinja2 渲染 HTML 邮件
  3. 通过 SMTP（126 SSL）发送给配置的收件人列表

入口：
  - send_test(to_list)       : 立即发测试邮件（前端按钮）
  - send_daily()             : 发送每日报告（被 scheduler_daemon 调用）
  - check_and_send_if_due()  : 每 tick 检查是否到点 + 防重发

配置（全部存 system_setting 表，没有硬编码默认）：
  email_notify_enabled  : "1"/"0"，默认 "0"
  email_smtp_host       : SMTP 服务器，默认 smtp.126.com
  email_smtp_port       : SMTP 端口，默认 465
  email_smtp_user       : SMTP 登录用户名（必填）
  email_smtp_pass       : SMTP 授权码（必填）
  email_from            : 发件人地址（必填）
  email_to              : 收件人列表，JSON 数组或逗号分隔字符串（必填）
  email_send_time       : "HH:MM"，默认 "08:00"
  email_last_sent_date  : 内部状态，"YYYY-MM-DD"，防当日重发
"""

from __future__ import annotations

import json
import logging
import os
import smtplib
import ssl
from datetime import datetime, timedelta
from email.header import Header
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from email.utils import formataddr
from typing import Optional

from jinja2 import Environment, FileSystemLoader, select_autoescape

import db

logger = logging.getLogger("email_notify")

# httpx 默认在 INFO 级别打印完整请求 URL —— Server酱 sendkey 写在 URL 里会泄露到日志。
# 一次性把 httpx / httpcore 提到 WARNING，全局生效。
for _noisy in ("httpx", "httpcore", "httpcore.http11", "httpcore.connection"):
    logging.getLogger(_noisy).setLevel(logging.WARNING)

_TEMPLATE_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "report_templates")
_env = Environment(
    loader=FileSystemLoader(_TEMPLATE_DIR),
    autoescape=select_autoescape(["html", "xml"]),
    trim_blocks=True,
    lstrip_blocks=True,
)


# ═══════════════ 配置默认值 ═══════════════

EMAIL_SETTING_KEYS = (
    "email_smtp_host", "email_smtp_port", "email_smtp_user", "email_smtp_pass",
    "email_from", "email_to", "email_send_time", "email_notify_enabled",
)

DEFAULT_NON_SECRET = {
    "email_smtp_host":      "smtp.126.com",
    "email_smtp_port":      "465",
    "email_send_time":      "08:00",
    "email_notify_enabled": "0",
}

REQUIRED_KEYS = ("email_smtp_user", "email_smtp_pass", "email_from", "email_to")


def _load_active_account() -> dict | None:
    """读 system_setting.email_active_account_id 指向的 email_account 行；无则 None。
    用于多账号切换：管理员可在前端切换不同发件邮箱，service 实时读激活账号。"""
    try:
        s = db.get_all_settings()
        aid = s.get("email_active_account_id")
        if not aid:
            return None
        row = db._fetchone(db.get_conn(),
            "SELECT email, display_name, smtp_host, smtp_port, smtp_user, smtp_pass "
            "FROM email_account WHERE id=%s AND is_active=1", (int(aid),))
        return row
    except Exception:
        return None


def _get_settings() -> dict:
    """优先用激活账号(email_account 表)；找不到则回退老 system_setting key（兼容历史配置）。"""
    s = db.get_all_settings()
    out = {k: "" for k in EMAIL_SETTING_KEYS}
    for k in EMAIL_SETTING_KEYS:
        v = s.get(k)
        if v not in (None, ""):
            out[k] = v
        elif k in DEFAULT_NON_SECRET:
            out[k] = DEFAULT_NON_SECRET[k]

    # 多账号切换：若有激活账号，覆盖 SMTP 凭据 + email_from
    acct = _load_active_account()
    if acct:
        out["email_smtp_host"] = acct.get("smtp_host") or out["email_smtp_host"]
        out["email_smtp_port"] = str(acct.get("smtp_port") or out["email_smtp_port"])
        out["email_smtp_user"] = acct.get("smtp_user") or out["email_smtp_user"]
        out["email_smtp_pass"] = acct.get("smtp_pass") or out["email_smtp_pass"]
        # email_from 用 display_name<email>，或纯 email
        name = (acct.get("display_name") or "").strip()
        out["email_from"] = f"{name} <{acct['email']}>" if name else acct["email"]

    out["email_last_sent_date"] = s.get("email_last_sent_date") or ""
    return out


def _missing_required(s: dict) -> list[str]:
    return [k for k in REQUIRED_KEYS if not (s.get(k) or "").strip()]


# ═══════════════ Server酱微信推送 ═══════════════

def _get_serverchan_settings() -> dict:
    """Server酱推送配置：sendkey + 是否启用 + 可选 channel。"""
    s = db.get_all_settings()
    return {
        "sendkey": (s.get("serverchan_sendkey") or "").strip(),
        "enabled": (s.get("serverchan_enabled") or "0") == "1",
        "channel": (s.get("serverchan_channel") or "").strip(),
    }


def _push_serverchan(title: str, desp: str, *, channel: str = "") -> dict:
    """通过 Server酱推送到微信（方糖服务号 / 官方 APP / 企业微信等，按 channel）。
    title 卡 32 字、desp 支持 Markdown 卡 32KB。任何失败返回 ok=False 不抛异常。"""
    sc = _get_serverchan_settings()
    if not sc["enabled"]:
        return {"ok": False, "skipped": "Server酱未启用"}
    if not sc["sendkey"]:
        return {"ok": False, "error": "未配置 serverchan_sendkey"}

    title = (title or "")[:32]
    payload = {"title": title, "desp": (desp or "")[:30000]}
    ch = (channel or sc["channel"] or "").strip()
    if ch:
        payload["channel"] = ch

    url = f"https://sctapi.ftqq.com/{sc['sendkey']}.send"
    try:
        import httpx
        with httpx.Client(timeout=15.0, trust_env=False) as cli:
            resp = cli.post(url, data=payload)
            resp.raise_for_status()
            try:
                j = resp.json()
            except Exception:
                j = {}
        if isinstance(j, dict) and j.get("code") == 0:
            push_id = (j.get("data") or {}).get("pushid", "")
            logger.info("[serverchan] push OK title=%r pushid=%s", title[:30], push_id)
            return {"ok": True, "pushid": push_id}
        return {"ok": False, "error": f"Server酱返回: {str(j)[:300]}"}
    except Exception as exc:
        logger.exception("[serverchan] push failed")
        return {"ok": False, "error": f"{type(exc).__name__}: {exc}"}


def _progress_bar(ok: int, total: int, width: int = 10) -> str:
    """生成 emoji 进度条：▓▓▓▓░░░░░░ 40%"""
    if total <= 0:
        return "░" * width
    filled = round(ok * width / total)
    filled = max(0, min(width, filled))
    return "▓" * filled + "░" * (width - filled)


def _kpi_emoji(ok: int, total: int) -> str:
    """根据成功率给颜色 emoji。"""
    if total == 0:
        return "⚪"
    if ok == total:
        return "🟢"
    if ok == 0:
        return "🔴"
    if ok / total >= 0.8:
        return "🟡"
    return "🟠"


def _build_wechat_summary(data: dict) -> str:
    """微信精美 Markdown 摘要：用表格 / 引用 / 进度条 emoji 让信息一目了然。"""
    L = []
    today = data.get("today", "")
    weekday = data.get("today_weekday", "")
    yesterday = data.get("yesterday", "")
    generated_at = data.get("generated_at", "")

    # ╔═══ 顶部大标题 + 引用块 KPI 总览 ═══╗
    L.append(f"# 📊 GEO 系统日报")
    L.append(f"### {today} · {weekday}")
    L.append("")

    # 提取核心 KPI
    ov = data.get("overnight") or {}
    ov_total = ov.get("total_runs", 0)
    ov_ok = ov.get("ok_runs", 0)
    ov_fail = ov.get("fail_runs", 0)
    today_kw = data.get("today_kw_detail") or {}
    today_q = today_kw.get("total_queries", 0)
    today_q_ok = today_kw.get("total_ok", 0)
    today_kw_n = today_kw.get("total_keywords", 0)
    err_count = data.get("yest_error_count", 0) or 0

    # 引用块大字 KPI
    if ov_total > 0:
        ov_emoji = "✅" if ov_fail == 0 else ("⚠️" if ov_ok > 0 else "❌")
        ov_line = f"**凌晨调度 `{ov_ok}/{ov_total}` {ov_emoji}**"
    else:
        ov_line = f"**凌晨调度 ⚠️ 未执行**"

    if today_q > 0:
        rate = today_q_ok * 100 // today_q
        kpi_line = f"**今日查询 `{today_q_ok}/{today_q}` ({rate}%)** · 覆盖 **{today_kw_n}** 个关键词"
    else:
        kpi_line = f"今日暂无查询"

    err_line = f"**昨日异常 ⚠️ {err_count} 条**" if err_count > 0 else f"**昨日异常 ✅ 无**"

    L.append(f"> {ov_line}")
    L.append(f"> {kpi_line}")
    L.append(f"> {err_line}")
    L.append("")

    # ╔═══ 1. 凌晨调度执行明细 ═══╗
    L.append("---")
    L.append("## 🌙 凌晨调度")
    items = ov.get("items") or []
    if items:
        L.append("")
        L.append("| 客户 | 任务 | 进度 | 状态 |")
        L.append("|---|---|:---:|:---:|")
        for it in items[:10]:
            label = it.get("type_label", "")
            name = (it.get("account_name") or "")[:15]
            o = it.get("ok", 0)
            t = it.get("total", 0)
            st = it.get("status", "")
            if t > 0 and o == t:
                e = "✅"
            elif o == 0 and t > 0:
                e = "❌"
            elif 0 < o < t:
                e = "⚠️"
            else:
                e = "✅" if st == "completed" else "❌"
            prog = f"{o}/{t}" if t > 0 else "—"
            L.append(f"| {name} | {label} | {prog} | {e} |")
    else:
        L.append("")
        L.append("> ⚠️ 今日凌晨没有自动调度执行")
    L.append("")

    # ╔═══ 2. 今日各客户查询明细 ═══╗
    rows = today_kw.get("rows") or []
    if rows:
        L.append("---")
        L.append(f"## 🔍 今日客户查询")
        L.append("")
        L.append("| 客户 | 查询 | 进度条 | 模型 |")
        L.append("|---|:---:|:---:|---|")
        for r in rows[:8]:
            cn = (r.get("company_name") or "")[:14]
            t = r.get("total", 0)
            o = r.get("ok", 0)
            kw_n = r.get("kw_count", 0)
            mc = r.get("model_count", 0)
            bar = _progress_bar(o, t, 8)
            mname = (r.get("models") or "").replace("·", "·")
            L.append(f"| **{cn}** | {o}/{t} | `{bar}` | {kw_n}词×{mc} |")
        L.append("")

    # ╔═══ 3. 昨日回顾 ═══╗
    yest_kw = data.get("yest_kw_detail") or {}
    yest_q = yest_kw.get("total_queries", 0)
    yest_q_ok = yest_kw.get("total_ok", 0)
    yest_sum = data.get("yest_summary") or {}
    if yest_q > 0 or yest_sum:
        L.append("---")
        L.append(f"## 📅 昨日回顾 ({yesterday})")
        L.append("")
        if yest_q > 0:
            yrate = yest_q_ok * 100 // yest_q if yest_q else 0
            ybar = _progress_bar(yest_q_ok, yest_q, 12)
            ye = _kpi_emoji(yest_q_ok, yest_q)
            L.append(f"{ye} **查询总量 `{yest_q_ok}/{yest_q}` ({yrate}%)**  `{ybar}`")
            L.append("")

        # 其他类任务（非查词）
        others = []
        for k, v in yest_sum.items():
            label = v.get("label", k)
            if label == "查词任务":
                continue
            others.append((label, v.get("ok", 0), v.get("total", 0), v.get("fail", 0)))
        if others:
            L.append("| 任务类型 | 成功 | 总数 | 失败 |")
            L.append("|---|:---:|:---:|:---:|")
            for label, o, t, f in others:
                f_cell = f"⚠️ {f}" if f else "—"
                L.append(f"| {label} | {o} | {t} | {f_cell} |")
            L.append("")

    # ╔═══ 4. 昨日异常 ═══╗
    errors = data.get("yest_errors") or []
    if errors:
        L.append("---")
        L.append(f"## ⚠️ 昨日异常 ({len(errors)})")
        L.append("")
        for e in errors[:5]:
            tp = e.get("type", "")
            aid = e.get("account_id", "?")
            msg = (e.get("msg") or "").replace("\n", " ")[:90]
            L.append(f"- **{tp}** · acct=`{aid}`")
            L.append(f"  > {msg}")
        if len(errors) > 5:
            L.append(f"- _其余 {len(errors)-5} 条详见邮件_")
        L.append("")

    # ╔═══ 5. 今日待执行调度 ═══╗
    due = data.get("today_due") or []
    if due:
        L.append("---")
        L.append(f"## ⏰ 今日待执行调度 ({len(due)})")
        L.append("")
        L.append("| 时间 | 类型 | 客户 |")
        L.append("|:---:|---|---|")
        for d in due[:8]:
            tlabel = d.get("type_label", d.get("type", ""))
            run_at = d.get("run_time", "") or (d.get("nextRunAt", "") or "")[-8:-3]
            name = (d.get("account_name") or d.get("companyName") or "")[:14]
            L.append(f"| {run_at} | {tlabel} | {name} |")
        L.append("")

    # ╔═══ 6. 系统状态 ═══╗
    sched_total = data.get("scheduled_total", 0)
    if sched_total or err_count:
        L.append("---")
        L.append("## 🔧 系统状态")
        L.append("")
        sys_ok_emoji = "✅" if err_count == 0 and ov_fail == 0 else "⚠️"
        L.append(f"- {sys_ok_emoji} 已配置调度：**{sched_total}** 个")
        if ov_fail > 0:
            L.append(f"- ⚠️ 凌晨失败：**{ov_fail}** 个")
        if err_count > 0:
            L.append(f"- ⚠️ 昨日异常：**{err_count}** 条")
        L.append("")

    # 底部
    gen_short = (generated_at or "")[-8:]
    L.append("---")
    L.append(f"📧 _完整 HTML 报告见邮箱  ·  {gen_short} 生成_")
    return "\n".join(L)




def _parse_to_list(raw: str) -> list[str]:
    """email_to 字段：兼容 JSON 数组 / 逗号分隔字符串"""
    raw = (raw or "").strip()
    if not raw:
        return []
    if raw.startswith("["):
        try:
            arr = json.loads(raw)
            if isinstance(arr, list):
                return [str(x).strip() for x in arr if str(x).strip()]
        except Exception:
            pass
    return [s.strip() for s in raw.replace("，", ",").split(",") if s.strip()]


# ═══════════════ 数据采集 ═══════════════

_SCHED_TYPE_LABELS = {
    "search":        "查词",
    "ranking":       "排名分析",
    "pipeline":      "批量流水线",
    "weekly_report": "周报",
    "citation":      "引用源抓取",
    "quote":         "报价计算",
}

# 邮件"今日已开始执行"统计的任务类型注册表：(key, label, table, date_col)
# 新增任务类型只需在这里加一行；SQL 在调用点用 date_col 拼装索引友好的范围查询。
_OUTLINE_QUERIES: list[tuple[str, str, str, str]] = [
    ("search",        "查词",         "search_task",          "created_at"),
    ("ranking",       "排名分析",     "ranking_task",         "created_at"),
    ("citation",      "引用源抓取",   "citation_scrape_task", "started_at"),
    ("quote",         "报价",         "quote_task",           "created_at"),
    ("kw_expand",     "拓词",         "keyword_expand_task",  "created_at"),
    ("weekly_report", "周报/品牌报告","weekly_report",        "created_at"),
    ("publish_order", "发布订单",     "publish_order",        "created_at"),
    ("publish_batch", "批量发布",     "publish_batch_task",   "created_at"),
    ("mediabox_sync", "媒体同步",     "mediabox_sync_task",   "started_at"),
    ("pipeline",      "批量流水线",   "pipeline_execution",   "started_at"),
]


def _gather_scheduled_tasks() -> list[dict]:
    """汇总所有 enabled=1 的调度任务，按 next_run_at 排序。"""
    conn = db.get_conn()
    rows = []

    def _fetch(table: str, type_key: str, extra_select: str = ""):
        try:
            sql = f"""SELECT '{type_key}' AS type, id, name, account_id, frequency, run_time,
                            day_of_week, day_of_month, enabled, next_run_at, last_run_at,
                            last_status {extra_select}
                     FROM {table} WHERE enabled=1"""
            return db._fetchall(conn, sql)
        except Exception as e:
            logger.debug("query %s failed: %s", table, e)
            return []

    rows.extend(_fetch("scheduled_search_task", "search"))
    rows.extend(_fetch("scheduled_ranking_task", "ranking"))
    rows.extend(_fetch("scheduled_pipeline_task", "pipeline"))
    rows.extend(_fetch("scheduled_weekly_report_task", "weekly_report"))
    rows.extend(_fetch("scheduled_citation_task", "citation"))
    rows.extend(_fetch("scheduled_quote_task", "quote"))

    # 拉取 account 名映射
    acct_ids = list({r["account_id"] for r in rows if r.get("account_id")})
    acct_name = {}
    if acct_ids:
        acct_rows = db._fetchall(conn,
            f"SELECT id, company_name FROM account WHERE id IN ({','.join(['%s']*len(acct_ids))})",
            tuple(acct_ids))
        acct_name = {r["id"]: r["company_name"] for r in acct_rows}

    out = []
    for r in rows:
        out.append({
            "type":         r["type"],
            "type_label":   _SCHED_TYPE_LABELS.get(r["type"], r["type"]),
            "id":           r["id"],
            "name":         r.get("name") or "",
            "account_name": acct_name.get(r.get("account_id")) or f"账号#{r.get('account_id')}",
            "frequency":    r.get("frequency") or "",
            "run_time":     r.get("run_time") or "",
            "day_of_week":  r.get("day_of_week"),
            "day_of_month": r.get("day_of_month"),
            "next_run_at":  str(r.get("next_run_at") or "") or "—",
            "last_run_at":  str(r.get("last_run_at") or "") or "—",
            "last_status":  (r.get("last_status") or "—"),
        })
    out.sort(key=lambda x: x["next_run_at"])
    return out


def _gather_today_due(scheduled_tasks: list[dict], today_str: str) -> list[dict]:
    return [t for t in scheduled_tasks if str(t.get("next_run_at") or "")[:10] == today_str]


def _classify_status(status: str) -> str:
    """统一归类：success / fail / running / unknown"""
    if status is None:
        return "unknown"
    s = str(status).strip().lower()
    if s in ("completed", "done", "success", "succeed", "succeeded"):
        return "success"
    if s in ("failed", "fail", "error", "cancelled", "canceled"):
        return "fail"
    if s in ("running", "pending", "expanding", "queued", "scraping", "extracting", "scoring"):
        return "running"
    return "unknown"


def _aggregate_table(conn, table: str, date_field: str, yesterday_str: str,
                     status_field: str = "status") -> dict | None:
    """通用：按 status 分组聚合昨日 table，返回 {total, ok, fail, running}。表不存在或字段不存在则返回 None。"""
    from geo_common import date_range
    args = date_range(yesterday_str)
    try:
        rows = db._fetchall(conn,
            f"SELECT {status_field} AS s, COUNT(*) AS n FROM {table} "
            f"WHERE {date_field} >= %s AND {date_field} < %s GROUP BY {status_field}",
            args)
    except Exception as e:
        logger.debug("aggregate %s skipped: %s", table, e)
        return None
    total = sum(r["n"] for r in rows)
    ok = fail = running = 0
    for r in rows:
        cat = _classify_status(r["s"])
        if cat == "success":
            ok += r["n"]
        elif cat == "fail":
            fail += r["n"]
        elif cat == "running":
            running += r["n"]
    return {"total": total, "ok": ok, "fail": fail, "running": running}


def _collect_errors(conn, table: str, type_label: str, date_field: str, yesterday_str: str,
                     id_field: str = "id", account_field: str = "account_id",
                     status_field: str = "status", error_field: str = "error_message",
                     fail_statuses: tuple = ("failed", "FAILED", "error", "ERROR",
                                             "cancelled", "CANCELLED"),
                     limit: int = 8) -> list[dict]:
    """通用：拉取昨日 table 的失败记录列表。表不存在或字段不存在则返回 []。"""
    from geo_common import date_range
    d0, d1 = date_range(yesterday_str)
    try:
        in_clause = ",".join(["%s"] * len(fail_statuses))
        rows = db._fetchall(conn,
            f"SELECT {id_field} AS x_id, {account_field} AS x_acct, {status_field} AS x_status, "
            f"{error_field} AS x_err, {date_field} AS x_time FROM {table} "
            f"WHERE {date_field} >= %s AND {date_field} < %s AND {status_field} IN ({in_clause}) "
            f"ORDER BY {date_field} DESC LIMIT {int(limit)}",
            (d0, d1, *fail_statuses))
    except Exception as e:
        logger.debug("collect_errors %s skipped: %s", table, e)
        return []
    out = []
    for r in rows:
        rid = r.get("x_id")
        rid_str = str(rid)[:14] if rid is not None else ""
        out.append({
            "type": type_label,
            "id": rid_str,
            "account_id": r.get("x_acct"),
            "status": r.get("x_status") or "",
            "time": str(r.get("x_time") or ""),
            "msg": (r.get("x_err") or "")[:200],
        })
    return out


def _gather_yesterday_executions(yesterday_str: str) -> dict:
    """采集昨日各类任务的执行情况，返回汇总 + 异常列表。覆盖：
       查词 / 排名分析 / 引用源抓取 / 报价 / GEO 拓词 /
       周报+品牌报告 / 批量流水线 / 内容发布订单 / 批量发布任务 / 媒体同步
    """
    conn = db.get_conn()
    summary = {}
    errors = []

    # ── 通用聚合（基于公共 status 字段）──
    table_specs = [
        # (key, label, table, date_field, error_field, fail_statuses)
        ("search",         "查词任务",           "search_task",         "created_at", "error_message",
            ("ERROR", "CANCELLED")),
        ("ranking",        "排名分析任务",        "ranking_task",        "created_at", "error_message",
            ("error", "ERROR", "failed", "FAILED")),
        ("citation",       "引用源抓取",          "citation_scrape_task","started_at", "error_message",
            ("error", "ERROR", "failed", "FAILED")),
        ("quote",          "GEO 报价",            "quote_task",          "created_at", "error_message",
            ("error", "ERROR", "failed", "FAILED")),
        ("kw_expand",      "GEO 拓词",            "keyword_expand_task", "created_at", "error_message",
            ("FAILED", "failed")),
        ("publish_batch",  "批量发布任务",        "publish_batch_task",  "created_at", "error_message",
            ("failed", "FAILED", "cancelled", "CANCELLED")),
        ("mediabox_sync",  "媒体资源同步",        "mediabox_sync_task",  "started_at", None,
            ("error", "ERROR", "failed", "FAILED")),
    ]
    for key, label, tbl, date_field, err_field, fail_states in table_specs:
        agg = _aggregate_table(conn, tbl, date_field, yesterday_str)
        if agg is None or agg["total"] == 0:
            continue
        summary[key] = {"label": label, **agg}
        if err_field:
            errors.extend(_collect_errors(conn, tbl, label, date_field, yesterday_str,
                                          error_field=err_field, fail_statuses=fail_states, limit=5))

    # ── weekly_report：要按 report_type 分两类 ──
    from geo_common import date_range as _dr
    _d0, _d1 = _dr(yesterday_str)
    try:
        rows = db._fetchall(conn,
            """SELECT report_type, status, COUNT(*) AS n
               FROM weekly_report
               WHERE created_at >= %s AND created_at < %s
               GROUP BY report_type, status""",
            (_d0, _d1))
        for rt, label_cn in [("weekly", "周报"), ("brand", "品牌竞争分析报告")]:
            sub = [r for r in rows if (r.get("report_type") or "weekly") == rt]
            if not sub:
                continue
            total = sum(r["n"] for r in sub)
            ok = sum(r["n"] for r in sub if r["status"] == "completed")
            fail = sum(r["n"] for r in sub if r["status"] == "failed")
            running = sum(r["n"] for r in sub if r["status"] == "running")
            key = "weekly_report" if rt == "weekly" else "brand_report"
            summary[key] = {"label": label_cn, "total": total, "ok": ok, "fail": fail, "running": running}

        err_rows = db._fetchall(conn,
            """SELECT id, account_id, report_type, status, error_message, created_at
               FROM weekly_report
               WHERE created_at >= %s AND created_at < %s AND status='failed'
               ORDER BY created_at DESC LIMIT 8""",
            (_d0, _d1))
        for r in err_rows:
            type_cn = "品牌报告" if r.get("report_type") == "brand" else "周报"
            errors.append({
                "type": type_cn, "id": str(r["id"]), "account_id": r.get("account_id"),
                "status": "failed", "time": str(r["created_at"]),
                "msg": (r.get("error_message") or "")[:200],
            })
    except Exception:
        logger.exception("[email_notify] weekly_report aggregation failed")

    # ── publish_order：状态是数字 ──
    try:
        rows = db._fetchall(conn,
            """SELECT status, COUNT(*) AS n FROM publish_order
               WHERE created_at >= %s AND created_at < %s GROUP BY status""",
            (_d0, _d1))
        if rows:
            total = sum(r["n"] for r in rows)
            ok = sum(r["n"] for r in rows if int(r["status"] or 0) == 2)
            fail = sum(r["n"] for r in rows if int(r["status"] or 0) in (-1, -2, 99))
            running = sum(r["n"] for r in rows if int(r["status"] or 0) in (0, 1))
            summary["publish_order"] = {"label": "内容发布订单", "total": total, "ok": ok, "fail": fail, "running": running}
    except Exception:
        logger.exception("[email_notify] publish_order aggregation failed")

    # ── pipeline_execution：单独处理 ──
    try:
        rows = db._fetchall(conn,
            """SELECT status, COUNT(*) AS n FROM pipeline_execution
               WHERE started_at >= %s AND started_at < %s GROUP BY status""",
            (_d0, _d1))
        if rows:
            total = sum(r["n"] for r in rows)
            ok = sum(r["n"] for r in rows if r["status"] == "completed")
            fail = sum(r["n"] for r in rows if r["status"] == "failed")
            summary["pipeline"] = {"label": "批量流水线（调度执行）", "total": total, "ok": ok, "fail": fail, "running": 0}

        err_rows = db._fetchall(conn,
            """SELECT id, account_id, status, error_message, started_at
               FROM pipeline_execution
               WHERE started_at >= %s AND started_at < %s AND status='failed'
               ORDER BY started_at DESC LIMIT 5""",
            (_d0, _d1))
        for r in err_rows:
            errors.append({
                "type": "批量流水线", "id": str(r["id"]), "account_id": r.get("account_id"),
                "status": "failed", "time": str(r["started_at"]),
                "msg": (r.get("error_message") or "")[:200],
            })
    except Exception:
        logger.exception("[email_notify] pipeline aggregation failed")

    # 异常按时间倒序
    errors.sort(key=lambda e: e["time"], reverse=True)
    return {"summary": summary, "errors": errors[:20]}


def _gather_today_outline(today_str: str) -> dict:
    """今日已开始的执行汇总（按类别）。新增任务类型只需在 _OUTLINE_QUERIES 注册。"""
    conn = db.get_conn()
    out = {}
    from geo_common import date_range
    args = date_range(today_str)
    for key, label, table, date_col in _OUTLINE_QUERIES:
        sql = f"SELECT COUNT(*) AS n FROM {table} WHERE {date_col} >= %s AND {date_col} < %s"
        try:
            r = db._fetchone(conn, sql, args)
            out[key] = {"label": label, "n": int(r["n"]) if r else 0}
        except Exception:
            out[key] = {"label": label, "n": 0}
    out["total"] = sum(v["n"] for v in out.values() if isinstance(v, dict))
    out["nonzero_count"] = sum(1 for v in out.values() if isinstance(v, dict) and v["n"] > 0)
    # 提取按值降序的可展示列表（仅非零项）
    out["display_items"] = sorted(
        [{"key": k, "label": v["label"], "n": v["n"]} for k, v in out.items() if isinstance(v, dict) and v["n"] > 0],
        key=lambda x: -x["n"],
    )
    return out


def _gather_overnight_runs(today_str: str) -> dict:
    """采集今日凌晨已执行的定时调度详情。
    数据源：6 张 scheduled_*_task 表的 last_run_at；对查词类任务关联 search_result 拉去重后的 KPI。
    返回：[{time, type, type_label, account_name, sched_id, kw_count, model_count, total, ok, fail, status, ...}]
    按 last_run_at 升序。
    """
    conn = db.get_conn()
    items = []

    # ── 查词调度（最重要，要拉去重后的实际查询数）──
    try:
        rows = db._fetchall(conn,
            """SELECT s.id AS sched_id, s.account_id, a.company_name,
                      s.run_time, s.last_run_at, s.last_status, s.last_task_id, s.models
               FROM scheduled_search_task s
               LEFT JOIN account a ON a.id=s.account_id
               WHERE s.enabled=1 AND LEFT(s.last_run_at, 10)=%s
               ORDER BY s.last_run_at""",
            (today_str,))
        for r in rows:
            stat = {"kw_count": 0, "model_count": 0, "total": 0, "ok": 0, "fail": 0, "models_list": ""}
            tid = r.get("last_task_id") or ""
            if tid:
                try:
                    sr = db._fetchone(conn,
                        """SELECT COUNT(DISTINCT keyword) AS kw,
                                  COUNT(DISTINCT model) AS mc,
                                  COUNT(*) AS total,
                                  SUM(eventually_succeeded) AS ok,
                                  GROUP_CONCAT(DISTINCT model ORDER BY model) AS models
                           FROM (
                              SELECT keyword, model, MAX(success) AS eventually_succeeded
                              FROM search_result
                              WHERE task_id=%s
                              GROUP BY keyword, model
                           ) t""",
                        (tid,))
                    if sr:
                        stat["kw_count"] = int(sr.get("kw") or 0)
                        stat["model_count"] = int(sr.get("mc") or 0)
                        stat["total"] = int(sr.get("total") or 0)
                        stat["ok"] = int(sr.get("ok") or 0)
                        stat["fail"] = stat["total"] - stat["ok"]
                        stat["models_list"] = (sr.get("models") or "").replace(",", " · ")
                except Exception:
                    pass
            items.append({
                "type": "search", "type_label": "查词",
                "sched_id": r["sched_id"],
                "account_name": r.get("company_name") or f"账号#{r.get('account_id')}",
                "run_time": r.get("run_time") or "—",
                "last_run_at": str(r.get("last_run_at") or ""),
                "status": r.get("last_status") or "—",
                "task_id": (tid or "")[:12],
                **stat,
            })
    except Exception as e:
        logger.exception("[email_notify] overnight search runs failed: %s", e)

    # ── 排名分析调度 ──
    try:
        rows = db._fetchall(conn,
            """SELECT s.id AS sched_id, s.account_id, a.company_name,
                      s.run_time, s.last_run_at, s.last_status, s.last_task_id
               FROM scheduled_ranking_task s
               LEFT JOIN account a ON a.id=s.account_id
               WHERE s.enabled=1 AND LEFT(s.last_run_at, 10)=%s
               ORDER BY s.last_run_at""",
            (today_str,))
        for r in rows:
            stat = {"kw_count": 0, "model_count": 0, "total": 0, "ok": 0, "fail": 0, "models_list": ""}
            tid = r.get("last_task_id") or ""
            if tid:
                try:
                    rt = db._fetchone(conn,
                        "SELECT total, done, hit, brand_name FROM ranking_task WHERE id=%s",
                        (tid,))
                    if rt:
                        stat["total"] = int(rt.get("total") or 0)
                        stat["ok"] = int(rt.get("done") or 0)
                        stat["fail"] = max(0, stat["total"] - stat["ok"])
                        stat["models_list"] = "已分析"
                except Exception:
                    pass
            items.append({
                "type": "ranking", "type_label": "排名分析",
                "sched_id": r["sched_id"],
                "account_name": r.get("company_name") or f"账号#{r.get('account_id')}",
                "run_time": r.get("run_time") or "—",
                "last_run_at": str(r.get("last_run_at") or ""),
                "status": r.get("last_status") or "—",
                "task_id": (tid or "")[:12],
                **stat,
            })
    except Exception as e:
        logger.exception("[email_notify] overnight ranking runs failed: %s", e)

    # ── 批量流水线调度（直接查 pipeline_execution，一天可多次）──
    try:
        import json as _j
        rows = db._fetchall(conn,
            """SELECT pe.id AS exec_id, pe.sched_id, pe.account_id, a.company_name,
                      pe.status, pe.step_results, pe.started_at, pe.finished_at
               FROM pipeline_execution pe
               LEFT JOIN account a ON a.id=pe.account_id
               WHERE LEFT(pe.started_at, 10)=%s
               ORDER BY pe.started_at""",
            (today_str,))
        for r in rows:
            # 解析 step_results 抓 keyword step 的 taskId
            stat = {"kw_count": 0, "model_count": 0, "total": 0, "ok": 0, "fail": 0, "models_list": ""}
            kw_task_id = ""
            steps_label_parts = []
            try:
                steps = _j.loads(r.get("step_results") or "[]")
                for st in steps:
                    if isinstance(st, dict):
                        steps_label_parts.append(st.get("type") or "")
                        if st.get("type") == "keyword" and st.get("taskId"):
                            kw_task_id = st["taskId"]
            except Exception:
                pass
            stat["models_list"] = "→".join([s for s in steps_label_parts if s]) or "keyword→ranking"

            if kw_task_id:
                try:
                    sr = db._fetchone(conn,
                        """SELECT COUNT(DISTINCT keyword) AS kw,
                                  COUNT(DISTINCT model) AS mc,
                                  COUNT(*) AS total,
                                  SUM(eventually_succeeded) AS ok
                           FROM (
                              SELECT keyword, model, MAX(success) AS eventually_succeeded
                              FROM search_result WHERE task_id=%s
                              GROUP BY keyword, model
                           ) t""",
                        (kw_task_id,))
                    if sr:
                        stat["kw_count"] = int(sr.get("kw") or 0)
                        stat["model_count"] = int(sr.get("mc") or 0)
                        stat["total"] = int(sr.get("total") or 0)
                        stat["ok"] = int(sr.get("ok") or 0)
                        stat["fail"] = stat["total"] - stat["ok"]
                except Exception:
                    pass

            items.append({
                "type": "pipeline", "type_label": "批量流水线",
                "sched_id": r["sched_id"],
                "account_name": r.get("company_name") or f"账号#{r.get('account_id')}",
                "run_time": str(r.get("started_at") or "")[11:16],
                "last_run_at": str(r.get("finished_at") or r.get("started_at") or ""),
                "status": r.get("status") or "—",
                "task_id": (kw_task_id or "")[:12],
                **stat,
            })
    except Exception as e:
        logger.exception("[email_notify] overnight pipeline runs failed: %s", e)

    # ── 周报 / 引用源 / 报价（这些通常体量小，列出有/无即可）──
    for tbl, type_key, type_label in [
        ("scheduled_weekly_report_task", "weekly_report", "周报生成"),
        ("scheduled_citation_task",      "citation",       "引用源抓取"),
        ("scheduled_quote_task",         "quote",          "报价生成"),
    ]:
        try:
            rows = db._fetchall(conn,
                f"""SELECT s.id AS sched_id, s.account_id, a.company_name,
                           s.run_time, s.last_run_at, s.last_status
                    FROM {tbl} s
                    LEFT JOIN account a ON a.id=s.account_id
                    WHERE s.enabled=1 AND LEFT(s.last_run_at, 10)=%s
                    ORDER BY s.last_run_at""",
                (today_str,))
            for r in rows:
                items.append({
                    "type": type_key, "type_label": type_label,
                    "sched_id": r["sched_id"],
                    "account_name": r.get("company_name") or f"账号#{r.get('account_id')}",
                    "run_time": r.get("run_time") or "—",
                    "last_run_at": str(r.get("last_run_at") or ""),
                    "status": r.get("last_status") or "—",
                    "task_id": "",
                    "kw_count": 0, "model_count": 0, "total": 0, "ok": 0, "fail": 0,
                    "models_list": "",
                })
        except Exception:
            pass

    items.sort(key=lambda x: x["last_run_at"])
    # 汇总指标
    total_runs = len(items)
    ok_runs = sum(1 for x in items if _classify_status(x["status"]) == "success")
    fail_runs = sum(1 for x in items if _classify_status(x["status"]) == "fail")
    sum_total = sum(x["total"] for x in items)
    sum_ok = sum(x["ok"] for x in items)
    return {
        "items": items,
        "total_runs": total_runs,
        "ok_runs": ok_runs,
        "fail_runs": fail_runs,
        "sum_total": sum_total,
        "sum_ok": sum_ok,
    }


def _gather_keyword_search_detail(date_str: str) -> dict:
    """采集某日各客户的查词明细：实际查询条数 + 关键词数 + 平台数 + 成功/失败。
    数据源：search_result 表。
    **必须按 (keyword, model) 去重**——重试/补查会写多条 search_result，
    若直接 COUNT(*) 会把同一(关键词×平台)算两遍，导致总数翻倍。
    每对取 MAX(success) 作为"最终成功"语义。
    """
    conn = db.get_conn()
    try:
        # 内层：按 (account_id, keyword, model) 去重，MAX(success) 表示"最终是否成功"
        # 外层：按 account 聚合
        rows = db._fetchall(conn,
            """SELECT t.account_id,
                      a.company_name,
                      COUNT(DISTINCT t.keyword) AS kw_count,
                      COUNT(DISTINCT t.model)   AS model_count,
                      COUNT(*)                  AS total,
                      SUM(t.eventually_succeeded) AS ok,
                      GROUP_CONCAT(DISTINCT t.model ORDER BY t.model) AS models
               FROM (
                   SELECT account_id, keyword, model, MAX(success) AS eventually_succeeded
                   FROM search_result
                   WHERE search_date=%s
                   GROUP BY account_id, keyword, model
               ) t
               LEFT JOIN account a ON a.id=t.account_id
               GROUP BY t.account_id, a.company_name
               ORDER BY total DESC""",
            (date_str,))
    except Exception as e:
        logger.exception("[email_notify] keyword_search_detail failed: %s", e)
        return {"rows": [], "total_queries": 0, "total_ok": 0, "total_fail": 0, "total_keywords": 0}

    out_rows = []
    total_q = total_ok = total_fail = total_kw = 0
    for r in rows:
        ok = int(r.get("ok") or 0)
        total = int(r.get("total") or 0)
        fail = total - ok
        kw = int(r.get("kw_count") or 0)
        out_rows.append({
            "account_id":   r.get("account_id"),
            "company_name": r.get("company_name") or f"账号#{r.get('account_id')}",
            "kw_count":     kw,
            "model_count":  int(r.get("model_count") or 0),
            "total":        total,
            "ok":           ok,
            "fail":         fail,
            "ok_rate":      int(round(ok * 100 / max(1, total))),
            "models":       (r.get("models") or "").replace(",", " · "),
        })
        total_q += total
        total_ok += ok
        total_fail += fail
        total_kw += kw
    return {
        "rows": out_rows,
        "total_queries": total_q,
        "total_ok": total_ok,
        "total_fail": total_fail,
        "total_keywords": total_kw,
    }


# ═══════════════ HTML 渲染 ═══════════════

def build_email_data() -> dict:
    """组装邮件渲染所需的数据。"""
    today = datetime.now().strftime("%Y-%m-%d")
    yesterday = (datetime.now() - timedelta(days=1)).strftime("%Y-%m-%d")

    scheduled = _gather_scheduled_tasks()
    today_due = _gather_today_due(scheduled, today)
    yest = _gather_yesterday_executions(yesterday)
    today_outline = _gather_today_outline(today)

    # 今日凌晨已执行的定时调度（核心 KPI，邮件最显眼分块）
    overnight = _gather_overnight_runs(today)

    # 按客户聚合的实际查询明细
    yest_kw_detail = _gather_keyword_search_detail(yesterday)
    today_kw_detail = _gather_keyword_search_detail(today)

    # 异常计数（用于标题）
    err_count = len(yest["errors"])
    today_due_count = len(today_due)

    return {
        "today": today,
        "yesterday": yesterday,
        "today_weekday": ["周一","周二","周三","周四","周五","周六","周日"][datetime.now().weekday()],
        "scheduled_total": len(scheduled),
        "today_due": today_due,
        "today_due_count": today_due_count,
        "yest_summary": yest["summary"],
        "yest_errors": yest["errors"],
        "yest_error_count": err_count,
        "today_outline": today_outline,
        "yest_kw_detail": yest_kw_detail,
        "today_kw_detail": today_kw_detail,
        "overnight": overnight,
        "generated_at": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
    }


def render_email_html(data: dict) -> str:
    tpl = _env.get_template("email_daily_report.html.j2")
    return tpl.render(**data)


def build_subject(data: dict) -> str:
    ov = data.get("overnight") or {}
    overnight_summary = ""
    if ov.get("total_runs", 0) > 0:
        if ov.get("fail_runs", 0) > 0:
            overnight_summary = f"｜凌晨执行 {ov['ok_runs']}/{ov['total_runs']}（⚠ {ov['fail_runs']} 失败）"
        else:
            overnight_summary = f"｜凌晨执行 {ov['ok_runs']}/{ov['total_runs']} 全部成功"
    else:
        overnight_summary = "｜⚠ 凌晨无调度执行"
    err_tag = f" ｜昨日异常 {data['yest_error_count']}" if data.get("yest_error_count", 0) > 0 else ""
    return f"【GEO 系统日报】{data['today']}（{data['today_weekday']}）{overnight_summary}{err_tag}"


# ═══════════════ SMTP 发送 ═══════════════

def _send_via_smtp(subject: str, html_body: str, to_list: list[str],
                   plain_fallback: Optional[str] = None,
                   override_settings: Optional[dict] = None) -> dict:
    """发送邮件，返回 {ok: bool, sent_to: [...], error: str}"""
    s = override_settings or _get_settings()
    host = s.get("email_smtp_host") or "smtp.126.com"
    try:
        port = int(s.get("email_smtp_port") or 465)
    except Exception:
        port = 465
    user = s.get("email_smtp_user") or ""
    pwd  = s.get("email_smtp_pass") or ""
    sender = s.get("email_from") or user

    if not user or not pwd:
        return {"ok": False, "sent_to": [], "error": "SMTP 用户名或授权码未配置"}
    if not to_list:
        return {"ok": False, "sent_to": [], "error": "收件人列表为空"}

    msg = MIMEMultipart("alternative")
    msg["Subject"] = Header(subject, "utf-8")
    # sender 可能是 "显示名 <email>" 或纯 email；formataddr 第二项必须是 ASCII 邮箱
    from email.utils import parseaddr as _parseaddr
    _disp, _addr = _parseaddr(sender)
    _display = _disp or "GEO 运营系统"
    msg["From"] = formataddr((str(Header(_display, "utf-8")), _addr or sender))
    msg["To"] = ", ".join(to_list)

    plain = plain_fallback or (subject + "\n\n请在支持 HTML 的客户端中查看完整报告。")
    msg.attach(MIMEText(plain, "plain", "utf-8"))
    msg.attach(MIMEText(html_body, "html", "utf-8"))

    try:
        ctx = ssl.create_default_context()
        with smtplib.SMTP_SSL(host, port, context=ctx, timeout=30) as srv:
            srv.login(user, pwd)
            srv.sendmail(sender, to_list, msg.as_string())
        logger.info("[email_notify] sent OK to %d recipient(s)", len(to_list))
        return {"ok": True, "sent_to": to_list, "error": ""}
    except Exception as exc:
        logger.exception("[email_notify] SMTP 发送失败")
        return {"ok": False, "sent_to": [], "error": f"{type(exc).__name__}: {exc}"}


# ═══════════════ 公开入口 ═══════════════

def send_daily(force: bool = False) -> dict:
    """发送每日报告。force=True 时跳过"今日已发送"检查。"""
    s = _get_settings()
    if (s.get("email_notify_enabled") or "0") != "1":
        return {"ok": False, "skipped": "通知未启用", "sent_to": []}

    missing = _missing_required(s)
    if missing:
        return {"ok": False, "error": f"邮件配置缺失: {', '.join(missing)}", "sent_to": []}

    today = datetime.now().strftime("%Y-%m-%d")
    if not force and s.get("email_last_sent_date") == today:
        return {"ok": True, "skipped": "今日已发送过", "sent_to": []}

    to_list = _parse_to_list(s.get("email_to") or "")
    if not to_list:
        return {"ok": False, "skipped": "收件人为空", "sent_to": []}

    data = build_email_data()
    html = render_email_html(data)
    subject = build_subject(data)

    result = _send_via_smtp(subject, html, to_list, override_settings=s)
    if result["ok"]:
        try:
            db.save_settings({"email_last_sent_date": today})
        except Exception:
            logger.exception("save email_last_sent_date failed")
        # 同步推一份到微信（Server酱）；失败不影响 result["ok"]
        try:
            wechat = _push_serverchan(subject, _build_wechat_summary(data))
            result["wechat"] = wechat
        except Exception as exc:
            logger.exception("Server酱推送异常")
            result["wechat"] = {"ok": False, "error": str(exc)}
    return result


def send_test(to_list: Optional[list[str]] = None) -> dict:
    """立即发送一封测试邮件（不修改 last_sent_date，可重复触发）"""
    s = _get_settings()
    missing = _missing_required(s)
    # 当显式传入 to_list 时只跳过 email_to 缺失项的检查（其余 SMTP 凭证仍必需）
    if to_list:
        missing = [k for k in missing if k != "email_to"]
    if missing:
        return {"ok": False, "error": f"邮件配置缺失: {', '.join(missing)}"}
    targets = to_list or _parse_to_list(s.get("email_to") or "")
    if not targets:
        return {"ok": False, "error": "收件人列表为空"}

    data = build_email_data()
    html = render_email_html(data)
    subject = "【测试】" + build_subject(data)
    result = _send_via_smtp(subject, html, targets, override_settings=s)
    if result["ok"]:
        try:
            wechat = _push_serverchan(subject, _build_wechat_summary(data))
            result["wechat"] = wechat
        except Exception as exc:
            logger.exception("Server酱推送异常")
            result["wechat"] = {"ok": False, "error": str(exc)}
    return result


def check_and_send_if_due() -> Optional[dict]:
    """scheduler_daemon 每 tick 调用：判断是否到点 + 当日未发送，是则发送一次。
    返回 None 表示不到点；返回 {ok, ...} 表示尝试过发送。
    """
    s = _get_settings()
    if (s.get("email_notify_enabled") or "0") != "1":
        return None
    today = datetime.now().strftime("%Y-%m-%d")
    if s.get("email_last_sent_date") == today:
        return None

    send_time = (s.get("email_send_time") or "08:00").strip()
    try:
        hh, mm = send_time.split(":")
        target_minutes = int(hh) * 60 + int(mm)
    except Exception:
        return None
    now = datetime.now()
    now_minutes = now.hour * 60 + now.minute
    # 只要当日已到设置时间且尚未发送，就触发（防止 daemon 假死/重启错过窄窗口；
    # 配合 last_sent_date 确保每日只发一次）
    if now_minutes < target_minutes:
        return None
    return send_daily()
