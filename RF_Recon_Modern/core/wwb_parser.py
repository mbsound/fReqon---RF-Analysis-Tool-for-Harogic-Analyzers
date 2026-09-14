"""
wwb_parser.py - Shure Wireless Workbench (WWB) Coordination CSV Parser.
Parses Wireless Workbench export CSV files, extracting hierarchical zones,
carrier frequencies, models, bands, and active TV / Public Safety exclusions.
"""

import os
import re
import csv
from typing import Dict, List, Any, Optional

# Default ordered palette: Orange, Yellow, Blue, Violet, Purple
# Deliberately omitting Red and Green as requested
WWB_DEFAULT_PALETTE = [
    "#f97316",  # Orange
    "#eab308",  # Yellow
    "#3b82f6",  # Blue
    "#8b5cf6",  # Violet
    "#a855f7",  # Purple
]

class WWBParser:
    """
    Parser for Shure Wireless Workbench (.csv) frequency coordination files.
    """

    @classmethod
    def parse_file(cls, filepath: str) -> Dict[str, Any]:
        if not os.path.exists(filepath):
            raise FileNotFoundError(f"File not found: {filepath}")

        with open(filepath, "r", encoding="utf-8", errors="replace") as f:
            lines = f.readlines()

        site_name = os.path.splitext(os.path.basename(filepath))[0]
        # Look for show/site title in first 20 lines
        for l in lines[:20]:
            s = l.strip().replace(",", "")
            if s and not any(k in s.lower() for k in ("point of contact", "venue information", "address", "phone", "e-mail", "notes", "coordination report")):
                site_name = s
                break

        zones = []
        current_zone = None
        in_primary = False
        in_backup = False
        in_exclusions = False
        active_tv = []
        active_ps = []

        header_cols = {}
        current_group = None
        color_idx = 0

        for raw_line in lines:
            line = raw_line.strip()
            if not line:
                continue

            # Detect RF Zone
            if line.startswith("RF zone:"):
                z_name = line.replace("RF zone:", "").strip().strip(",")
                current_color = WWB_DEFAULT_PALETTE[color_idx % len(WWB_DEFAULT_PALETTE)]
                color_idx += 1
                current_zone = {
                    "id": f"zone_{len(zones)}",
                    "name": z_name or f"Zone {len(zones) + 1}",
                    "color": current_color,
                    "groups": []
                }
                zones.append(current_zone)
                current_group = None
                in_primary = False
                in_backup = False
                continue

            # Detect Primary / Backup section
            if "Primary frequencies" in line:
                in_primary = True
                in_backup = False
                header_cols = {}
                current_group = None
                continue

            if "Backup frequencies" in line:
                in_backup = True
                in_primary = False
                header_cols = {}
                current_group = None
                continue

            # Detect Exclusions section
            if any(k in line for k in ("Frequency coordination parameters", "Exclusions", "Active TV channels")):
                in_primary = False
                in_backup = False
                in_exclusions = True

            if in_exclusions:
                if line.startswith("Digital,"):
                    parts = [p.strip() for p in line.split(",") if p.strip()]
                    for p in parts[1:]:
                        if p.isdigit():
                            active_tv.append(int(p))
                elif line.startswith("Public Safety,"):
                    parts = [p.strip() for p in line.split(",") if p.strip()]
                    for p in parts[1:]:
                        if p.isdigit():
                            active_ps.append(int(p))
                continue

            # Parse Channels within Primary or Backup
            if (in_primary or in_backup) and current_zone is not None:
                # Header row detection
                if "Type" in line and "Frequency" in line:
                    parts = [p.strip() for p in raw_line.split(",")]
                    header_cols = {col.lower(): idx for idx, col in enumerate(parts) if col}
                    continue

                parts = [p.strip() for p in raw_line.split(",")]
                first_col = parts[0] if len(parts) > 0 else ""

                # Look for frequency value
                freq_col_idx = header_cols.get("frequency", 4 if len(parts) > 4 else -1)
                freq_str = parts[freq_col_idx] if 0 <= freq_col_idx < len(parts) else ""

                freq_match = re.search(r"([\d\.]+)\s*(?:mhz)?", freq_str, re.IGNORECASE)
                if not freq_match and len(parts) > 1:
                    for c_idx, col_val in enumerate(parts):
                        m = re.search(r"([\d\.]+)\s*mhz", col_val, re.IGNORECASE)
                        if m:
                            freq_match = m
                            freq_col_idx = c_idx
                            break

                if freq_match:
                    freq_mhz = float(freq_match.group(1))
                    freq_hz = freq_mhz * 1e6

                    if current_group is None:
                        current_group = {
                            "id": f"group_{current_zone['id']}_0",
                            "name": "Primary" if in_primary else "Backup",
                            "color": current_zone["color"],
                            "carriers": []
                        }
                        current_zone["groups"].append(current_group)

                    type_col_idx = header_cols.get("type", 0)
                    band_col_idx = header_cols.get("band", 1)
                    name_col_idx = header_cols.get("channel name", 2)
                    gc_col_idx = header_cols.get("group & channel", 3)

                    m_type = parts[type_col_idx] if 0 <= type_col_idx < len(parts) else ""
                    m_band = parts[band_col_idx] if 0 <= band_col_idx < len(parts) else ""
                    ch_name = parts[name_col_idx] if 0 <= name_col_idx < len(parts) else ""
                    gc_str = parts[gc_col_idx] if 0 <= gc_col_idx < len(parts) else ""

                    if not ch_name:
                        if m_type:
                            ch_name = f"{m_type} {m_band}".strip()
                        else:
                            ch_name = f"Ch {freq_mhz:.3f}"

                    bw_hz = 200000
                    if any(k in m_type.lower() for k in ("hd", "high density")):
                        bw_hz = 150000
                    bw_mhz = bw_hz / 1e6
                    f_start = freq_mhz - (bw_mhz / 2.0)
                    f_stop = freq_mhz + (bw_mhz / 2.0)

                    carrier_dict = {
                        "id": f"wwb_{len(current_zone['groups'])}_{len(current_group['carriers'])}_{freq_mhz:.3f}",
                        "name": ch_name,
                        "identifier": gc_str,
                        "freq_hz": freq_hz,
                        "freq_mhz": freq_mhz,
                        "bandwidth_hz": bw_hz,
                        "bandwidth_mhz": bw_mhz,
                        "color": current_group["color"],
                        "model": m_type,
                        "band": m_band,
                        "manufacturer": "Shure" if any(k in m_type for k in ("AD", "PSM", "ULX", "QLX", "Axient")) else "",
                        "f_start_mhz": f_start,
                        "f_stop_mhz": f_stop,
                        "group_id": current_group["id"],
                        "group_name": current_group["name"],
                        "is_backup": in_backup
                    }
                    current_group["carriers"].append(carrier_dict)
                else:
                    clean_name = re.sub(r"\s*\(\d+\)\s*", "", first_col).strip()
                    if clean_name and clean_name != "Type":
                        current_group = {
                            "id": f"group_{current_zone['id']}_{len(current_zone['groups'])}",
                            "name": clean_name,
                            "color": current_zone["color"],
                            "carriers": []
                        }
                        current_zone["groups"].append(current_group)

        # Fallback if no zones were defined
        if not zones:
            raise ValueError("No valid RF zones or frequency tables found in Wireless Workbench file.")

        all_carriers = [c for z in zones for g in z["groups"] for c in g["carriers"]]

        return {
            "sites": [{
                "id": "wwb_site_1",
                "name": site_name,
                "color": WWB_DEFAULT_PALETTE[0],
                "zones": zones
            }],
            "total_carriers": len(all_carriers),
            "all_carriers": all_carriers,
            "active_tv_channels": sorted(list(set(active_tv))),
            "active_public_safety_channels": sorted(list(set(active_ps)))
        }
