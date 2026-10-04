"""
test_soundbase.py - Soundbase coordination file layouts (no analyzer needed).

    python testing/test_soundbase.py
"""

import gzip
import json
import os
import sys
import tempfile
import time

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), ".."))

from core.soundbase_parser import SoundbaseParser

SITE, ZONE, GROUP_A, GROUP_B = "site1", "zone1", "grpA", "grpB"


def records():
    zone = {"_id": ZONE, "name": "Main Hall", "siteId": SITE}
    groups = [{"_id": GROUP_A, "name": "Vocals", "siteId": SITE, "zoneId": ZONE, "color": "#aea1ff"},
              {"_id": GROUP_B, "name": "IEM", "siteId": SITE, "zoneId": ZONE, "color": "#fcdc00"}]
    model = {"model": "AD4Q-A", "manufacturer": "Shure", "bandwidth": 350000}
    freqs = [{"_id": "f1", "name": "Lead", "freq": 490500000, "siteId": SITE, "zoneId": ZONE, "groupId": GROUP_A, "model": model},
             {"_id": "f2", "name": "BV 1", "freq": 491300000, "siteId": SITE, "zoneId": ZONE, "groupId": GROUP_A, "model": model},
             {"_id": "f3", "name": "", "identifier": "IEM 3", "freq": 560125000, "siteId": SITE, "zoneId": ZONE,
              "groupId": GROUP_B, "model": {}},
             {"_id": "f4", "name": "No group", "freq": 600000000, "siteId": SITE, "zoneId": ZONE, "groupId": None, "model": model}]
    return zone, groups, freqs


def write(data, name, compress=False):
    path = os.path.join(tempfile.mkdtemp(), name)
    with (gzip.open(path, "wt", encoding="utf-8") if compress else open(path, "w", encoding="utf-8")) as f:
        json.dump(data, f)
    return path


def check(parsed, site_name, zone_name):
    assert parsed["total_carriers"] == 4, parsed["total_carriers"]
    site = parsed["sites"][0]
    assert site["name"] == site_name and [z["name"] for z in site["zones"]] == [zone_name], (site["name"], site["zones"])
    groups = {g["name"]: g for g in site["zones"][0]["groups"]}
    assert sorted(groups) == ["IEM", "Unassigned", "Vocals"], sorted(groups)
    assert [c["name"] for c in groups["Vocals"]["carriers"]] == ["Lead", "BV 1"]
    lead = groups["Vocals"]["carriers"][0]
    assert (lead["freq_mhz"], lead["bandwidth_mhz"], lead["color"], lead["model"]) == (490.5, 0.35, "#aea1ff", "AD4Q-A")
    iem = groups["IEM"]["carriers"][0]
    assert iem["name"] == "IEM 3" and iem["bandwidth_mhz"] == 0.2, iem      # no model: the 200 kHz default


def test_project_file():
    """A full project: a stream of {collectionName, value} records, gzip-compressed."""
    zone, groups, freqs = records()
    stream = ([{"collectionName": "coordSite", "value": {"_id": SITE, "name": "Tour 2026"}},
               {"collectionName": "coordZone", "value": zone}]
              + [{"collectionName": "coordGroup", "value": g} for g in groups]
              + [{"collectionName": "coordFreq", "value": f} for f in freqs]
              # a carrier of a zone that was deleted from the project is not shown
              + [{"collectionName": "coordFreq", "value": dict(freqs[0], _id="old", zoneId="deleted-zone")}])
    check(SoundbaseParser.parse_file(write(stream, "tour.sbcoordsite", compress=True)), "Tour 2026", "Main Hall")


def test_zone_export():
    """A zone export: one zone as an object, no site record, the collections as lists."""
    zone, groups, freqs = records()
    export = {"siteId": SITE, "zone": zone, "groups": groups, "freqs": freqs, "broadbandFreqs": [],
              "groupImOverrides": [], "version": 0}
    check(SoundbaseParser.parse_file(write(export, "ZoneExport_Main Hall_10_1_2026.json")), "Main Hall", "Main Hall")
    # Even with no zone or site information at all, the carriers are kept
    bare = {"groups": groups, "freqs": freqs}
    check(SoundbaseParser.parse_file(write(bare, "carriers.json")), "carriers", "General Zone")


if __name__ == "__main__":
    for test in (test_project_file, test_zone_export):
        t0 = time.monotonic()
        test()
        print(f"ok  {test.__name__}  ({time.monotonic() - t0:.1f} s)")
    print("All Soundbase tests passed.")
