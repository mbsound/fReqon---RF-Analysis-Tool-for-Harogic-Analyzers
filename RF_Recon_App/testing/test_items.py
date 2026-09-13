import sys
import pyqtgraph as pg
from PyQt6.QtWidgets import QApplication
from gui import MainWindow

app = QApplication(sys.argv)
win = MainWindow()

def check_items():
    print("Items in spectrum_channels:")
    for item in win.spectrum_channels.items():
        print(f" - {type(item)}: isVisible={item.isVisible()}")
    app.quit()

pg.QtCore.QTimer.singleShot(1000, check_items)
app.exec()
