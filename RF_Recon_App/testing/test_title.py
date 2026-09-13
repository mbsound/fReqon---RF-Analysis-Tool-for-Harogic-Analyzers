import sys, pyqtgraph as pg
from PyQt6.QtWidgets import QApplication
app = QApplication(sys.argv)
win = pg.PlotWidget(title="Spectrogram")
win.setTitle("Spectrogram", justify='left')
print(win.getPlotItem().titleLabel.opts.get('justify'))
