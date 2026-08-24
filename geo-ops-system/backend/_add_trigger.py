"""
添加数据库触发器防止短时间内重复插入历史记录
"""
import mysql.connector

conn = mysql.connector.connect(host='127.0.0.1', port=3306, user='geo_system', password='', database='geo_system')
cur = conn.cursor()

# 删除已存在的触发器（如果有的话）
try:
    cur.execute("DROP TRIGGER IF EXISTS prevent_duplicate_history")
    print("已删除旧触发器")
except Exception as e:
    print(f"删除触发器: {e}")

# 创建新触发器：在插入前检查是否120秒内已有同sched_id的记录
trigger_sql = """
CREATE TRIGGER prevent_duplicate_history
BEFORE INSERT ON scheduled_task_history
FOR EACH ROW
BEGIN
    DECLARE recent_count INT;
    DECLARE recent_type VARCHAR(20);
    
    -- 查询最近120秒内同一任务的记录
    SELECT COUNT(*), trigger_type INTO recent_count, recent_type
    FROM scheduled_task_history 
    WHERE sched_id = NEW.sched_id 
      AND created_at >= DATE_SUB(NOW(), INTERVAL 120 SECOND)
    LIMIT 1;
    
    -- 如果已有记录：
    -- 1. 如果类型相同，阻止插入
    -- 2. 如果要插入scheduled但已有manual，也阻止
    IF recent_count > 0 THEN
        IF NEW.trigger_type = recent_type OR (NEW.trigger_type = 'scheduled' AND recent_type = 'manual') THEN
            SIGNAL SQLSTATE '45000' SET MESSAGE_TEXT = 'DUPLICATE_PREVENTED: 最近120秒内已有记录';
        END IF;
    END IF;
END;
"""

try:
    cur.execute(trigger_sql)
    conn.commit()
    print("✓ 触发器创建成功！")
except Exception as e:
    print(f"✗ 创建触发器失败: {e}")
    conn.rollback()

# 验证触发器存在
cur.execute("SHOW TRIGGERS LIKE 'scheduled_task_history'")
triggers = cur.fetchall()
print(f"\n当前触发器数量: {len(triggers)}")
for t in triggers:
    print(f"  - {t[0]}")

conn.close()
