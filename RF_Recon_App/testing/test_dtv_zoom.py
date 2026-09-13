import sys
import pyqtgraph as pg
from PyQt6.QtWidgets import QApplication
from gui import MainWindow

app = QApplication(sys.argv)
win = MainWindow()
win.resize(1024, 768)

def setup():
    win.start_spin.setValue(470)
    win.stop_spin.setValue(800)
    win.apply_frequencies()
    pg.QtCore.QTimer.singleShot(500, lambda: win.grab().save("screenshot_dtv_zoom.png") or app.quit())

pg.QtCore.QTimer.singleShot(100, setup)
app.exec()
