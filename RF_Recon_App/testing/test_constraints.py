import sys
from PyQt6.QtWidgets import QApplication
from gui import MainWindow

app = QApplication(sys.argv)
win = MainWindow()
print(f"Window Min: {win.minimumSize()}, Max: {win.maximumSize()}")
print(f"Central Widget Min: {win.centralWidget().minimumSize()}, Max: {win.centralWidget().maximumSize()}")
print(f"Layout size constraint: {win.centralWidget().layout().sizeConstraint()}")
