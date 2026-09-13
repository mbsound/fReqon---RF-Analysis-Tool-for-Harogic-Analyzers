import math
import pgeocode

def _haversine(lat1, lon1, lat2, lon2):
    R = 6371.0
    dlat = math.radians(lat2 - lat1)
    dlon = math.radians(lon2 - lon1)
    a = math.sin(dlat / 2)**2 + math.cos(math.radians(lat1)) * math.cos(math.radians(lat2)) * math.sin(dlon / 2)**2
    c = 2 * math.atan2(math.sqrt(a), math.sqrt(1 - a))
    return R * c

nomi = pgeocode.Nominatim('us')
res = nomi.query_postal_code("20148")
target_lat = res.latitude
target_lon = res.longitude

print("Dist to Pittsburgh:", _haversine(target_lat, target_lon, 40.4406, -79.9959))
print("Dist to Philadelphia:", _haversine(target_lat, target_lon, 39.9526, -75.1652))
