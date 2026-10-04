"""
iberia_tv.py - Television transmitter lookup for Spain and Portugal.

Spain publishes no list of transmitter sites. What it does publish is the
national plan (Real Decreto 391/2019): every municipality belongs to one of 75
geographic areas, and each area has one channel for each of the eight national
and regional multiplexes. So the Spanish lookup is by area: a postcode gives
the municipality, the municipality its area, and the area its eight channels.
Those channels are in use throughout the area by definition, so all of them
are returned as "here" (distance 0, power unknown).

Portugal's network is a list of transmitters with coordinates, channel and
radiated power, looked up by distance like the UK's.

Data: data/spain_tdt_plan.json and data/portugal_tdt.json, built by
tools/build_iberia_tv.py from the BOE text and the ANACOM-sourced table.
"""

import json
import math
import re
import unicodedata

from .app_paths import APP_DIR

DATA_DIR = APP_DIR / "data"


def _norm(name: str) -> str:
    s = unicodedata.normalize("NFKD", str(name)).encode("ascii", "ignore").decode().upper()
    return re.sub(r"[^A-Z0-9]+", " ", s).strip()


def _name_keys(name: str) -> set:
    """Ways a municipality is written: 'Gineta (La)', 'La Gineta', 'Palma De Mallorca' / 'Palma', 'Alacant/Alicante'."""
    keys = set()
    for part in re.split(r"[/]", str(name)):
        m = re.match(r"^(.*?)\s*\((.+?)\)\s*$", part.strip())
        if m:                                       # "Gineta (La)" -> "La Gineta"
            part = f"{m.group(2)} {m.group(1)}"
        m = re.match(r"^(.*?),\s*(\w+)$", part.strip())
        if m:                                       # "Bóveda de Toro, La"
            part = f"{m.group(2)} {m.group(1)}"
        k = _norm(part)
        if k:
            keys.add(k)
            keys.add(re.sub(r"^(EL|LA|LOS|LAS|L|O|A|OS|AS|ES|SA|S) ", "", k))
    return keys


def _haversine_km(lat1, lon1, lat2, lon2):
    p1, p2 = math.radians(lat1), math.radians(lat2)
    a = math.sin((p2 - p1) / 2) ** 2 + math.cos(p1) * math.cos(p2) * math.sin(math.radians(lon2 - lon1) / 2) ** 2
    return 6371.0 * 2 * math.asin(math.sqrt(a))


class SpainTDTPlan:
    def __init__(self, path=None):
        self.path = path or DATA_DIR / "spain_tdt_plan.json"
        self._data = None

    @property
    def data(self):
        if self._data is None:
            try:
                with open(self.path, encoding="utf-8") as f:
                    self._data = json.load(f)
            except (OSError, ValueError):
                self._data = {"areas": {}, "municipalities": {}, "multiplexes": [], "source": ""}
            by_province = {}
            for ine, (name, area) in self._data["municipalities"].items():
                by_province.setdefault(ine[:2], []).append((name, area))
            self._by_province = by_province
        return self._data

    def has_data(self) -> bool:
        return bool(self.data["areas"])

    @staticmethod
    def _place_names(postcode: str) -> list:
        """Municipality names the postcode geocoder gives for a postcode ([] if it cannot be asked)."""
        try:
            import pgeocode
            res = pgeocode.Nominatim("ES").query_postal_code(postcode)
            return [n.strip() for n in str(res.place_name).split(",")] if isinstance(res.place_name, str) else []
        except Exception:
            return []

    def areas_for_postcode(self, postcode: str):
        """
        (area keys, exact). A Spanish postcode starts with its province's number, which is
        also how municipality codes start; within the province the municipality name picks
        the area. Without a name match, every area with a municipality in the province is
        returned (exact False).
        """
        code = re.sub(r"\D", "", str(postcode))
        if len(code) != 5 or not self.has_data():
            return [], False
        in_province = self._by_province.get(code[:2], [])
        if not in_province:
            return [], False
        areas = sorted({a for _n, a in in_province})
        if len(areas) == 1:
            return areas, True
        wanted = set()
        for place in self._place_names(code):
            wanted |= _name_keys(place)
        hits = {a for n, a in in_province if _name_keys(n) & wanted}
        if len(hits) == 1:
            return sorted(hits), True
        return (sorted(hits) if hits else areas), False

    def query_by_postcode(self, postcode: str):
        """
        (stations, info): one station per multiplex channel of the postcode's area, in the
        shape the other lookups return; info = {"areas": [names], "exact": bool}.
        """
        keys, exact = self.areas_for_postcode(postcode)
        stations = []
        seen = set()
        for key in keys:
            area = self.data["areas"][key]
            for mux, ch in area["channels"].items():
                if (ch, mux) in seen and not exact:
                    continue
                seen.add((ch, mux))
                stations.append({"site_name": area["name"], "call_sign": f"{mux} ({area['name']})",
                                 "distance_km": 0.0, "channel": int(ch), "erp": None, "is_public_safety": False})
        stations.sort(key=lambda s: s["channel"])
        return stations, {"areas": [self.data["areas"][k]["name"] for k in keys], "exact": exact}


class PortugalTDT:
    def __init__(self, path=None):
        self.path = path or DATA_DIR / "portugal_tdt.json"
        self._data = None

    @property
    def data(self):
        if self._data is None:
            try:
                with open(self.path, encoding="utf-8") as f:
                    self._data = json.load(f)
            except (OSError, ValueError):
                self._data = {"transmitters": [], "source": "", "dated": ""}
        return self._data

    def has_data(self) -> bool:
        return bool(self.data["transmitters"])

    @staticmethod
    def _geocode(postcode: str):
        """(lat, lon) of a Portuguese postcode ('1000-001', or its first four digits), or None."""
        digits = re.sub(r"\D", "", str(postcode))
        if len(digits) < 4:
            return None
        import pgeocode
        nomi = pgeocode.Nominatim("PT")
        if len(digits) >= 7:
            res = nomi.query_postal_code(f"{digits[:4]}-{digits[4:7]}")
            if not (math.isnan(res.latitude) or math.isnan(res.longitude)):
                return float(res.latitude), float(res.longitude)
        # The geocoder only knows full codes: take the middle of those sharing the first four digits
        frame = getattr(nomi, "_data_frame", None)
        if frame is None:
            frame = getattr(nomi, "_data", None)
        if frame is not None:
            same = frame[frame["postal_code"].astype(str).str.startswith(digits[:4])]
            same = same.dropna(subset=["latitude", "longitude"])
            if len(same):
                return float(same["latitude"].median()), float(same["longitude"].median())
        return None

    def query_by_postcode(self, postcode: str, radius_km: float = 80.0):
        loc = self._geocode(postcode)
        if loc is None:
            return []
        return self.query_near(loc[0], loc[1], radius_km)

    def query_near(self, lat, lon, radius_km: float = 80.0):
        stations = []
        for t in self.data["transmitters"]:
            d = _haversine_km(lat, lon, t["lat"], t["lon"])
            if d <= radius_km:
                stations.append({"site_name": t["site"], "call_sign": t["site"], "distance_km": round(d, 1),
                                 "channel": int(t["channel"]), "erp": t.get("erp_kw"), "is_public_safety": False})
        stations.sort(key=lambda s: s["distance_km"])
        return stations
