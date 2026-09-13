import sys
from PyQt6.QtWidgets import QApplication
from gui import MainWindow

app = QApplication(sys.argv)
win = MainWindow()
print(f"Min Size Hint: {win.minimumSizeHint()}")
