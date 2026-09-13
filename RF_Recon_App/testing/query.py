from fcc_database import FCCDatabaseManager
import math

def should_auto_flag_station(s):
    dist_km = s.get('distance_km')
    erp = s.get('erp')
    ch = s.get('channel')
    
    if dist_km is None:
        return True
        
    dist_miles = dist_km * 0.621371
    
    # Public Safety / T-Band injections
    if s.get('is_public_safety'):
        if dist_miles <= 60.0:
            return True
        return False
    
    if erp == 'N/A' or erp is None:
        if dist_miles <= 10.0:
            return True
        return False
        
    try:
        erp_float = float(erp)
    except (ValueError, TypeError):
        if dist_miles <= 10.0:
            return True
        return False
        
    if dist_km >= 100.0 and erp_float < 175.0:
        return False
        
    if 2 <= ch <= 13: # VHF
        effective_erp = min(erp_float, 316.0)
        radius_km = 80 * math.sqrt(effective_erp / 316.0)
        radius_miles = radius_km * 0.621371
        if math.floor(radius_miles) >= math.floor(dist_miles):
            return True
    elif ch >= 14: # UHF
        radius_km = 82 * math.sqrt(erp_float / 1000.0)
        radius_miles = radius_km * 0.621371
        if math.floor(radius_miles) >= math.floor(dist_miles):
            return True
            
    return False

db = FCCDatabaseManager()
stations = db.get_stations_near_zip('20148')

valid = []
for s in stations:
    if 2 <= s['channel'] <= 36:
        if should_auto_flag_station(s):
            valid.append(s)
            
# Deduplicate
best = {}
for s in valid:
    ch = s['channel']
    erp = float('inf') if s.get('is_public_safety') else (float(s.get('erp', 0)) if s.get('erp') not in ('N/A', None) else 0.0)
    if ch not in best or erp > best[ch][1]:
        best[ch] = (s, erp)

dedup = [v[0] for v in best.values()]
dedup.sort(key=lambda x: x['channel'])

print("Channels found:", [s['channel'] for s in dedup])
for s in dedup:
    print(f"Ch: {s['channel']:02d} | Call: {s['call_sign']:<10} | ERP: {str(s['erp']):<6} | Dist: {s['distance_km']} km")
