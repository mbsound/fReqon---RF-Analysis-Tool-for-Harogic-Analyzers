import sys
import pyqtgraph as pg
from PyQt6.QtWidgets import QApplication
from gui import MainWindow

app = QApplication(sys.argv)
win = MainWindow()
win.resize(1024, 768)

def setup():
    win.start_spin.setValue(470)
    win.stop_spin.setValue(500)
    win.apply_frequencies()
    
    # Simulate a click on channel 14
    win.on_channel_clicked(14, 470e6, 476e6)
    
    pg.QtCore.QTimer.singleShot(500, lambda: win.grab().save("screenshot_toggle.png") or app.quit())

pg.QtCore.QTimer.singleShot(100, setup)
app.exec()
