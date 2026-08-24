import re

with open(r'c:\Users\Administrator\Desktop\geo-ops-system\geo-ops-system\backend\app.py', 'r', encoding='utf-8') as f:
    content = f.read()

# Find the target location
target = '@app.get("/api/search/today-stats")'
idx = content.find(target)
print(f'Found at index: {idx}')

if idx > 0:
    # Show context
    before = content[max(0, idx-80):idx]
    after = content[idx:idx+60]
    print(f'Before: [{before}]')
    print(f'After: [{after}]')
    
    # New code to insert
    new_code = '''

# ═══════════════════════════════════════════════════════════
# 首页概览 — 聚合统计
# ═══════════════════════════════════════════════════════════

@app.get("/api/home/overview")
def api_home_overview():
    """首页聚合数据：KPI 卡片 + 运行中任务 + 近 7 天趋势 + 客户概览"""
    uid = _current_user_id()
    if not uid:
        return jsonify({"error": "Unauthorized"}), 401

    # ── 1. 客户账号数量（正式客户）──
    accounts = db.list_accounts(owner_id=uid, only_formal=True)
    account_count = len(accounts)

    # ── 2. 关键词总量 & 平均值 ──
    total_keywords = 0
    for acc in accounts:
        kws = db.get_keywords(acc["id"])
        total_keywords += len(kws)

    # ── 3. 今日查词统计 ──
    today_stats = db.get_today_search_stats()
    today_data = {
        "totalCount": today_stats.get("totalCount", 0),
        "totalSuccessRate": today_stats.get("totalSuccessRate", 0),
        "totalSuccess": today_stats.get("totalSuccess", 0),
    }

    # ── 4. 运行中任务数 ──
    running_tasks = _get_running_search_tasks()
    running_count = len(running_tasks)

    # ── 5. 运行中的查词任务列表（带客户名称）──
    running_list = []
    for t in running_tasks[:10]:
        acc_info = next((a for a in accounts if a["id"] == t.get("account_id")), None)
        total = t.get("total_queries", 0)
        completed = t.get("completed_queries", 0)
        running_list.append({
            "taskId": t.get("id"),
            "accountName": acc_info.get("companyName") if acc_info else f"客户#{t.get('account_id')}",
            "brand": acc_info.get("brandName", "") if acc_info else "",
            "completed": completed,
            "total": total,
            "progress": round(completed / total * 100) if total else 0,
            "status": t.get("status", ""),
        })

    # ── 6. 近 7 天查词趋势 ──
    trend = _get_7day_trend()

    # ── 7. 客户概览（最近 8 个，带关键词/查词数据）──
    recent_customers = []
    for acc in accounts[:8]:
        kws = db.get_keywords(acc["id"])
        kw_count = len(kws)
        last_dates = db.get_last_search_dates()
        last_date = last_dates.get(str(acc["id"]), "")
        history = db.get_search_history_grouped(acc["id"], limit_dates=999)
        total_searches = sum(h.get("count", 0) for h in history)
        today_count = 0
        today_success = 0
        today_str = _now()[:10]
        for h in history:
            if h.get("date") == today_str:
                today_count = h.get("count", 0)
                today_success = h.get("successCount", 0)
                break
        recent_customers.append({
            "id": acc["id"],
            "companyName": acc.get("companyName", ""),
            "companyBrand": acc.get("brandName", ""),
            "platforms": acc.get("platforms", []) or [],
            "keywordCount": kw_count,
            "totalSearches": total_searches,
            "todayCount": today_count,
            "todaySuccess": today_success,
            "lastSearchDate": last_date or "",
        })

    return jsonify({
        "stats": {
            "accounts": account_count,
            "keywords": total_keywords,
            "searches": 0,
            "runningTasks": running_count,
        },
        "today": today_data,
        "running": running_list,
        "recent": recent_customers,
        "alerts": [],
        "trend": trend,
        "todos": {
            "needSearch": {"count": max(0, account_count - len(trend))} if trend else {"count": account_count},
            "failedTasks": {"count": 0},
        },
    })


def _get_running_search_tasks():
    """获取所有 RUNNING / PENDING 状态的查词任务"""
    conn = db.get_conn()
    rows = db._fetchall(conn,
        "SELECT id, account_id, status, total_queries, completed_queries, "
        "created_at FROM search_task "
        "WHERE status IN ('RUNNING', 'PENDING') "
        "ORDER BY (status='RUNNING') DESC, created_at ASC"
    )
    return [dict(r) for r in rows] if rows else []


def _get_7day_trend():
    """近 7 天每日查词次数趋势"""
    from datetime import datetime as _dt, timedelta as _td
    conn = db.get_conn()
    today = _dt.now().strftime("%Y-%m-%d")
    rows = db._fetchall(conn,
        "SELECT search_date AS date, COUNT(*) AS count "
        "FROM search_result "
        "WHERE search_date >= %s AND search_date <= %s "
        "GROUP BY search_date ORDER BY date ASC",
        ((_dt.now() - _td(days=6)).strftime("%Y-%m-%d"), today),
    )
    result = [dict(r) for r in rows] if rows else []
    date_set = {r["date"] for r in result}
    for i in range(6, -1, -1):
        d = (_dt.now() - _td(days=i)).strftime("%Y-%m-%d")
        if d not in date_set:
            result.append({"date": d, "count": 0})
    result.sort(key=lambda x: x["date"])
    return result


'''

    # Insert before the target
    new_content = content[:idx] + new_code + content[idx:]
    
    with open(r'c:\Users\Administrator\Desktop\geo-ops-system\geo-ops-system\backend\app.py', 'w', encoding='utf-8') as f:
        f.write(new_content)
    
    print(f'Success! Inserted {len(new_code)} chars before index {idx}')
else:
    print('Target not found!')
