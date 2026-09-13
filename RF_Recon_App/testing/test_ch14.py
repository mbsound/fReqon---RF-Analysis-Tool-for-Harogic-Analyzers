import sqlite3

conn = sqlite3.connect("fcc_tv.db")
c = conn.cursor()
c.execute("SELECT * FROM stations WHERE channel = 14")
rows = c.fetchall()
print(f"Total Ch 14 stations: {len(rows)}")
for r in rows[:5]:
    print(r)
