import sys
import pyqtgraph as pg
from PyQt6.QtWidgets import QApplication
from gui import MainWindow

app = QApplication(sys.argv)
win = MainWindow()
win.resize(1024, 768)
win.start_spin.setValue(400)
win.stop_spin.setValue(800)
win.apply_frequencies()

# Let the event loop process a bit to draw
def take_screenshot():
    win.grab().save("screenshot1.png")
    app.quit()

pg.QtCore.QTimer.singleShot(1000, take_screenshot)
app.exec()
