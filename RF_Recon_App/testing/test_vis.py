import sys
import pyqtgraph as pg
from PyQt6.QtWidgets import QApplication
from gui import MainWindow

app = QApplication(sys.argv)
win = MainWindow()
win.resize(1024, 768)

def check_visibility():
    count = 0
    for item in win.spectrum_channels.items():
        if hasattr(item, 'start_freq') and item.isVisible():
            count += 1
    print(f"Visible items: {count}")
    app.quit()

pg.QtCore.QTimer.singleShot(1000, check_visibility)
app.exec()
