import sys
import pyqtgraph as pg
from PyQt6.QtWidgets import QApplication
from gui import MainWindow

app = QApplication(sys.argv)
win = MainWindow()
win.resize(1024, 768)

def check_range():
    print("Plot widget X range:", win.plot_widget.viewRange()[0])
    print("ChannelMarkerBar X range:", win.spectrum_channels.viewRange()[0])
    app.quit()

pg.QtCore.QTimer.singleShot(1000, check_range)
app.exec()
