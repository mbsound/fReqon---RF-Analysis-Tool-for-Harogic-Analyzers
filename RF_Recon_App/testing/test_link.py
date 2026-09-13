import sys
import pyqtgraph as pg
from PyQt6.QtWidgets import QApplication
from gui import MainWindow

app = QApplication(sys.argv)
win = MainWindow()

def check_called():
    app.quit()

pg.QtCore.QTimer.singleShot(1000, check_called)
app.exec()
