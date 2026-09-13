import os
import time
import sqlite3
import zipfile
import urllib.request
import pgeocode
import math
import threading

T_BAND_CITIES = [
    {"name": "Boston, MA", "lat": 42.3601, "lon": -71.0589, "channels": [14, 16]},
    {"name": "Chicago, IL", "lat": 41.8781, "lon": -87.6298, "channels": [14, 15]},
    {"name": "Dallas, TX", "lat": 32.7767, "lon": -96.7970, "channels": [16]},
    {"name": "Houston, TX", "lat": 29.7604, "lon": -95.3698, "channels": [17]},
    {"name": "Los Angeles, CA", "lat": 34.0522, "lon": -118.2437, "channels": [14, 15, 16, 20]},
    {"name": "Miami, FL", "lat": 25.7617, "lon": -80.1918, "channels": [14]},
    {"name": "New York, NY", "lat": 40.7128, "lon": -74.0060, "channels": [14, 15, 16, 19]},
    {"name": "Philadelphia, PA", "lat": 39.9526, "lon": -75.1652, "channels": [19, 20]},
    {"name": "Pittsburgh, PA", "lat": 40.4406, "lon": -79.9959, "channels": [14, 18]},
    {"name": "San Francisco, CA", "lat": 37.7749, "lon": -122.4194, "channels": [16, 17]},
    {"name": "Washington, DC", "lat": 38.9072, "lon": -77.0369, "channels": [17, 18]}
]

