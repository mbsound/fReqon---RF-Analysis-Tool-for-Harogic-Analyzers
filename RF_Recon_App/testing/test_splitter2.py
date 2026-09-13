import sys
from PyQt6.QtWidgets import QApplication, QSplitter, QWidget, QVBoxLayout, QLabel
import pyqtgraph as pg
app = QApplication(sys.argv)
splitter = QSplitter()
w1 = QWidget()
l1 = QVBoxLayout(w1)
l1.addWidget(QLabel("Title 1"))
p1 = pg.PlotWidget()
l1.addWidget(p1)
print("w1 minimum height:", w1.minimumSizeHint().height())
print("p1 minimum height:", p1.minimumSizeHint().height())
