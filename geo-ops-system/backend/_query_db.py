"""
直接查询 search_task 和 history 的关联数据
输出到文件以便查看
"""
import pymysql
import sys
from datetime import datetime

DB_CONFIG = {
    'host': '127.0.0.1',
    'port': 3306,
    'user': 'geo_system',
    'password': '',
    'database': 'geo_system',
    'charset': 'utf8mb4'
}

output_file = r'C:\Users\Administrator\Desktop\geo-ops-system\_db_query_result.txt'

try:
    conn = pymysql.connect(**DB_CONFIG, cursorclass=pymysql.cursors.DictCursor)
    cur = conn.cursor()
    
    lines = []
    lines.append("=" * 80)
    lines.append(f"查询时间: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    lines.append("=" * 80)
    
    # 1. 查询最新5条历史记录及其关联的search_task
    lines.append("\n【1】最新历史记录与 search_task 关联:")
    lines.append("-" * 80)
    
    cur.execute("""
        SELECT 
            h.id as hist_id,
            h.sched_id,
            h.task_id,
            h.started_at as hist_started,
            h.finished_at as hist_finished,
            h.duration_seconds as hist_duration,
            h.trigger_type,
            h.status as hist_status,
            h.created_at as hist_created,
            s.created_at as task_created,
            s.completed_at as task_completed,
            s.status as task_status
        FROM scheduled_task_history h
        LEFT JOIN search_task s ON h.task_id = s.id
        ORDER BY h.id DESC 
        LIMIT 5
    """)
    
    rows = cur.fetchall()
    
    for row in rows:
        lines.append(f"\n--- History #{row['hist_id']} ({row['trigger_type']}) ---")
        lines.append(f"  task_id: {row['task_id']}")
        lines.append(f"  History: started={row['hist_started']}, finished={row['hist_finished']}, duration={row['hist_duration']}s")
        lines.append(f"  created_at: {row['hist_created']}")
        
        if row.get('task_created'):
            lines.append(f"  SearchTask: created={row['task_created']}, completed={row['task_completed']}, status={row['task_status']}")
            
            # 计算真实耗时
            if row['task_created'] and row['task_completed']:
                try:
                    start_dt = datetime.strptime(str(row['task_created'])[:19], "%Y-%m-%d %H:%M:%S")
                    end_dt = datetime.strptime(str(row['task_completed'])[:19], "%Y-%m-%d %H:%M:%S")
                    real_duration = int((end_dt - start_dt).total_seconds())
                    lines.append(f"  ✅ 真实耗时: {real_duration} 秒")
                except Exception as e:
                    lines.append(f"  ❌ 时间解析失败: {e}")
            else:
                lines.append(f"  ⚠️ task_completed 为空")
        else:
            lines.append(f"  ⚠️ 无关联的 search_task 数据 (LEFT JOIN 无匹配)")
    
    # 2. 查询最新的 search_task 记录
    lines.append("\n\n【2】最新5条 search_task 记录:")
    lines.append("-" * 80)
    
    cur.execute("""
        SELECT id, status, created_at, completed_at, 
               TIMESTAMPDIFF(SECOND, created_at, COALESCE(completed_at, NOW())) as calc_duration
        FROM search_task 
        ORDER BY id DESC 
        LIMIT 5
    """)
    
    tasks = cur.fetchall()
    for t in tasks:
        lines.append(f"  #{t['id'][:12]}... | status={t['status']} | "
                     f"created={t['created_at']} | completed={t['completed_at']} | "
                     f"calc_duration={t['calc_duration']}s")
    
    # 3. 统计
    lines.append("\n\n【3】统计信息:")
    lines.append("-" * 80)
    
    cur.execute("""
        SELECT COUNT(*) as total, 
               SUM(CASE WHEN duration_seconds <= 1 THEN 1 ELSE 0 END) as zero_count,
               SUM(CASE WHEN duration_seconds > 1 THEN 1 ELSE 0 END) as ok_count,
               AVG(duration_seconds) as avg_duration
        FROM scheduled_task_history 
        WHERE created_at >= DATE_SUB(NOW(), INTERVAL 2 HOUR)
    """)
    stats = cur.fetchone()
    lines.append(f"最近2小时统计:")
    lines.append(f"  总记录数: {stats['total']}")
    lines.append(f"  duration<=1: {stats['zero_count']}")
    lines.append(f"  duration>1: {stats['ok_count']}")
    lines.append(f"  平均duration: {stats['avg_duration']}")
    
    # 4. 检查触发器是否存在
    lines.append("\n\n【4】触发器状态:")
    lines.append("-" * 80)
    
    cur.execute("SHOW TRIGGERS LIKE 'scheduled_task_history'")
    triggers = cur.fetchall()
    if triggers:
        for trig in triggers:
            lines.append(f"  触发器: {trig.get('Trigger', 'N/A')}")
    else:
        lines.append("  ⚠️ 未找到触发器!")
    
    conn.close()
    
    # 写入文件
    with open(output_file, 'w', encoding='utf-8') as f:
        f.write('\n'.join(lines))
    
    print(f"[OK] 结果已写入: {output_file}")
    print(f"[OK] 共查询 {len(rows)} 条历史记录")
    
except Exception as e:
    with open(output_file, 'w', encoding='utf-8') as f:
        f.write(f"[ERROR] {e}\n{str(sys.exc_info())}")
    print(f"[ERROR] {e}")
