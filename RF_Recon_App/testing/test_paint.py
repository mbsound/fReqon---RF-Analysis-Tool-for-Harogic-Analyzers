import sys
import pyqtgraph as pg
from PyQt6.QtWidgets import QApplication
from gui import MainWindow

app = QApplication(sys.argv)
win = MainWindow()

def check_paint():
    app.quit()

pg.QtCore.QTimer.singleShot(1000, check_paint)
app.exec()
