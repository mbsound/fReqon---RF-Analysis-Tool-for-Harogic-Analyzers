import sys
from PyQt6.QtWidgets import QApplication
from gui import MainWindow
app = QApplication(sys.argv)
win = MainWindow()
win.resize(1000, 600)
# Force one button to be checked
win.quick_btns[0].setChecked(True)
win.quick_btns[0].setText("VHF")
win.grab().save("test30.png")
app.quit()
