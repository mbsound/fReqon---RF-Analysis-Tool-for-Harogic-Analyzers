import sys
import pyqtgraph as pg
from PyQt6.QtWidgets import QApplication
from gui import MainWindow

app = QApplication(sys.argv)
win = MainWindow()

def check_sig():
    print("Visibility of first item:", win.spectrum_channels.plotItem.items[0].isVisible())
    app.quit()

pg.QtCore.QTimer.singleShot(1000, check_sig)
app.exec()
