"""
soundbase_parser.py - Soundbase Coordination File Parser.
Parses .sbcoordsite (gzip compressed) and .json Soundbase export files,
extracting hierarchical sites, zones, groups, and carriers with colors and bandwidths.
"""

import gzip
import json
import os
from typing import Dict, List, Any, Optional

class SoundbaseParser:
    """
    Parser for Soundbase frequency coordination files.
    """

    @staticmethod
    def load_raw_data(filepath: str) -> Any:
        """
        Loads raw data from filepath, handling gzip compression or plain JSON.
        """
        if not os.path.exists(filepath):
            raise FileNotFoundError(f"File not found: {filepath}")

        # Try gzip first
        try:
            with gzip.open(filepath, 'rt', encoding='utf-8') as f:
                return json.load(f)
        except (gzip.BadGzipFile, OSError):
            # Fall back to plain JSON
            with open(filepath, 'r', encoding='utf-8') as f:
                return json.load(f)

    @classmethod
    def parse_file(cls, filepath: str) -> Dict[str, Any]:
        raw_data = cls.load_raw_data(filepath)

        sites_raw = {}
        zones_raw = {}
        groups_raw = {}
        freqs_raw = []

        # Handle collection stream (standard Soundbase export)
        if isinstance(raw_data, list):
            for item in raw_data:
                if not isinstance(item, dict):
                    continue
                cname = item.get('collectionName')
                val = item.get('value', {})
                if not isinstance(val, dict):
                    continue

                if cname == 'coordSite':
                    s_id = val.get('_id', f"site_{len(sites_raw)}")
                    sites_raw[s_id] = val
                elif cname == 'coordZone':
                    z_id = val.get('_id', f"zone_{len(zones_raw)}")
                    zones_raw[z_id] = val
                elif cname == 'coordGroup':
                    g_id = val.get('_id', f"group_{len(groups_raw)}")
                    groups_raw[g_id] = val
                elif cname == 'coordFreq':
                    freqs_raw.append(val)

        # Handle dictionary structure if exported differently
        elif isinstance(raw_data, dict):
            for k, val_list in raw_data.items():
                if isinstance(val_list, list):
                    for v in val_list:
                        if not isinstance(v, dict):
                            continue
                        if 'site' in k.lower():
                            s_id = v.get('_id', f"site_{len(sites_raw)}")
                            sites_raw[s_id] = v
                        elif 'zone' in k.lower():
                            z_id = v.get('_id', f"zone_{len(zones_raw)}")
                            zones_raw[z_id] = v
                        elif 'group' in k.lower():
                            g_id = v.get('_id', f"group_{len(groups_raw)}")
                            groups_raw[g_id] = v
                        elif 'freq' in k.lower() or 'channel' in k.lower():
                            freqs_raw.append(v)

        # If no site was explicitly defined, provide a default root
        if not sites_raw:
            default_site_id = "default_site"
            site_name = os.path.splitext(os.path.basename(filepath))[0]
            sites_raw[default_site_id] = {"_id": default_site_id, "name": site_name, "color": "#505C62"}

        # Build Sites hierarchy
        sites = {}
        for s_id, s_val in sites_raw.items():
            sites[s_id] = {
                "id": s_id,
                "name": s_val.get("name") or "Unnamed Site",
                "color": s_val.get("color") or "#505C62",
                "zones": {}
            }

        first_site_id = next(iter(sites.keys()))

        # Build Zones hierarchy
        for z_id, z_val in zones_raw.items():
            s_id = z_val.get("siteId")
            if s_id not in sites:
                s_id = first_site_id
            sites[s_id]["zones"][z_id] = {
                "id": z_id,
                "siteId": s_id,
                "name": z_val.get("name") or "Unnamed Zone",
                "color": z_val.get("color") or sites[s_id]["color"],
                "groups": {}
            }

        # Build Groups hierarchy
        for g_id, g_val in groups_raw.items():
            s_id = g_val.get("siteId")
            z_id = g_val.get("zoneId")

            if s_id not in sites:
                s_id = first_site_id

            if z_id not in sites[s_id]["zones"]:
                found_z = False
                for other_s in sites.values():
                    if z_id in other_s["zones"]:
                        s_id = other_s["id"]
                        found_z = True
                        break
                if not found_z:
                    z_id = f"zone_auto_{s_id}"
                    if z_id not in sites[s_id]["zones"]:
                        sites[s_id]["zones"][z_id] = {
                            "id": z_id,
                            "siteId": s_id,
                            "name": "General Zone",
                            "color": sites[s_id]["color"],
                            "groups": {}
                        }

            group_color = g_val.get("color") or sites[s_id]["zones"][z_id]["color"]
            if not group_color or group_color == "#505C62":
                group_color = "#38bdf8"

            sites[s_id]["zones"][z_id]["groups"][g_id] = {
                "id": g_id,
                "siteId": s_id,
                "zoneId": z_id,
                "name": g_val.get("name") or "Unnamed Group",
                "color": group_color,
                "carriers": []
            }

        # Map Carriers to Groups
        all_carriers = []
        for f_idx, f_val in enumerate(freqs_raw):
            freq_hz = f_val.get("freq")
            if not freq_hz or freq_hz <= 0:
                continue

            freq_mhz = freq_hz / 1e6

            # Bandwidth resolution
            model_info = f_val.get("model") or {}
            bw_hz = model_info.get("bandwidth")
            if not bw_hz or bw_hz <= 0:
                bw_hz = 200000  # Standard 200 kHz fallback
            bw_mhz = bw_hz / 1e6

            f_start_mhz = freq_mhz - (bw_mhz / 2.0)
            f_stop_mhz = freq_mhz + (bw_mhz / 2.0)

            model_name = model_info.get("model", "")
            mfg_name = model_info.get("manufacturer", "")
            raw_name = str(f_val.get("name") or "").strip()
            raw_ident = str(f_val.get("identifier") or "").strip()
            if raw_name:
                name = raw_name
            elif raw_ident and raw_ident not in ("RF 000", ""):
                name = raw_ident
            elif model_name:
                name = f"{model_name} ({freq_mhz:.3f})"
            elif raw_ident:
                name = f"{raw_ident} ({freq_mhz:.3f})"
            else:
                name = f"Ch {freq_mhz:.3f}"
            f_id = f_val.get("_id") or f"carrier_{f_idx}"

            s_id = f_val.get("siteId")
            z_id = f_val.get("zoneId")
            g_id = f_val.get("groupId")

            # Locate destination zone and group
            target_group = None
            target_zone = None

            # First, check direct site + zone mapping
            if s_id in sites and z_id in sites[s_id]["zones"]:
                target_zone = sites[s_id]["zones"][z_id]
                if g_id in target_zone["groups"]:
                    target_group = target_zone["groups"][g_id]
            else:
                # Search zone by z_id across all sites
                for s in sites.values():
                    if z_id in s["zones"]:
                        target_zone = s["zones"][z_id]
                        if g_id in target_zone["groups"]:
                            target_group = target_zone["groups"][g_id]
                        break

            # If the carrier points to a non-existent / deleted zone not present in coordZone, skip it
            if target_zone is None:
                continue

            # If the zone is valid but the group is missing or unassigned, place under an Unassigned group in that specific zone
            if target_group is None:
                if "unassigned" not in target_zone["groups"]:
                    target_zone["groups"]["unassigned"] = {
                        "id": "unassigned",
                        "siteId": target_zone["siteId"],
                        "zoneId": target_zone["id"],
                        "name": "Unassigned",
                        "color": "#94a3b8",
                        "carriers": []
                    }
                target_group = target_zone["groups"]["unassigned"]

            carrier_color = f_val.get("color") or target_group["color"]

            carrier_dict = {
                "id": f_id,
                "name": name,
                "identifier": f_val.get("identifier", ""),
                "freq_hz": freq_hz,
                "freq_mhz": freq_mhz,
                "bandwidth_hz": bw_hz,
                "bandwidth_mhz": bw_mhz,
                "color": carrier_color,
                "model": model_name,
                "manufacturer": mfg_name,
                "f_start_mhz": f_start_mhz,
                "f_stop_mhz": f_stop_mhz,
                "group_id": target_group["id"],
                "group_name": target_group["name"]
            }

            target_group["carriers"].append(carrier_dict)
            all_carriers.append(carrier_dict)

        # Convert dictionary hierarchy to list structure
        sites_list = []
        for s in sites.values():
            zones_list = []
            for z in s["zones"].values():
                groups_list = []
                for g in z["groups"].values():
                    if g["carriers"] or len(z["groups"]) == 1:
                        groups_list.append({
                            "id": g["id"],
                            "name": g["name"],
                            "color": g["color"],
                            "carriers": g["carriers"]
                        })
                if groups_list or len(s["zones"]) == 1:
                    zones_list.append({
                        "id": z["id"],
                        "name": z["name"],
                        "color": z["color"],
                        "groups": groups_list
                    })
            sites_list.append({
                "id": s["id"],
                "name": s["name"],
                "color": s["color"],
                "zones": zones_list
            })

        return {
            "sites": sites_list,
            "total_carriers": len(all_carriers),
            "all_carriers": all_carriers
        }
