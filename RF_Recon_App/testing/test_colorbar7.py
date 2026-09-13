import sys, pyqtgraph as pg
from PyQt6.QtWidgets import QApplication
app = QApplication(sys.argv)
win = pg.PlotWidget()
img = pg.ImageItem()
win.addItem(img)
cb = pg.ColorBarItem(values=(-120, -20), colorMap=pg.colormap.get('viridis'), orientation='horizontal')
cb.setImageItem(img)
cb.setParentItem(win.getPlotItem())
cb.anchor(itemPos=(1, 0), parentPos=(1, 0), offset=(-10, 10))
print("Success")
