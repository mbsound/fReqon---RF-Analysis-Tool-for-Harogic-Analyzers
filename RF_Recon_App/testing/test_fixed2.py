import sys
from PyQt6.QtWidgets import QApplication
from PyQt6.QtCore import QTimer
from gui import MainWindow
import numpy as np

app = QApplication(sys.argv)
win = MainWindow()
win.show()

def run_test():
    x = np.linspace(win.start_spin.value()*1e6, win.stop_spin.value()*1e6, 1000)
    y = np.random.randn(1000) - 50
    win.update_plot(x, y)
    
    win.on_channel_clicked(14, 470e6, 476e6)
    
    QTimer.singleShot(1000, finish_test)

def finish_test():
    pixmap = win.grab()
    pixmap.save("screenshot_fixed2.png")
    app.quit()

QTimer.singleShot(1000, run_test)
sys.exit(app.exec())
