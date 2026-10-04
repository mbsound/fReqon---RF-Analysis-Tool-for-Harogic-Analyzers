"""
channel_style.py - One colour scheme and labelling for channel masks.

Every view that draws channel masks (spectrum, waterfall, folded waterfall,
RTSA) and the channel bar under them take their colours from here:

    LMR / public safety      red
    Channel 37 (US)          grey   (radio astronomy and medical telemetry: off limits)
    Other TV channels        blue   (with the station's details on the mask)
    Cellular uplink          pink
    Cellular downlink        purple
    Guard bands              slate
"""

import html

import pyqtgraph as pg
from PyQt6.QtCore import Qt
from PyQt6.QtGui import QColor, QFont, QFontMetrics

# kind -> (mask fill, mask edge, edge width, text colour, bar fill, bar edge)
_STYLES = {
    "lmr":      ((239, 68, 68, 40),   (248, 113, 113, 120), 1.0, "#f87171", (239, 68, 68, 220),   (248, 113, 113)),
    "ch37":     ((100, 116, 139, 50), (148, 163, 184, 130), 1.5, "#94a3b8", (71, 85, 105, 200),   (148, 163, 184)),
    "dtv":      ((59, 130, 246, 45),  (96, 165, 250, 140),  1.0, "#60a5fa", (37, 99, 235, 220),   (96, 165, 250)),
    "uplink":   ((236, 72, 153, 35),  (244, 114, 182, 110), 1.0, "#f472b6", (236, 72, 153, 200),  (244, 114, 182)),
    "downlink": ((168, 85, 247, 35),  (192, 132, 252, 110), 1.0, "#c084fc", (168, 85, 247, 200),  (192, 132, 252)),
    "guard":    ((100, 116, 139, 30), (148, 163, 184, 90),  1.0, "#94a3b8", (100, 116, 139, 180), (148, 163, 184)),
}


def channel_kind(ch_type: str, is_public_safety: bool = False) -> str:
    """What a channel is, for colouring: lmr, ch37, dtv, uplink, downlink or guard."""
    if is_public_safety or ch_type == "lmr_smr":
        return "lmr"
    if ch_type in ("ch37", "uplink", "downlink", "guard"):
        return ch_type
    return "dtv"


def mask_brush_pen(kind: str):
    """(brush, pen) of a channel mask."""
    fill, edge, width, *_ = _STYLES[kind]
    return pg.mkBrush(QColor(*fill)), pg.mkPen(QColor(*edge), width=width, style=Qt.PenStyle.DashLine)


def mask_text_color(kind: str) -> str:
    return _STYLES[kind][3]


def bar_colors(kind: str):
    """(fill, edge) QColors of a channel's block in the channel bar."""
    return QColor(*_STYLES[kind][4]), QColor(*_STYLES[kind][5])


def channel_label_html(mask_w_px: float, kind: str, ch_label, f_start: float, f_stop: float, info=None) -> str:
    """
    The text drawn at the top of a channel mask, fitted to the mask's width.

    info: the station on the channel, {"call", "place", "detail", "more"} (any
    may be missing; "more" counts further stations on the channel), or just a
    call sign. Without one the label is the channel and its frequency range.
    """
    if mask_w_px < 22:
        return ""
    label = str(ch_label).strip()
    if kind == "ch37":
        title = "CH 37 - OFF LIMITS" if mask_w_px >= 90 else ("CH 37" if mask_w_px >= 40 else "37")
    elif kind == "lmr":
        title = f"LMR {label}" if label.isdigit() else label
    elif kind == "dtv":
        title = f"DTV {label}"
    elif kind == "guard":
        title = "GUARD" if mask_w_px >= 40 else "GB"
    else:
        title = f"{'UL' if kind == 'uplink' else 'DL'} {label}"

    if isinstance(info, str):
        info = {"call": info}
    info = info or {}
    call = str(info.get("call") or "").strip()
    if call and info.get("more"):
        call += f" +{info['more']}"

    if mask_w_px >= 85:
        freq_range = f"{f_start:g} - {f_stop:g} MHz"
    elif mask_w_px >= 55:
        freq_range = f"{f_start:g}-{f_stop:g} MHz"
    else:
        freq_range = f"{int(f_start)}-{int(f_stop)}"

    # The title (and call sign) set the font size; the detail lines are shortened to fit
    avail_w = max(mask_w_px - 4, 10)
    font = QFont("sans-serif")
    font.setBold(True)
    pt = 10.0
    fitted = [title, call] if call else [title, freq_range]
    while pt >= 5.5:
        font.setPointSizeF(pt)
        if max(QFontMetrics(font).horizontalAdvance(text) for text in fitted) <= avail_w:
            break
        pt -= 0.5
    small_pt = max(pt - 1.0, 5.0)
    font.setBold(False)
    font.setPointSizeF(small_pt)
    small_fm = QFontMetrics(font)

    def small(text):
        # Too long for the mask: keep its first part ("Boston, MA" -> "Boston",
        # "1000 kW · 9 mi" -> "1000 kW") before resorting to an ellipsis
        for candidate in (text, text.split(" · ")[0], text.split(",")[0]):
            if small_fm.horizontalAdvance(candidate) <= avail_w:
                return html.escape(candidate)
        return html.escape(small_fm.elidedText(text.split(",")[0], Qt.TextElideMode.ElideRight, int(avail_w)))

    lines = [f"<div style='color: {mask_text_color(kind)}; font-weight: bold; font-size: {pt:.1f}pt;'>{html.escape(title)}</div>"]
    if call:
        lines.append(f"<div style='color: #facc15; font-weight: bold; font-size: {pt:.1f}pt;'>{html.escape(call)}</div>")
        if mask_w_px >= 40:
            for detail in (info.get("place"), info.get("detail")):
                if detail:
                    lines.append(f"<div style='color: #cbd5e1; font-size: {small_pt:.1f}pt;'>{small(str(detail))}</div>")
    else:
        lines.append(f"<div style='color: #cbd5e1; font-size: {small_pt:.1f}pt;'>{html.escape(freq_range)}</div>")
    return ("<div style='text-align: center; font-family: -apple-system, BlinkMacSystemFont, Segoe UI, Roboto, "
            "sans-serif; line-height: 1.15;'>" + "".join(lines) + "</div>")
