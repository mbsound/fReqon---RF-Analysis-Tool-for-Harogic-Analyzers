import sys
import pyqtgraph as pg
from PyQt6.QtWidgets import QApplication

class MHzAxisItem(pg.AxisItem):
    def tickStrings(self, values, scale, spacing):
        return [f"{v / 1e6:g}" for v in values]

app = QApplication(sys.argv)
pw = pg.PlotWidget(axisItems={'bottom': MHzAxisItem(orientation='bottom')})
pw.setXRange(1e9, 2e9)
pw.grab().save("test_mhz_axis.png")
