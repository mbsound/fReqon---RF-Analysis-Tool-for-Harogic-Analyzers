"""
fcc_database.py - US broadcast TV station lookup.

Stations near a location are fetched live from the FCC's TV Query service
(pipe-delimited text output; typically <1 s and a few tens of KB), instead of
downloading the 1.6 GB LMS database dump. Every live result is cached in the
per-user SQLite database, so a venue looked up once keeps working offline. If
the FCC can't be reached and no cached lookup covers the location, the
bundled station table (built from an LMS dump) is used.
"""

import math
import os
import sqlite3
import threading
import time

import pgeocode
import requests

try:
    from .app_paths import user_database
except ImportError:
    from app_paths import user_database

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

TVQ_URL = "https://transition.fcc.gov/fcc-bin/tvq"
TVQ_TIMEOUT = (5, 20)  # connect, read (seconds)

# Source of the most recent lookup (see FCCDatabaseManager.last_lookup)
SOURCE_LIVE, SOURCE_CACHE, SOURCE_BUNDLED = "live", "cache", "bundled"


def _haversine_km(lat1, lon1, lat2, lon2):
    dlat = math.radians(lat2 - lat1)
    dlon = math.radians(lon2 - lon1)
    a = (math.sin(dlat / 2) ** 2 +
         math.cos(math.radians(lat1)) * math.cos(math.radians(lat2)) * math.sin(dlon / 2) ** 2)
    return 6371.0 * 2 * math.atan2(math.sqrt(a), math.sqrt(1 - a))


def _dms(value):
    """Decimal degrees -> (degrees, minutes, seconds) of the magnitude."""
    value = abs(value)
    d = int(value)
    m = int((value - d) * 60)
    s = round(((value - d) * 60 - m) * 60, 1)
    return d, m, s


def parse_tvq_text(text):
    """
    Parse TV Query's pipe-delimited text output (list=4). Returns dicts with
    call_sign, service, channel, status, city, state, erp (kW), facility_id,
    lat, lon, licensee and distance_km (from the query point).
    """
    stations = []
    for line in text.splitlines():
        f = [x.strip() for x in line.strip().strip("|").split("|")]
        if len(f) < 28:
            continue
        try:
            channel = int(f[3])
            lat = int(f[19]) + int(f[20]) / 60.0 + float(f[21]) / 3600.0
            lon = int(f[23]) + int(f[24]) / 60.0 + float(f[25]) / 3600.0
        except ValueError:
            continue
        if f[18] == "S":
            lat = -lat
        if f[22] == "W":
            lon = -lon
        try:
            erp = float(f[13].split()[0])
        except (ValueError, IndexError):
            erp = None
        try:
            dist = float(f[27].split()[0])
        except (ValueError, IndexError):
            dist = None
        stations.append({
            "call_sign": f[0],
            "service": f[2],
            "channel": channel,
            "status": f[8],
            "city": f[9].title(),
            "state": f[10],
            "erp": erp,
            "facility_id": f[17],
            "lat": lat,
            "lon": lon,
            "licensee": f[26],
            "distance_km": dist,
        })
    return stations


