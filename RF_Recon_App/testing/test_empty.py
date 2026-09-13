import sys
import pyqtgraph as pg
from PyQt6.QtWidgets import QApplication
from gui import MainWindow

app = QApplication(sys.argv)
win = MainWindow()
win.resize(1024, 768)

def empty_bar():
    win.spectrum_channels.clear()
    win.waterfall_channels.clear()
    win.grab().save("test_empty.png")
    app.quit()

pg.QtCore.QTimer.singleShot(1000, empty_bar)
app.exec()
