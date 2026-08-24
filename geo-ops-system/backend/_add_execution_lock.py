"""
添加 execution_lock 字段到 scheduled_search_task 表
用于防止 API 和调度器并发执行同一任务
"""
import mysql.connector

conn = mysql.connector.connect(host='127.0.0.1', port=3306, user='geo_system', password='', database='geo_system')
cur = conn.cursor()

# 检查是否已有 execution_lock 列
cur.execute("SHOW COLUMNS FROM scheduled_search_task LIKE 'execution_lock'")
existing = cur.fetchall()

if existing:
    print(f"execution_lock 列已存在: {existing[0]}")
else:
    # 添加列
    try:
        cur.execute("""
            ALTER TABLE scheduled_search_task 
            ADD COLUMN execution_lock VARCHAR(20) DEFAULT NULL 
            COMMENT '执行锁: api/manual/scheduler, 防止并发执行'
        """)
        conn.commit()
        print("✓ 已添加 execution_lock 列")
    except Exception as e:
        print(f"✗ 添加列失败: {e}")
        conn.rollback()

# 验证
cur.execute("DESCRIBE scheduled_search_task")
print("\n=== 更新后的表结构(最后几列) ===")
for row in cur.fetchall():
    if row[0] in ('execution_lock', 'is_triggering', 'manual_trigger_pending', 'next_run_at'):
        print(f"  {row[0]}: {row[1]}")

conn.close()