class FCCDatabaseManager:
    def __init__(self, db_path="fcc_tv.db"):
        self.db_path = db_path
        self.download_url = "https://enterpriseefiling.fcc.gov/dataentry/api/download/dbfile/Current_LMS_Dump.zip"
        self.last_update_key = "last_update"
        self.cache_days = 7
        self.is_downloading = False
        
        self._init_db()

    def _init_db(self):
        self.conn = sqlite3.connect(self.db_path, check_same_thread=False)
        cursor = self.conn.cursor()
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS metadata (
                key TEXT PRIMARY KEY,
                value TEXT
            )
        """)
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS stations (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                application_id TEXT,
                service TEXT,
                lms_application_id TEXT,
                call_sign TEXT,
                lat REAL,
                lon REAL,
                channel INTEGER,
                erp REAL,
                is_public_safety BOOLEAN DEFAULT 0
            )
        """)
        self.conn.commit()

    def get_last_update_time(self):
        cursor = self.conn.cursor()
        cursor.execute("SELECT value FROM metadata WHERE key=?", (self.last_update_key,))
        row = cursor.fetchone()
        if row:
            try:
                return float(row[0])
            except ValueError:
                return 0.0
        return 0.0

    def needs_update(self):
        last_update = self.get_last_update_time()
        if last_update == 0.0:
            return True
        days_since_update = (time.time() - last_update) / (24 * 3600)
        return days_since_update > self.cache_days
        
    def has_data(self):
        cursor = self.conn.cursor()
        cursor.execute("SELECT COUNT(*) FROM stations")
        return cursor.fetchone()[0] > 0

    def download_and_update_async(self, progress_callback=None, completion_callback=None):
        if self.is_downloading:
            return
        
        self.is_downloading = True
        
        def _task():
            try:
                self.download_and_update(progress_callback)
                if completion_callback:
                    completion_callback(True)
            except Exception as e:
                print(f"Error in async FCC DB download: {e}")
                if completion_callback:
                    completion_callback(False)
            finally:
                self.is_downloading = False
                
        t = threading.Thread(target=_task)
        t.daemon = True
        t.start()

    def download_and_update(self, progress_callback=None):
        """
        Downloads the FCC database and populates the local SQLite DB.
        """
        if progress_callback:
            progress_callback(0, "Downloading FCC LMS Database...")
            
        zip_path = "fcc_temp.zip"
        try:
            # Download file
            import requests
            
            headers = {'User-Agent': 'python-urllib/3.10'}
            
            # Check for partial download
            file_mode = 'wb'
            initial_size = 0
            if os.path.exists(zip_path):
                initial_size = os.path.getsize(zip_path)
                headers['Range'] = f'bytes={initial_size}-'
                file_mode = 'ab'
                
            try:
                with requests.get(self.download_url, headers=headers, stream=True, timeout=10) as r:
                    if r.status_code == 416: # Range not satisfiable (already fully downloaded)
                        pass
                    else:
                        r.raise_for_status()
                        if r.status_code == 200 and initial_size > 0:
                            # Server ignored Range header, rewrite from scratch
                            file_mode = 'wb'
                            initial_size = 0
                            
                        total_size = int(r.headers.get('content-length', 0)) + initial_size
                        downloaded = initial_size
                        
                        with open(zip_path, file_mode) as f:
                            for chunk in r.iter_content(chunk_size=1024 * 1024): # 1MB chunks
                                if chunk:
                                    f.write(chunk)
                                    downloaded += len(chunk)
                                    if progress_callback and total_size > 0:
                                        pct = int((downloaded / total_size) * 30)
                                        pct = max(0, min(30, pct))
                                        mb_down = downloaded // (1024*1024)
                                        mb_tot = total_size // (1024*1024)
                                        progress_callback(pct, f"Downloading FCC Database... ({mb_down}/{mb_tot} MB)")
            except Exception as e:
                print(f"Error downloading: {e}")
                # If resume failed, delete temp file so next time it starts fresh
                if os.path.exists(zip_path):
                    os.remove(zip_path)
                raise e
            
            if progress_callback:
                progress_callback(30, "Parsing FCC Database (Pass 1/5)...")
                
            cursor = self.conn.cursor()
            cursor.execute("DELETE FROM stations")
            
            # Extract true data from LMS Dump
            ant_to_erp = {}
            with zipfile.ZipFile(zip_path, 'r') as z:
                if 'app_antenna_frequency.dat' in z.namelist():
                    with z.open('app_antenna_frequency.dat') as f:
                        headers = f.readline().decode('utf-8').strip().split('|')
                        ant_idx = headers.index('aafq_aant_antenna_record_id')
                        erp_idx = headers.index('aafq_power_erp_kw')
                        max_erp_idx = headers.index('aafq_max_erp_kw')
                        for line in f:
                            parts = line.decode('utf-8', errors='ignore').split('|')
                            if len(parts) > max(ant_idx, max_erp_idx):
                                val = parts[erp_idx].strip()
                                if not val: val = parts[max_erp_idx].strip()
                                if val:
                                    try:
                                        ant_to_erp[parts[ant_idx]] = float(val)
                                    except ValueError:
                                        pass
                                        
            if progress_callback: progress_callback(45, "Parsing FCC Database (Pass 2/5)...")
            
            loc_to_erp = {}
            with zipfile.ZipFile(zip_path, 'r') as z:
                if 'app_antenna.dat' in z.namelist():
                    with z.open('app_antenna.dat') as f:
                        headers = f.readline().decode('utf-8').strip().split('|')
                        loc_idx = headers.index('aant_aloc_loc_record_id')
                        ant_idx = headers.index('aant_antenna_record_id')
                        for line in f:
                            parts = line.decode('utf-8', errors='ignore').split('|')
                            if len(parts) > max(loc_idx, ant_idx):
                                erp = ant_to_erp.get(parts[ant_idx])
                                if erp is not None:
                                    loc_to_erp[parts[loc_idx]] = erp
            ant_to_erp.clear() # save memory
            
            if progress_callback: progress_callback(60, "Parsing FCC Database (Pass 3/4)...")
            
            fac_info = {}
            with zipfile.ZipFile(zip_path, 'r') as z:
                if 'facility.dat' in z.namelist():
                    with z.open('facility.dat') as f:
                        headers = f.readline().decode('utf-8').strip().split('|')
                        fac_id_idx = headers.index('facility_id')
                        stat_idx = headers.index('facility_status')
                        call_idx = headers.index('callsign')
                        chan_idx = headers.index('channel')
                        act_idx = headers.index('active_ind')
                        
                        for line in f:
                            parts = line.decode('utf-8', errors='ignore').split('|')
                            if len(parts) > max(fac_id_idx, chan_idx, stat_idx, act_idx, call_idx):
                                if parts[act_idx] != 'Y' or parts[stat_idx] != 'LICEN':
                                    continue
                                fac_id = parts[fac_id_idx].strip()
                                try:
                                    chan = int(parts[chan_idx])
                                    if 7 <= chan <= 36:
                                        callsign = parts[call_idx].strip()
                                        if fac_id and callsign:
                                            fac_info[fac_id] = {
                                                'channel': chan,
                                                'callsign': callsign
                                            }
                                except ValueError:
                                    pass

            if progress_callback: progress_callback(75, "Parsing FCC Database (Pass 4/5)...")
            
            app_to_info = {}
            with zipfile.ZipFile(zip_path, 'r') as z:
                if 'application_facility.dat' in z.namelist():
                    with z.open('application_facility.dat') as f:
                        headers = f.readline().decode('utf-8').strip().split('|')
                        app_idx = headers.index('afac_application_id')
                        fac_idx = headers.index('afac_facility_id')
                        act_idx = headers.index('active_ind')
                        
                        for line in f:
                            parts = line.decode('utf-8', errors='ignore').split('|')
                            if len(parts) > max(app_idx, fac_idx, act_idx):
                                if parts[act_idx] == 'Y':
                                    fac_id = parts[fac_idx].strip()
                                    if fac_id in fac_info:
                                        app_to_info[parts[app_idx].strip()] = fac_info[fac_id]
            
            if progress_callback: progress_callback(90, "Writing FCC Database (Pass 5/5)...")

            stations_to_insert = []
            with zipfile.ZipFile(zip_path, 'r') as z:
                if 'app_location.dat' in z.namelist():
                    with z.open('app_location.dat') as f:
                        headers = f.readline().decode('utf-8').strip().split('|')
                        app_idx = headers.index('aloc_aapp_application_id')
                        loc_idx = headers.index('aloc_loc_record_id')
                        lat_deg_idx = headers.index('aloc_lat_deg')
                        lat_min_idx = headers.index('aloc_lat_mm')
                        lat_sec_idx = headers.index('aloc_lat_ss')
                        lat_dir_idx = headers.index('aloc_lat_dir')
                        lon_deg_idx = headers.index('aloc_long_deg')
                        lon_min_idx = headers.index('aloc_long_mm')
                        lon_sec_idx = headers.index('aloc_long_ss')
                        lon_dir_idx = headers.index('aloc_long_dir')
                        
                        for line in f:
                            parts = line.decode('utf-8', errors='ignore').split('|')
                            if len(parts) > max(app_idx, lon_dir_idx, loc_idx):
                                app_id = parts[app_idx]
                                if app_id in app_to_info:
                                    try:
                                        lat = float(parts[lat_deg_idx]) + float(parts[lat_min_idx])/60.0 + float(parts[lat_sec_idx])/3600.0
                                        if parts[lat_dir_idx] == 'S': lat = -lat
                                        
                                        lon = float(parts[lon_deg_idx]) + float(parts[lon_min_idx])/60.0 + float(parts[lon_sec_idx])/3600.0
                                        if parts[lon_dir_idx] == 'W': lon = -lon
                                        
                                        erp = loc_to_erp.get(parts[loc_idx], 0.0)
                                        info = app_to_info[app_id]
                                        
                                        stations_to_insert.append((
                                            info['callsign'], lat, lon, info['channel'], erp, False
                                        ))
                                        
                                        # Only one location per app 
                                        del app_to_info[app_id]
                                    except ValueError:
                                        pass
                                        
            cursor.executemany("INSERT INTO stations (call_sign, lat, lon, channel, erp, is_public_safety) VALUES (?, ?, ?, ?, ?, ?)",
                               stations_to_insert)
            
            cursor.execute("INSERT OR REPLACE INTO metadata (key, value) VALUES (?, ?)", 
                           (self.last_update_key, str(time.time())))
            self.conn.commit()
            
            if progress_callback:
                progress_callback(100, "FCC Database Update Complete")
                
        except Exception as e:
            print(f"Error updating FCC database: {e}")
            if progress_callback:
                progress_callback(-1, f"Error: {str(e)}")
        finally:
            if os.path.exists(zip_path):
                os.remove(zip_path)

    def _haversine(self, lat1, lon1, lat2, lon2):
        # Calculate distance in km
        R = 6371.0
        dlat = math.radians(lat2 - lat1)
        dlon = math.radians(lon2 - lon1)
        a = math.sin(dlat / 2)**2 + math.cos(math.radians(lat1)) * math.cos(math.radians(lat2)) * math.sin(dlon / 2)**2
        c = 2 * math.atan2(math.sqrt(a), math.sqrt(1 - a))
        return R * c

    def get_stations_near_zip(self, zip_code, radius_km=200):
        # Convert ZIP to Lat/Lon
        nomi = pgeocode.Nominatim('us')
        res = nomi.query_postal_code(zip_code)
        
        if str(res.latitude) == 'nan' or str(res.longitude) == 'nan':
            return []
            
        target_lat = float(res.latitude)
        target_lon = float(res.longitude)
        
        # Spatial bounding box pre-filtering for fast indexing
        lat_delta = radius_km / 111.0
        cos_lat = max(0.1, math.cos(math.radians(target_lat)))
        lon_delta = radius_km / (111.0 * cos_lat)
        
        cursor = self.conn.cursor()
        cursor.execute(
            "SELECT call_sign, lat, lon, channel, erp, is_public_safety FROM stations "
            "WHERE lat BETWEEN ? AND ? AND lon BETWEEN ? AND ?",
            (target_lat - lat_delta, target_lat + lat_delta, target_lon - lon_delta, target_lon + lon_delta)
        )
        
        nearby_stations = []
        for row in cursor.fetchall():
            call_sign, lat, lon, channel, erp, is_ps = row
            if lat is None or lon is None:
                continue
            dist = self._haversine(target_lat, target_lon, lat, lon)
            if dist <= radius_km:
                nearby_stations.append({
                    "call_sign": call_sign,
                    "distance_km": round(dist, 1),
                    "channel": channel,
                    "erp": erp,
                    "is_public_safety": bool(is_ps)
                })
                
        # Inject T-Band Public Safety
        # T-Band operations are protected within an ~80km (50 mile) radius of these centers.
        for city in T_BAND_CITIES:
            dist = self._haversine(target_lat, target_lon, city["lat"], city["lon"])
            if dist <= radius_km: # Default 100km is a good safety buffer
                for ch in city["channels"]:
                    nearby_stations.append({
                        "call_sign": f'LMR {city["name"]}',
                        "distance_km": round(dist, 1),
                        "channel": ch,
                        "erp": "N/A",
                        "is_public_safety": True
                    })
                
        # Sort by distance
        nearby_stations.sort(key=lambda x: x["distance_km"])
        return nearby_stations