class FCCDatabaseManager:
    def __init__(self, db_path="fcc_tv.db"):
        # Relative names refer to the per-user copy (writable, independent of the
        # working directory); absolute paths are used as given.
        if not os.path.isabs(db_path):
            db_path = user_database(db_path)
        self.db_path = db_path
        # {"source": live|cache|bundled, "fetched_at": epoch or None, "error": str or None}
        self.last_lookup = {"source": None, "fetched_at": None, "error": None}
        self._init_db()

    def _init_db(self):
        # One connection, shared by the GUI thread and lookup worker threads;
        # every use goes through _db_lock.
        self._db_lock = threading.RLock()
        self.conn = sqlite3.connect(self.db_path, check_same_thread=False)
        with self._db_lock, self.conn:
            self.conn.execute("CREATE TABLE IF NOT EXISTS metadata (key TEXT PRIMARY KEY, value TEXT)")
            # Bundled fallback, built from an LMS dump
            self.conn.execute("""
                CREATE TABLE IF NOT EXISTS stations (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    application_id TEXT, service TEXT, lms_application_id TEXT,
                    call_sign TEXT, lat REAL, lon REAL, channel INTEGER, erp REAL,
                    is_public_safety BOOLEAN DEFAULT 0
                )""")
            # Cache of live TV Query lookups
            self.conn.execute("""
                CREATE TABLE IF NOT EXISTS live_queries (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    lat REAL, lon REAL, radius_km REAL, fetched_at REAL
                )""")
            self.conn.execute("""
                CREATE TABLE IF NOT EXISTS live_stations (
                    query_id INTEGER REFERENCES live_queries(id) ON DELETE CASCADE,
                    call_sign TEXT, service TEXT, channel INTEGER, status TEXT,
                    city TEXT, state TEXT, erp REAL, facility_id TEXT,
                    lat REAL, lon REAL, licensee TEXT
                )""")
            self.conn.execute("CREATE INDEX IF NOT EXISTS live_stations_query ON live_stations(query_id)")

    def _query(self, sql, params=()):
        with self._db_lock:
            return self.conn.execute(sql, params).fetchall()

    def get_last_update_time(self):
        """Time of the most recent successful live lookup (0 if none)."""
        rows = self._query("SELECT MAX(fetched_at) FROM live_queries")
        return float(rows[0][0]) if rows and rows[0][0] else 0.0

    def has_data(self):
        return (self._query("SELECT COUNT(*) FROM live_stations")[0][0] > 0 or
                self._query("SELECT COUNT(*) FROM stations")[0][0] > 0)

    # --- Live lookup -----------------------------------------------------

    def fetch_live(self, lat, lon, radius_km, first_channel=2, last_channel=36):
        """Query the FCC TV Query service. Raises on network or HTTP errors."""
        dlat, mlat, slat = _dms(lat)
        dlon, mlon, slon = _dms(lon)
        params = {
            "call": "", "chan": first_channel, "cha2": last_channel, "serv": "", "type": 0,
            "status": 3,  # licensed facilities
            "facid": "", "list": 4,  # pipe-delimited text
            "dist": round(radius_km, 1),
            "dlat2": dlat, "mlat2": mlat, "slat2": slat, "NS": "N" if lat >= 0 else "S",
            "dlon2": dlon, "mlon2": mlon, "slon2": slon, "EW": "W" if lon < 0 else "E",
            "size": 9,
        }
        r = requests.get(TVQ_URL, params=params, timeout=TVQ_TIMEOUT,
                         headers={"User-Agent": "Freqon (RF coordination tool)"})
        r.raise_for_status()
        return parse_tvq_text(r.text)

    def _store_live(self, lat, lon, radius_km, stations):
        with self._db_lock, self.conn:
            cur = self.conn.execute(
                "INSERT INTO live_queries (lat, lon, radius_km, fetched_at) VALUES (?, ?, ?, ?)",
                (lat, lon, radius_km, time.time()))
            qid = cur.lastrowid
            self.conn.executemany(
                "INSERT INTO live_stations (query_id, call_sign, service, channel, status, city, "
                "state, erp, facility_id, lat, lon, licensee) VALUES (?,?,?,?,?,?,?,?,?,?,?,?)",
                [(qid, s["call_sign"], s["service"], s["channel"], s["status"], s["city"],
                  s["state"], s["erp"], s["facility_id"], s["lat"], s["lon"], s["licensee"])
                 for s in stations])
            # Keep only the newest lookup for (roughly) the same place and radius
            self.conn.execute("PRAGMA foreign_keys = ON")
            old = self.conn.execute(
                "SELECT id FROM live_queries WHERE id != ? AND ABS(lat - ?) < 0.01 AND "
                "ABS(lon - ?) < 0.01 AND ABS(radius_km - ?) < 1", (qid, lat, lon, radius_km)).fetchall()
            for (oid,) in old:
                self.conn.execute("DELETE FROM live_stations WHERE query_id = ?", (oid,))
                self.conn.execute("DELETE FROM live_queries WHERE id = ?", (oid,))

    def _from_cache(self, lat, lon, radius_km):
        """Stations from the newest cached lookup whose area covers this one."""
        best = None
        for qid, qlat, qlon, qrad, fetched in self._query(
                "SELECT id, lat, lon, radius_km, fetched_at FROM live_queries ORDER BY fetched_at DESC"):
            if _haversine_km(lat, lon, qlat, qlon) + radius_km <= qrad + 1.0:
                best = (qid, fetched)
                break
        if best is None:
            return None, None
        rows = self._query(
            "SELECT call_sign, service, channel, status, city, state, erp, facility_id, lat, lon, "
            "licensee FROM live_stations WHERE query_id = ?", (best[0],))
        keys = ("call_sign", "service", "channel", "status", "city", "state", "erp",
                "facility_id", "lat", "lon", "licensee")
        stations = []
        for row in rows:
            s = dict(zip(keys, row))
            s["distance_km"] = round(_haversine_km(lat, lon, s["lat"], s["lon"]), 2)
            if s["distance_km"] <= radius_km:
                stations.append(s)
        return stations, best[1]

    def _from_bundled(self, lat, lon, radius_km):
        lat_delta = radius_km / 111.0
        lon_delta = radius_km / (111.0 * max(0.1, math.cos(math.radians(lat))))
        rows = self._query(
            "SELECT call_sign, lat, lon, channel, erp FROM stations "
            "WHERE lat BETWEEN ? AND ? AND lon BETWEEN ? AND ?",
            (lat - lat_delta, lat + lat_delta, lon - lon_delta, lon + lon_delta))
        stations = []
        for call_sign, slat, slon, channel, erp in rows:
            if slat is None or slon is None:
                continue
            dist = _haversine_km(lat, lon, slat, slon)
            if dist <= radius_km:
                stations.append({"call_sign": call_sign, "channel": channel, "erp": erp,
                                 "lat": slat, "lon": slon, "distance_km": round(dist, 2)})
        return stations

    def lookup(self, lat, lon, radius_km, allow_network=True):
        """
        Stations within radius_km of (lat, lon): live when possible, otherwise
        from a cached lookup covering the area, otherwise the bundled table.
        Sets self.last_lookup to describe where the data came from.
        """
        error = None
        if allow_network:
            try:
                stations = self.fetch_live(lat, lon, radius_km)
                self._store_live(lat, lon, radius_km, stations)
                self.last_lookup = {"source": SOURCE_LIVE, "fetched_at": time.time(), "error": None}
                return self._finish(stations, lat, lon, radius_km)
            except Exception as e:  # network down, FCC unavailable, ...
                error = str(e)
        stations, fetched = self._from_cache(lat, lon, radius_km)
        if stations is not None:
            self.last_lookup = {"source": SOURCE_CACHE, "fetched_at": fetched, "error": error}
            return self._finish(stations, lat, lon, radius_km)
        self.last_lookup = {"source": SOURCE_BUNDLED, "fetched_at": None, "error": error}
        return self._finish(self._from_bundled(lat, lon, radius_km), lat, lon, radius_km)

    def _finish(self, stations, lat, lon, radius_km):
        # One row per facility and channel (a facility can have several records,
        # e.g. distributed transmitters); keep the nearest.
        best = {}
        for s in stations:
            s["is_public_safety"] = False
            key = (s.get("facility_id") or s.get("call_sign"), s.get("channel"))
            if key not in best or (s.get("distance_km") or 0) < (best[key].get("distance_km") or 0):
                best[key] = s
        result = list(best.values())
        # T-Band public safety (LMR) is protected within ~80 km of these cities
        for city in T_BAND_CITIES:
            dist = _haversine_km(lat, lon, city["lat"], city["lon"])
            if dist <= radius_km:
                for ch in city["channels"]:
                    result.append({"call_sign": f'LMR {city["name"]}', "distance_km": round(dist, 1),
                                   "channel": ch, "erp": "N/A", "is_public_safety": True})
        result.sort(key=lambda s: s.get("distance_km") or 0)
        return result

    # --- ZIP code entry points (used by the UI) --------------------------

    @staticmethod
    def geocode_zip(zip_code):
        res = pgeocode.Nominatim("us").query_postal_code(str(zip_code).strip()[:5])
        if math.isnan(res.latitude) or math.isnan(res.longitude):
            return None
        return float(res.latitude), float(res.longitude)

    def query_by_zip(self, zip_code: str, radius_miles: float = 65, allow_network=True):
        """Stations near a US ZIP code, within radius_miles."""
        loc = self.geocode_zip(zip_code)
        if loc is None:
            self.last_lookup = {"source": None, "fetched_at": None, "error": f"Unknown ZIP code {zip_code}"}
            return []
        return self.lookup(loc[0], loc[1], radius_miles * 1.60934, allow_network)

    def get_stations_near_zip(self, zip_code, radius_km=200):
        loc = self.geocode_zip(zip_code)
        return self.lookup(loc[0], loc[1], radius_km) if loc else []

    def get_station_name_for_channel(self, channel: int):
        """Primary call sign for an RF channel, from the most recent lookup area."""
        rows = self._query(
            "SELECT call_sign FROM live_stations WHERE channel = ? AND query_id = "
            "(SELECT id FROM live_queries ORDER BY fetched_at DESC LIMIT 1) ORDER BY erp DESC LIMIT 1",
            (channel,))
        if not rows:
            rows = self._query("SELECT call_sign FROM stations WHERE channel = ? ORDER BY erp DESC LIMIT 1",
                               (channel,))
        return rows[0][0] if rows and rows[0][0] else None
