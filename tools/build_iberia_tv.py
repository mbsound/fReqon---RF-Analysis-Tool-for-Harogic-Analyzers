"""
build_iberia_tv.py - Build the Spanish and Portuguese television data shipped with fReqon.

    python tools/build_iberia_tv.py --spain BOE-A-2019-9513-consolidado.pdf
    python tools/build_iberia_tv.py --portugal mapa-emissores.html

Spain: the Plan Técnico Nacional de la Televisión Digital Terrestre (Real Decreto
391/2019, consolidated text from boe.es). Annex I assigns every municipality (INE
code) to one of 75 geographic areas; annex II gives the channel of each of the
eight national and regional multiplexes in each area. There is no public list of
transmitter sites, so the lookup is by area: the eight channels planned where you are.
    -> RF_Recon_Modern/data/spain_tdt_plan.json

Portugal: the table of DTT (TDT) transmitters with coordinates, channel and radiated
power (source: ANACOM / the network operator, as republished at
electronica-pt.com/mapa-emissores.php; save that page and pass the file).
    -> RF_Recon_Modern/data/portugal_tdt.json

Needs pypdf for --spain.
"""

import html
import json
import os
import re
import sys
import unicodedata

OUT = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "RF_Recon_Modern", "data")
MUXES = ("RGE1", "RGE2", "MPE1", "MPE2", "MPE3", "MPE4", "MPE5", "MAUT")


def norm(name: str) -> str:
    s = unicodedata.normalize("NFKD", name).encode("ascii", "ignore").decode().upper()
    return re.sub(r"[^A-Z0-9]+", " ", s).strip()


def build_spain(pdf_path):
    import pypdf
    text = "\n".join((p.extract_text() or "") for p in pypdf.PdfReader(pdf_path).pages)
    text = re.sub(r"BOLETÍN OFICIAL DEL ESTADO\s*\nLEGISLACIÓN CONSOLIDADA\s*\nPágina \d+\s*\n", "", text)
    i1, i2 = text.index("ANEXO I\nÁreas geográficas"), text.index("ANEXO II\n")
    annex1 = text[i1:i2]
    annex2 = text[i2:text.index("ANEXO III", i2)]
    # Annex II: "<AREA NAME> c c c c c c c c"
    areas = {}
    for m in re.finditer(r"^([A-ZÁÉÍÓÚÑÜ][A-ZÁÉÍÓÚÑÜ \-/]+?)((?: \d{2}){8})\s*$", annex2, re.M):
        areas[norm(m.group(1))] = {"name": m.group(1).title(), "channels": dict(zip(MUXES, map(int, m.group(2).split())))}
    # Annex I: "Área geográfica n.º N\n<Name>\n" then rows of "<INE> <municipality>."
    municipalities = {}
    blocks = re.split(r"Área geográfica n\.º (\d+)\s*\n([^\n]+)\n", annex1)
    for k in range(1, len(blocks), 3):
        area_name, body = blocks[k + 1].strip().rstrip("."), blocks[k + 2]
        key = norm(area_name)
        if key not in areas:
            raise SystemExit(f"area {area_name!r} of annex I has no channels in annex II")
        for ine, muni in re.findall(r"(\d{5}) ([^\d\n]+?)\.(?= \d{5} |\s*$|\s*\n)", body, re.M):
            municipalities[ine] = [muni.strip(), key]
    data = {"source": "Real Decreto 391/2019, Plan Técnico Nacional de la Televisión Digital Terrestre (BOE-A-2019-9513, consolidated)",
            "multiplexes": list(MUXES), "areas": areas, "municipalities": municipalities}
    path = os.path.join(OUT, "spain_tdt_plan.json")
    with open(path, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, separators=(",", ":"))
    print(f"{path}: {len(areas)} areas, {len(municipalities)} municipalities, {os.path.getsize(path) // 1024} kB")


