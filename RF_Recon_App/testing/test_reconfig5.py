import sys
from PyQt6.QtWidgets import QApplication
from PyQt6.QtCore import QTimer
from gui import MainWindow

app = QApplication(sys.argv)
window = MainWindow()
window.show()

def apply_freqs():
    window.start_spin.setValue(1000.0)
    window.stop_spin.setValue(2000.0)
    print('Applying new frequencies...')
    window.apply_frequencies()

print('Connecting...')
window.toggle_connection()
QTimer.singleShot(2000, apply_freqs)
QTimer.singleShot(4000, lambda: app.quit())
app.exec()
print('Done')
