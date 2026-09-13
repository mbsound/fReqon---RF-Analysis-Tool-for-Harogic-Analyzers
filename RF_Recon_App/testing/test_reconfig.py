import sys, time
from PyQt6.QtWidgets import QApplication
from gui import MainWindow
app = QApplication(sys.argv)
window = MainWindow()
window.show()
print('Connecting...')
window.toggle_connection()
time.sleep(2)
print('Applying new frequencies...')
window.apply_frequencies()
time.sleep(2)
print('Disconnecting...')
window.toggle_connection()
print('Done')