# The published page has lost its accented letters (each is a replacement character).
# The place names are put back from this list; R stands for the lost character.
_PT_REPAIRS = {
    "Rguia": "Águia", "AlcobaRaa": "Alcobaça", "AlcRcer": "Alcácer", "AlmodRvar": "Almodôvar", "chRo": "Chão",
    "AlvaiRzere": "Alvaiázere", "AlvRco": "Alvôco", "VRrzeas": "Várzeas", "BaiRo": "Baião", "SRo": "São",
    "BraganRa": "Bragança", "BufRo": "Bufão", "SRr": "Sôr", "CabaRos": "Cabaços", "CacRm": "Cacém", "PRra": "Pêra",
    "ObservatRrio": "Observatório", "CouRo": "Couço", "CovilhR": "Covilhã", "EsperanRa": "Esperança",
    "FRtima": "Fátima", "GaviRo": "Gavião", "GerRs": "Gerês", "GraRa": "Graça", "GrRndola": "Grândola",
    "GuimarRes": "Guimarães", "LeRa": "Leça", "LoulR": "Loulé", "LousR": "Lousã", "MarvRo": "Marvão",
    "MaRRo": "Mação", "MortRgua": "Mortágua", "MRrtola": "Mértola", "NazarR": "Nazaré", "OurRm": "Ourém",
    "PirocRo": "Pirocão", "Espada R Cinta": "Espada à Cinta", "PiRdRo": "Piódão", "FernRo": "Fernão", "MRs": "Mós",
    "AdriRo": "Adrião", "PRvoa": "Póvoa", "ARores": "Açores", "PenaguiRo": "Penaguião", "SantarRm": "Santarém",
    "SapiRos": "Sapiãos", "AlvRo": "Alvão", "JoRo": "João", "SRtio": "Sítio", "SRtRo": "Sátão", "TrancRo": "Trancão",
    "ValenRa": "Valença", "Rncora": "Âncora", "ViRosa": "Viçosa", "Rbidos": "Óbidos", "Rgueda": "Águeda", "Rvora": "Évora",
}


def _repair_pt(name: str) -> str:
    for damaged, fixed in sorted(_PT_REPAIRS.items(), key=lambda kv: -len(kv[0])):
        name = name.replace(damaged.replace("R", "\ufffd"), fixed)
    return name


def build_portugal(html_path):
    raw = open(html_path, "rb").read()
    try:
        page = raw.decode("utf-8")
    except UnicodeDecodeError:
        page = raw.decode("latin-1")
    table = page[page.index("id='tabela'"):]
    table = table[:table.index("</table>")]
    sites = []
    for row in re.findall(r"<tr>(.*?)</tr>", table, re.S):
        cells = [html.unescape(re.sub(r"<[^>]+>", "", c)).replace("♦", "").strip() for c in re.findall(r"<td[^>]*>(.*?)</td>", row, re.S)]
        if len(cells) < 6:
            continue
        pos = re.match(r"\(\s*(-?\d+\.\d+)\s*,\s*(-?\d+\.\d+)\s*\)", cells[3])
        power = re.match(r"([\d.,]+)\s*(k?W)", cells[5], re.I)
        if not pos or not cells[4].isdigit():
            continue
        erp_kw = None
        if power:
            watts = float(power.group(1).replace(",", "."))
            erp_kw = watts if power.group(2).lower() == "kw" else watts / 1000.0
        sites.append({"site": _repair_pt(cells[0]), "lat": float(pos.group(1)), "lon": float(pos.group(2)),
                      "channel": int(cells[4]), "erp_kw": erp_kw})
    dated = re.search(r"(\d{1,2}) de (\w+) de (20\d\d)", page)
    data = {"source": "ANACOM / network operator transmitter list, as published at electronica-pt.com/mapa-emissores.php",
            "dated": dated.group(0) if dated else "", "transmitters": sites}
    path = os.path.join(OUT, "portugal_tdt.json")
    with open(path, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, separators=(",", ":"))
    left = sorted({t["site"] for t in sites if "\ufffd" in t["site"]})
    if left:
        print("names still damaged (add them to _PT_REPAIRS):", left)
    print(f"{path}: {len(sites)} transmitters, channels {sorted({s['channel'] for s in sites})}, dated {data['dated']!r}")


if __name__ == "__main__":
    if len(sys.argv) != 3 or sys.argv[1] not in ("--spain", "--portugal"):
        sys.exit(__doc__)
    os.makedirs(OUT, exist_ok=True)
    (build_spain if sys.argv[1] == "--spain" else build_portugal)(sys.argv[2])
