"""
channel_marker_bar.py - Interactive RF Channel & Band Allocation Strip.
Renders TV channels, Guard Bands, LTE blocks, DECT carriers, and PMR/TETRA allocations.
Synchronized with PyQtGraph frequency axes with click-to-mask and hover tooltips.
"""

import pyqtgraph as pg
from PyQt6.QtCore import Qt, QRectF, pyqtSignal
from PyQt6.QtGui import QBrush, QColor, QPen, QFont
from .channel_style import channel_kind, bar_colors

class MHzAxisItem(pg.AxisItem):
    """
    X-axis formatting helper displaying clean numeric frequency values.
    """
    def tickStrings(self, values, scale, spacing):
        return [f"{v:g}" for v in values]


class ClickableChannelItem(pg.GraphicsObject):
    channel_clicked = pyqtSignal(object, float, float)

    def __init__(self, ch_num, start_x, width, height=1.0, label_text=None, item_type="default", display_name=None):
        super().__init__()
        self.ch_num = ch_num
        self.start_freq = start_x
        self.stop_freq = start_x + width
        self.rect = QRectF(start_x, 0, width, height)
        self.item_type = item_type
        self.display_name = display_name or f"Channel {ch_num}"
        self.short_label = label_text or str(ch_num)
        self.is_active = True
        self.is_public_safety = False
        
        self.text = pg.TextItem(self.short_label, anchor=(0.5, 0.5), color='#f0f6fc')
        font = QFont()
        font.setFamilies(["Segoe UI", "Inter"])  # first installed one wins
        font.setStyleHint(QFont.StyleHint.SansSerif)
        font.setPointSize(8)
        font.setWeight(QFont.Weight.Bold)
        if self.item_type == "guard":
            font.setPointSize(7)
        self.text.setFont(font)
        self.text.setParentItem(self)
        self.text.setPos(start_x + width / 2.0, height / 2.0)
        self.setToolTip(f"{self.display_name}: {start_x/1e6:g} MHz - {(start_x+width)/1e6:g} MHz")
        
    def boundingRect(self):
        return self.rect
        
    def paint(self, p, *args):
        view = self.getViewBox()
        if view is not None:
            v_range = view.viewRange()[0]
            # Frustum culling
            if self.stop_freq < v_range[0] or self.start_freq > v_range[1]:
                self.text.setVisible(False)
                return
                
            hz_per_pixel = view.viewPixelSize()[0]
            pixel_width = self.rect.width() / (hz_per_pixel if hz_per_pixel > 0 else 1.0)
            
            min_px = 10 if self.item_type == "guard" else 14
            self.text.setVisible(pixel_width >= min_px)
            hz_gap = hz_per_pixel * 2
        else:
            hz_gap = self.rect.width() * 0.02

        if self.is_active:
            fill, edge = bar_colors(channel_kind(self.item_type, self.is_public_safety))
            p.setBrush(QBrush(fill))
            p.setPen(QPen(edge, 1))
        else:
            # Muted inactive state
            p.setBrush(QBrush(QColor(30, 41, 59, 120)))
            p.setPen(QPen(QColor(51, 65, 85), 1))
        
        draw_width = max(self.rect.width() - hz_gap, self.rect.width() * 0.1)
        draw_rect = QRectF(self.rect.x() + hz_gap / 2, self.rect.y(), draw_width, self.rect.height() * 0.82)
        draw_rect.moveTop(0.09)
        p.drawRoundedRect(draw_rect, 1.5, 1.5)
        
    def mouseClickEvent(self, ev):
        if ev.button() == Qt.MouseButton.LeftButton:
            self.channel_clicked.emit(self.ch_num, self.start_freq, self.stop_freq)
            ev.accept()
        else:
            ev.ignore()


class ChannelMarkerBar(pg.PlotWidget):
    channel_clicked = pyqtSignal(object, float, float)
    
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setFixedHeight(26)
        self.hideAxis('bottom')
        self.getPlotItem().layout.removeItem(self.getAxis('bottom'))
        
        left_axis = self.getAxis('left')
        left_axis.setPen(pg.mkPen(color=(0,0,0,0)))
        left_axis.setTextPen(pg.mkPen(color=(0,0,0,0)))
        
        self.setMouseEnabled(x=False, y=False)
        self.setMenuEnabled(False)
        self.setBackground('#0d1117')
        self.getViewBox().disableAutoRange()
        self.setYRange(0, 1, padding=0)
        self.hideButtons()
        
        if hasattr(self.plotItem, 'autoBtn') and self.plotItem.autoBtn:
            self.plotItem.autoBtn.setParentItem(None)
            self.plotItem.autoBtn.hide()

    def on_channel_clicked(self, ch_num, start_freq, stop_freq):
        self.channel_clicked.emit(ch_num, start_freq, stop_freq)

    def update_visibility(self, view_box, range):
        x_min, x_max = range
        for item in getattr(self.plotItem, 'items', []):
            if isinstance(item, ClickableChannelItem):
                if item.start_freq <= x_max and item.stop_freq >= x_min:
                    item.setVisible(True)
                else:
                    item.setVisible(False)

    def set_active_channels(self, active_dict, ps_dict=None):
        if ps_dict is None:
            ps_dict = {}
        for item in getattr(self.plotItem, 'items', []):
            if isinstance(item, ClickableChannelItem):
                item.is_active = active_dict.get(item.ch_num, False)
                item.is_public_safety = ps_dict.get(item.ch_num, False)
                item.update()

    def draw_channels(self, standard, x_mult=1e6):
        self.clear()
        if not standard:
            return
        
        if isinstance(standard, dict):
            standard = [standard]
            
        for band in standard:
            if "custom_items" in band:
                for c_item in band["custom_items"]:
                    c_id = c_item["id"]
                    start_freq = c_item["start"] * (1e6 / x_mult)
                    stop_freq = c_item["stop"] * (1e6 / x_mult)
                    width = stop_freq - start_freq
                    item = ClickableChannelItem(
                        ch_num=c_id,
                        start_x=start_freq,
                        width=width,
                        label_text=c_item.get("label", str(c_id)),
                        item_type=c_item.get("type", "default"),
                        display_name=c_item.get("display_name")
                    )
                    item.channel_clicked.connect(self.on_channel_clicked)
                    self.addItem(item)
                continue
                
            start_ch = band["start_ch"]
            end_ch = band["end_ch"]
            start_freq = band["start_freq"] * (1e6 / x_mult)
            spacing = band["spacing"] * (1e6 / x_mult)
            
            for ch in range(start_ch, end_ch + 1):
                ch_idx = ch - start_ch
                f_start = start_freq + (ch_idx * spacing)
                
                item = ClickableChannelItem(ch, f_start, spacing, item_type=band.get("type", "default"))
                item.channel_clicked.connect(self.on_channel_clicked)
                self.addItem(item)
