import sys
from PyQt6.QtWidgets import QApplication
from PyQt6.QtCore import QTimer
from gui import MainWindow

app = QApplication(sys.argv)
window = MainWindow()
window.show()

def apply_freqs():
    window.start_spin.setValue(3000.0)
    window.stop_spin.setValue(4000.0)
    print('Applying new frequencies...')
    window.apply_frequencies()

def finish():
    print('Disconnecting...')
    window.toggle_connection()
    app.quit()

print('Connecting...')
window.toggle_connection()
QTimer.singleShot(2000, apply_freqs)
QTimer.singleShot(4000, finish)
app.exec()
print('Done')
