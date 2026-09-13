import sys, pyqtgraph as pg
from PyQt6.QtWidgets import QApplication
app = QApplication(sys.argv)
win = pg.PlotWidget()
curve = win.plot(pen='y')
import numpy as np
x = np.linspace(1e9, 2e9, 1000)
y = np.random.normal(size=1000)
curve.setData(x, y)
win.autoRange()
print("XRange:", win.viewRange()[0])
