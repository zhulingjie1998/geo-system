import sys
sys.path.insert(0, '.')
import db

# 检查 scheduled_task_history 表
conn = db.get_conn()
try:
    # 1. 检查表是否存在
    tables = db._fetchall(conn, "SHOW TABLES LIKE 'scheduled_task_history'")
    print(f"Table exists: {bool(tables)}")
    if tables:
        print(f"Table name: {tables[0]}")
    
    # 2. 检查表结构
    if tables:
        cols = db._fetchall(conn, "DESCRIBE scheduled_task_history")
        print(f"\nColumns ({len(cols)}):")
        for c in cols:
            print(f"  - {c}")
    
    # 3. 检查数据
    rows = db._fetchall(conn, "SELECT COUNT(*) as cnt FROM scheduled_task_history")
    print(f"\nTotal records: {rows[0]['cnt'] if rows else 0}")
    
    # 4. 显示最近几条记录
    recent = db._fetchall(conn, "SELECT id, sched_id, status, started_at, task_id FROM scheduled_task_history ORDER BY started_at DESC LIMIT 5")
    print(f"\nRecent records:")
    for r in (recent or []):
        print(f"  ID={r['id']}, sched_id={r['sched_id']}, status={r['status']}, time={r['started_at']}, task_id={r['task_id'][:12] if r['task_id'] else 'None'}...")
    
    # 5. 检查定时任务
    tasks = db._fetchall(conn, "SELECT id, name, account_id FROM scheduled_search_task LIMIT 5")
    print(f"\nScheduled tasks:")
    for t in (tasks or []):
        print(f"  ID={t['id']}, name={t.get('name', 'N/A')}, account_id={t['account_id']}")

except Exception as e:
    print(f"Error: {e}")
    import traceback
    traceback.print_exc()
