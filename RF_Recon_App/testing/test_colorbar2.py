import sys, pyqtgraph as pg
from PyQt6.QtWidgets import QApplication
app = QApplication(sys.argv)
win = pg.PlotWidget(title="") # Title occupies row 0 usually!
img = pg.ImageItem()
win.addItem(img)
cb = pg.ColorBarItem(values=(-120, -20), colorMap=pg.colormap.get('viridis'), orientation='horizontal')
cb.setImageItem(img)
plot_item = win.getPlotItem()
plot_item.layout.addItem(cb, 0, 1) # title might be at 0, 1
print("Success")
