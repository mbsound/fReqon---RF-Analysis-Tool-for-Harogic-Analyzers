import sys, pyqtgraph as pg
from PyQt6.QtWidgets import QApplication
app = QApplication(sys.argv)
win = pg.PlotWidget()
img = pg.ImageItem()
cb = pg.ColorBarItem(values=(-120, -20), colorMap=pg.colormap.get('viridis'), orientation='horizontal')
cb.setImageItem(img, insert_in=win.getPlotItem())
print("Success")
