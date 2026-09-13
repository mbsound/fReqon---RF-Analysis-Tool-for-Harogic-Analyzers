import sys, pyqtgraph as pg
from PyQt6.QtWidgets import QApplication, QVBoxLayout, QWidget
app = QApplication(sys.argv)
win = QWidget()
layout = QVBoxLayout(win)

cw = pg.GraphicsLayoutWidget()
cw.setFixedHeight(40)
plot = pg.PlotWidget()
img = pg.ImageItem()
plot.addItem(img)

cb = pg.ColorBarItem(values=(-120, -20), colorMap=pg.colormap.get('viridis'), orientation='horizontal')
cb.setImageItem(img)
cw.addItem(cb)

layout.addWidget(cw)
layout.addWidget(plot)

win.show()
print("Success")
