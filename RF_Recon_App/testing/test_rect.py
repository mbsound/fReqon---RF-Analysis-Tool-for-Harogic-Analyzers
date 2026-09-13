import sys
from PyQt6.QtWidgets import QApplication
import pyqtgraph as pg
from PyQt6.QtCore import QRectF

class TestItem(pg.GraphicsObject):
    def boundingRect(self):
        return QRectF(470, 0, 6, 1)
    
    def paint(self, p, *args):
        p.setPen(pg.mkPen('r', width=1))
        p.drawRect(QRectF(470, 0, 6, 1))

app = QApplication(sys.argv)
win = pg.PlotWidget()
win.setXRange(465, 480)

# Draw a standard pyqtgraph curve
curve = win.plot([470, 470, 476, 476], [0, 1, 1, 0], pen='g')

# Draw our custom item
item = TestItem()
win.addItem(item)

# Save image
from PyQt6.QtCore import QTimer
def save():
    win.grab().save('test_rect.png')
    app.quit()
    
QTimer.singleShot(1000, save)
win.show()
app.exec()
