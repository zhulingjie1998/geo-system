"""检查并创建缺失的 KB 表"""
import sys, os
sys.path.insert(0, os.path.dirname(__file__))
import db

conn = db.get_conn()
cur = conn.cursor()

# 检查表是否存在
cur.execute("SHOW TABLES LIKE 'customer_knowledge_kb'")
exists = cur.fetchall()
print(f"customer_knowledge_kb table exists: {len(exists) > 0}")

if not exists:
    print("Creating missing KB tables...")
    from pathlib import Path
    sql = Path("migrations/kb_schema.sql").read_text(encoding="utf-8")
    stmts = db._split_sql_statements(sql)
    print(f"Found {len(stmts)} SQL statements")
    for i, stmt in enumerate(stmts):
        try:
            cur.execute(stmt)
            print(f"  [{i+1}/{len(stmts)}] OK")
        except Exception as e:
            print(f"  [{i+1}/{len(stmts)}] FAILED: {e}")
    conn.commit()
    print("Done! Tables created.")
else:
    print("Table already exists, skipping.")

# 验证
cur.execute("SHOW TABLES LIKE 'customer_knowledge%'")
tables = cur.fetchall()
print(f"\nKB-related tables: {[t for row in tables for t in row.values()]}")
cur.close()
conn.close()
