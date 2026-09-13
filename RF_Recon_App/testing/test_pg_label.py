import pyqtgraph as pg
from pyqtgraph.Qt import QtWidgets
import sys
import numpy as np

app = QtWidgets.QApplication(sys.argv)
win = pg.GraphicsLayoutWidget(show=True)
p1 = win.addPlot()
x = np.linspace(1.5, 1.6, 100) # In GHz
y = np.random.normal(size=100)
p1.plot(x, y)

# Set literal label, no auto SI units
p1.setLabel('bottom', 'Frequency (GHz)')

win.grab().save("test20.png")
app.quit()
