import sys
import pyqtgraph as pg
from PyQt6.QtWidgets import QApplication
from gui import MainWindow

app = QApplication(sys.argv)
win = MainWindow()

def check_list():
    items = getattr(win.spectrum_channels.plotItem, 'items', [])
    print(f"Items type: {type(items)}")
    print(f"Items length: {len(items)}")
    for item in items[:2]:
        print(type(item))
    app.quit()

pg.QtCore.QTimer.singleShot(1000, check_list)
app.exec()
