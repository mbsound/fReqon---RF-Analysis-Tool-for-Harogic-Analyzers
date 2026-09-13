import sys
from PyQt6.QtWidgets import QApplication
from PyQt6.QtCore import QTimer
from gui import MainWindow

app = QApplication(sys.argv)
window = MainWindow()
window.show()

def on_status(msg):
    print("STATUS:", msg)
def on_data(freq, pwr):
    print(f"DATA: freq len {len(freq)}, pwr len {len(pwr)}")

window.controller.status_message.connect(on_status)
window.controller.spectrum_data_ready.connect(on_data)

print('Connecting...')
window.toggle_connection()

def apply_freqs():
    print('Applying new frequencies...')
    window.apply_frequencies()

def finish():
    print('Disconnecting...')
    window.toggle_connection()
    app.quit()

QTimer.singleShot(2000, apply_freqs)
QTimer.singleShot(4000, finish)

app.exec()
print('Done')
