import sys
import pyqtgraph as pg
from PyQt6.QtWidgets import QApplication
from PyQt6.QtCore import Qt, QRectF
from PyQt6.QtGui import QBrush, QColor, QPen

class ClickableChannelItem(pg.GraphicsObject):
    def __init__(self, ch_num, start_x, width, height=1.0):
        super().__init__()
        self.ch_num = ch_num
        self.rect = QRectF(start_x, 0, width, height)
        
        # We can add text as a child
        self.text = pg.TextItem(f"{ch_num}", anchor=(0.5, 0.5), color='w')
        self.text.setParentItem(self)
        self.text.setPos(start_x + width / 2.0, height / 2.0)
        
        # To make it clickable, we need to accept hover events or just mouse click
        # Wait, pg.GraphicsObject needs boundingRec and paint
        
    def boundingRect(self):
        return self.rect
        
    def paint(self, p, *args):
        p.setBrush(QBrush(QColor(120, 120, 120)))
        p.setPen(QPen(QColor(50, 50, 50), 1))
        # draw rect slightly smaller than width to have a gap
        draw_rect = QRectF(self.rect.x(), self.rect.y(), self.rect.width() * 0.95, self.rect.height())
        p.drawRect(draw_rect)
        
    def mouseClickEvent(self, ev):
        if ev.button() == Qt.MouseButton.LeftButton:
            print(f"Clicked channel {self.ch_num}")
            ev.accept()
        else:
            ev.ignore()

app = QApplication(sys.argv)
pw = pg.PlotWidget()
pw.setYRange(0, 1, padding=0)

for i in range(14, 20):
    item = ClickableChannelItem(i, i * 10, 10)
    pw.addItem(item)

pw.grab().save("test_clickable.png")
