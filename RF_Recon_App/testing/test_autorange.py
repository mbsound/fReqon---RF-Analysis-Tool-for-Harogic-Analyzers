import sys
import pyqtgraph as pg
from PyQt6.QtWidgets import QApplication, QMainWindow

app = QApplication(sys.argv)
win = QMainWindow()
plot = pg.PlotWidget()
win.setCentralWidget(plot)

plot.setYRange(-120, 10)
plot.setXRange(100, 200, padding=0)

plot.getViewBox().disableAutoRange()
plot.getViewBox().setAutoVisible(x=False, y=False)

win.show()
print("Initial:", plot.getViewBox().viewRange())
win.resize(1000, 800)
app.processEvents()
print("After resize:", plot.getViewBox().viewRange())

