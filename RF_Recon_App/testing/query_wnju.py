import sqlite3
conn = sqlite3.connect('fcc_tv.db')
cursor = conn.cursor()
cursor.execute("SELECT * FROM stations WHERE call_sign LIKE '%WNJU%' LIMIT 10;")
for row in cursor.fetchall():
    print(row)
