import sys, time
from PyQt6.QtWidgets import QApplication
from PyQt6.QtCore import QTimer
from gui import MainWindow

app = QApplication(sys.argv)
window = MainWindow()
window.show()

counter = 0
def on_data(freq, pwr):
    global counter
    counter += 1
    print(f"GUI Received data frame {counter}")

window.controller.spectrum_data_ready.connect(on_data)

print('Connecting...')
window.toggle_connection()
QTimer.singleShot(10000, lambda: app.quit())
app.exec()
print('Done. Total frames:', counter)
