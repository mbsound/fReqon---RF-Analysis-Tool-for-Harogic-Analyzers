import pyqtgraph as pg
from pyqtgraph.Qt import QtWidgets
import sys

app = QtWidgets.QApplication(sys.argv)
win = pg.GraphicsLayoutWidget(show=True, title="Basic plotting examples")
win.resize(1000,600)
p1 = win.addPlot(title="Basic array plotting")
p1.setLabel('bottom', 'Frequency', units='Hz')

# Plot 1 GHz to 2 GHz
import numpy as np
x = np.linspace(1e9, 2e9, 100)
y = np.random.normal(size=100)
p1.plot(x, y)

win.grab().save("test19.png")
app.quit()
