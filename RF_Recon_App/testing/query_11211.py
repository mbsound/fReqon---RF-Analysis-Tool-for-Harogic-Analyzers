import sys
from fcc_database import FCCDatabaseManager
from gui import MainWindow
from PyQt6.QtWidgets import QApplication

app = QApplication(sys.argv)
win = MainWindow()

db = FCCDatabaseManager()
stations = db.get_stations_near_zip('11211')

best_stations = {}
for s in stations:
    ch = s.get('channel')
    erp = s.get('erp')
    if erp == 'N/A' or erp is None:
        erp_val = -1.0
    else:
        try:
            erp_val = float(erp)
        except ValueError:
            erp_val = -1.0
    
    if ch not in best_stations:
        best_stations[ch] = (erp_val, s)
    else:
        if erp_val > best_stations[ch][0]:
            best_stations[ch] = (erp_val, s)
            
dedup_stations = [v[1] for v in best_stations.values()]
dedup_stations.sort(key=lambda s: s.get('channel', 0))

print("Our Deduplicated Stations (Before Threshold):")
for s in dedup_stations:
    if s.get('channel') is not None and 14 <= s['channel'] <= 36:
        print(f"Ch: {s['channel']:2} | Call: {s['call_sign']:8} | ERP: {s['erp']} | Dist: {s['distance_km']} | PS: {s['is_public_safety']}")

print("\nStations that pass should_auto_flag_station:")
for s in dedup_stations:
    if s.get('channel') is not None and 14 <= s['channel'] <= 36:
        if win.should_auto_flag_station(s):
            print(f"Ch: {s['channel']:2} | Call: {s['call_sign']:8} | ERP: {s['erp']} | Dist: {s['distance_km']} | PS: {s['is_public_safety']}")

