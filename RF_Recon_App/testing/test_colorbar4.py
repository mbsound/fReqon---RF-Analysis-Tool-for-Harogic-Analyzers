import sys, pyqtgraph as pg
from PyQt6.QtWidgets import QApplication
app = QApplication(sys.argv)
win = pg.PlotWidget(title="Spectrogram")
img = pg.ImageItem()
win.addItem(img)
cb = pg.ColorBarItem(values=(-120, -20), colorMap=pg.colormap.get('viridis'), orientation='horizontal')
cb.setImageItem(img)
plot_item = win.getPlotItem()
plot_item.layout.addItem(cb, 1, 1) # row 1 is below title, above viewbox
print("Success")
