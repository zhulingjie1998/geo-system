import pymysql

# Use correct credentials from .env
conn = pymysql.connect(
    host='127.0.0.1',
    port=3306,
    user='geo_system',
    password='',
    database='geo_system'
)
cur = conn.cursor()

# Check if column exists
cur.execute("SHOW COLUMNS FROM scheduled_search_task LIKE 'is_triggering'")
result = cur.fetchone()
if result:
    print(f"Column already exists: {result}")
else:
    # Add the column
    print("Adding is_triggering column...")
    cur.execute("ALTER TABLE scheduled_search_task ADD COLUMN is_triggering TINYINT(1) NOT NULL DEFAULT 0")
    conn.commit()
    print("Column added successfully!")
    
    # Verify
    cur.execute("SHOW COLUMNS FROM scheduled_search_task LIKE 'is_triggering'")
    print(f"Verified: {cur.fetchone()}")

conn.close()
print("Done!")
