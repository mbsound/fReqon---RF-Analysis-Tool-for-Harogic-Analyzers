import sys
import pyqtgraph as pg
from PyQt6.QtWidgets import QApplication, QVBoxLayout, QWidget, QGraphicsRectItem

app = QApplication(sys.argv)
win = QWidget()
layout = QVBoxLayout(win)

pw1 = pg.PlotWidget()
layout.addWidget(pw1)

pw2 = pg.PlotWidget()
pw2.hideAxis('left')
pw2.hideAxis('bottom')
layout.addWidget(pw2)

pw2.setXLink(pw1)

text = pg.TextItem("TEST", color='w')
text.setPos(0, 0.5)
pw2.addItem(text)

rect = QGraphicsRectItem(0, 0, 100, 1)
rect.setBrush(pg.mkBrush('r'))
pw2.addItem(rect)

pw1.setXRange(1000, 2000, padding=0)

win.show()
win.resize(400, 300)
win.grab().save("test_clip.png")
app.quit()
