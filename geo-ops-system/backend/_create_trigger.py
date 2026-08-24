"""
创建防重复触发器 - 数据库层面彻底解决重复记录问题
"""
import pymysql
from db import get_conn

def create_anti_duplicate_trigger():
    conn = get_conn()
    cur = conn.cursor()
    
    try:
        # 删除旧触发器（如果存在）
        cur.execute("DROP TRIGGER IF EXISTS prevent_duplicate_history_insert")
        
        # 创建新触发器：在 INSERT 前检查是否有120秒内的同 sched_id 记录
        trigger_sql = """
        CREATE TRIGGER prevent_duplicate_history_insert
        BEFORE INSERT ON scheduled_task_history
        FOR EACH ROW
        BEGIN
            DECLARE recent_count INT;
            
            -- 检查120秒内是否已有同 sched_id 的记录
            SELECT COUNT(*) INTO recent_count 
            FROM scheduled_task_history 
            WHERE sched_id = NEW.sched_id 
              AND created_at >= DATE_SUB(NOW(), INTERVAL 120 SECOND);
            
            -- 如果已有记录，阻止插入
            IF recent_count > 0 THEN
                SIGNAL SQLSTATE '45000' 
                    SET MESSAGE_TEXT = 'Duplicate history record within 120 seconds';
            END IF;
        END;
        """
        
        cur.execute(trigger_sql)
        conn.commit()
        print("[OK] 防重复触发器创建成功!")
        
        # 验证触发器
        cur.execute("SHOW TRIGGERS LIKE 'scheduled_task_history'")
        triggers = cur.fetchall()
        for t in triggers:
            print(f"  触发器: {t}")
            
    except Exception as e:
        print(f"[ERROR] 创建触发器失败: {e}")
        conn.rollback()
    finally:
        cur.close()
        conn.close()

if __name__ == "__main__":
    create_anti_duplicate_trigger()
