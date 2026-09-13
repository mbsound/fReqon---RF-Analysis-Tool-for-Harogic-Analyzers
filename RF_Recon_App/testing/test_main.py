import sys
from PyQt6.QtWidgets import QApplication
from gui import MainWindow
app = QApplication(sys.argv)
win = MainWindow()
win.resize(1000, 600)
win.grab().save("test18.png")
app.quit()
