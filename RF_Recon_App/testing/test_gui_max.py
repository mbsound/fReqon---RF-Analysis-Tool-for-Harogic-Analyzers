import sys
from PyQt6.QtWidgets import QApplication
from gui import MainWindow
app = QApplication(sys.argv)
win = MainWindow()
win.resize(1000, 600)
win.setStyleSheet(win.styleSheet() + " QDoubleSpinBox, QSpinBox { max-width: 145px; }")
win.grab().save("test27.png")
app.quit()
