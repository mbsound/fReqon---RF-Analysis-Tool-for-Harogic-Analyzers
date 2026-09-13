import sys
import pyqtgraph as pg
from PyQt6.QtWidgets import QApplication

from gui import ChannelMarkerBar

app = QApplication(sys.argv)

bar = ChannelMarkerBar()
standard = {
    "start_ch": 14,
    "end_ch": 83,
    "start_freq": 470.0,
    "spacing": 6.0
}
bar.draw_channels(standard)
bar.resize(800, 30)

# Save the widget as an image
bar.grab().save("test_bar.png")
