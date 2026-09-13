import sys
from fcc_database import FCCDatabaseManager

def cb(pct, msg):
    print(f"[{pct}%] {msg}")
    
db = FCCDatabaseManager(db_path="fcc_tv.db")
db.download_and_update(cb)

import sqlite3
conn = sqlite3.connect("fcc_tv.db")
cursor = conn.cursor()
cursor.execute("SELECT call_sign, channel, erp FROM stations WHERE call_sign LIKE '%WNJU%'")
print("WNJU stations found:", cursor.fetchall())
