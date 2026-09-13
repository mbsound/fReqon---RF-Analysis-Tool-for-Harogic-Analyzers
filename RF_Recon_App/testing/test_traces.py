import sys
import numpy as np
import pyqtgraph as pg
from PyQt6.QtWidgets import QApplication
from gui import MainWindow

app = QApplication(sys.argv)
win = MainWindow()
win.resize(1024, 768)

def setup():
    # turn on all traces
    win.trace_controls["Max. Hold"]['cb'].setChecked(True)
    win.trace_controls["Min. Hold"]['cb'].setChecked(True)
    win.trace_controls["Average"]['cb'].setChecked(True)
    
    # Freeze the Max Hold trace
    win.trace_controls["Max. Hold"]['freeze_cb'].setChecked(True)
    
    # set average to 1000
    win.avg_sweeps_spin.setValue(1000)
    
    # pump some fake data
    x = np.linspace(1e9, 2e9, 1000)
    for i in range(20):
        # random noisy data
        y = -100 + np.random.randn(1000) * 5
        # fake signal
        y[500:510] += 20 + np.random.randn(10) * 5
        win.update_plot(x, y)
        
    pg.QtCore.QTimer.singleShot(1000, lambda: win.grab().save("screenshot_traces.png") or app.quit())

pg.QtCore.QTimer.singleShot(100, setup)
app.exec()
