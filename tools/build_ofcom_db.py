"""
build_ofcom_db.py - Rebuild the Ofcom transmitter database that ships with fReqon.

    python tools/build_ofcom_db.py /path/to/700-plan-clearance.xlsx

Download Ofcom's "Television transmitter frequency data" spreadsheet and run this
when Ofcom reissues it. The result (RF_Recon_Modern/ofcom_tv.db) is what a new
installation starts with; users can still import a newer spreadsheet themselves
(Broadcast / DTV > Update UK Data).

Ofcom's data is published under the Open Government Licence v3.0.
"""

import os
import sys

APP = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "RF_Recon_Modern")
sys.path.insert(0, APP)

from core.ofcom_database import OfcomDatabaseManager


def main():
    if len(sys.argv) != 2:
        sys.exit(__doc__)
    target = os.path.abspath(os.path.join(APP, "ofcom_tv.db"))
    if os.path.exists(target):
        os.remove(target)
    db = OfcomDatabaseManager(target)
    count = db.import_excel(sys.argv[1], source="bundled")
    db.conn.execute("VACUUM")
    db.conn.close()
    info = OfcomDatabaseManager(target).info()
    print(f"{target}: {count} records, Ofcom's file of {info['data_date']}, {os.path.getsize(target) // 1024} kB")


if __name__ == "__main__":
    main()
