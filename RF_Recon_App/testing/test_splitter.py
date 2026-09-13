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
w2 = QWidget()
l2 = QVBoxLayout(w2)
l2.addWidget(QLabel("Title 2"))
p2 = pg.PlotWidget()
l2.addWidget(p2)
splitter.addWidget(w1)
splitter.addWidget(w2)
splitter.show()
print(splitter.handleWidth())
