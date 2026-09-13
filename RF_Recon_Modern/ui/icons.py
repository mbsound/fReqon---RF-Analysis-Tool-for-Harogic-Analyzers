"""
icons.py - Professional Vector Icon Provider for RF Recon Modern.
Renders clean, high-DPI vector icons using QPainter.
Zero emojis, strict professional industrial test-and-measurement aesthetic.
"""

from PyQt6.QtGui import QIcon, QPixmap, QPainter, QColor, QPen, QBrush, QPainterPath, QPolygonF
from PyQt6.QtCore import Qt, QPointF, QRectF

def _create_pixmap(size=24):
    pix = QPixmap(size, size)
    pix.fill(Qt.GlobalColor.transparent)
    return pix

def get_play_icon(color="#10b981", size=24) -> QIcon:
    pix = _create_pixmap(size)
    p = QPainter(pix)
    p.setRenderHint(QPainter.RenderHint.Antialiasing)
    p.setBrush(QBrush(QColor(color)))
    p.setPen(Qt.PenStyle.NoPen)
    
    # Right-pointing triangle
    margin = size * 0.25
    points = [
        QPointF(margin + 2, margin),
        QPointF(size - margin + 2, size / 2.0),
        QPointF(margin + 2, size - margin)
    ]
    p.drawPolygon(QPolygonF(points))
    p.end()
    return QIcon(pix)

def get_pause_icon(color="#f59e0b", size=24) -> QIcon:
    pix = _create_pixmap(size)
    p = QPainter(pix)
    p.setRenderHint(QPainter.RenderHint.Antialiasing)
    p.setBrush(QBrush(QColor(color)))
    p.setPen(Qt.PenStyle.NoPen)
    
    w = size * 0.22
    h = size * 0.55
    y = (size - h) / 2.0
    x1 = size * 0.25
    x2 = size * 0.53
    
    p.drawRoundedRect(QRectF(x1, y, w, h), 2, 2)
    p.drawRoundedRect(QRectF(x2, y, w, h), 2, 2)
    p.end()
    return QIcon(pix)

def get_chevron_icon(direction="right", color="#8b949e", size=20) -> QIcon:
    pix = _create_pixmap(size)
    p = QPainter(pix)
    p.setRenderHint(QPainter.RenderHint.Antialiasing)
    pen = QPen(QColor(color), 2.0, Qt.PenStyle.SolidLine, Qt.PenCapStyle.RoundCap, Qt.PenJoinStyle.RoundJoin)
    p.setPen(pen)
    
    m = size * 0.3
    c = size / 2.0
    
    if direction == "right":
        p.drawLine(QPointF(m, m), QPointF(size - m, c))
        p.drawLine(QPointF(size - m, c), QPointF(m, size - m))
    elif direction == "left":
        p.drawLine(QPointF(size - m, m), QPointF(m, c))
        p.drawLine(QPointF(m, c), QPointF(size - m, size - m))
    elif direction == "down":
        p.drawLine(QPointF(m, m), QPointF(c, size - m))
        p.drawLine(QPointF(c, size - m), QPointF(size - m, m))
    elif direction == "up":
        p.drawLine(QPointF(m, size - m), QPointF(c, m))
        p.drawLine(QPointF(c, m), QPointF(size - m, size - m))
        
    p.end()
    return QIcon(pix)

def get_settings_icon(color="#8b949e", size=24) -> QIcon:
    pix = _create_pixmap(size)
    p = QPainter(pix)
    p.setRenderHint(QPainter.RenderHint.Antialiasing)
    pen = QPen(QColor(color), 1.8, Qt.PenStyle.SolidLine, Qt.PenCapStyle.RoundCap)
    p.setPen(pen)
    p.setBrush(Qt.BrushStyle.NoBrush)
    
    c = size / 2.0
    r_outer = size * 0.35
    r_inner = size * 0.16
    
    p.drawEllipse(QPointF(c, c), r_inner, r_inner)
    
    # 6 teeth
    import math
    for i in range(6):
        angle = i * (math.pi / 3.0)
        x1 = c + (r_inner + 1) * math.cos(angle)
        y1 = c + (r_inner + 1) * math.sin(angle)
        x2 = c + r_outer * math.cos(angle)
        y2 = c + r_outer * math.sin(angle)
        p.drawLine(QPointF(x1, y1), QPointF(x2, y2))
        
    p.end()
    return QIcon(pix)

def get_alert_icon(color="#f43f5e", size=24) -> QIcon:
    pix = _create_pixmap(size)
    p = QPainter(pix)
    p.setRenderHint(QPainter.RenderHint.Antialiasing)
    
    # Triangle
    p.setBrush(QBrush(QColor(color)))
    p.setPen(Qt.PenStyle.NoPen)
    points = [
        QPointF(size / 2.0, 3),
        QPointF(size - 3, size - 4),
        QPointF(3, size - 4)
    ]
    p.drawPolygon(QPolygonF(points))
    
    # Exclamation mark inside
    p.setPen(QPen(QColor("#000000"), 1.8, Qt.PenStyle.SolidLine, Qt.PenCapStyle.RoundCap))
    p.drawLine(QPointF(size / 2.0, size * 0.38), QPointF(size / 2.0, size * 0.65))
    p.drawPoint(QPointF(size / 2.0, size * 0.78))
    
    p.end()
    return QIcon(pix)

def get_signal_icon(color="#38bdf8", size=24) -> QIcon:
    pix = _create_pixmap(size)
    p = QPainter(pix)
    p.setRenderHint(QPainter.RenderHint.Antialiasing)
    pen = QPen(QColor(color), 1.8, Qt.PenStyle.SolidLine, Qt.PenCapStyle.RoundCap)
    p.setPen(pen)
    p.setBrush(Qt.BrushStyle.NoBrush)
    
    c = size / 2.0
    base_y = size * 0.75
    
    # Concentric arcs
    p.drawArc(QRectF(c - 8, base_y - 8, 16, 16), 45 * 16, 90 * 16)
    p.drawArc(QRectF(c - 14, base_y - 14, 28, 28), 45 * 16, 90 * 16)
    
    p.setBrush(QBrush(QColor(color)))
    p.drawEllipse(QPointF(c, base_y), 2, 2)
    p.end()
    return QIcon(pix)
