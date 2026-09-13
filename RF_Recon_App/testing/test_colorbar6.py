import sys, pyqtgraph as pg
from PyQt6.QtWidgets import QApplication
app = QApplication(sys.argv)
win = pg.PlotWidget()
img = pg.ImageItem()
win.addItem(img)
cb = pg.ColorBarItem(values=(-120, -20), colorMap=pg.colormap.get('viridis'), orientation='horizontal')
cb.setImageItem(img)
# Put cb inside the viewbox
cb.setParentItem(win.getPlotItem().vb)
cb.setPos(10, 10)
print("Success")
