import sys
import pyqtgraph as pg
from PyQt6.QtWidgets import QApplication
from gui import MainWindow

app = QApplication(sys.argv)
win = MainWindow()
win.resize(1024, 768)

def take_screenshot():
    win.grab().save("screenshot_launch.png")
    app.quit()

pg.QtCore.QTimer.singleShot(1000, take_screenshot)
app.exec()
