import sys
from PyQt6.QtWidgets import QApplication, QDoubleSpinBox, QWidget, QFormLayout
app = QApplication(sys.argv)
app.setStyle("Fusion")
w = QWidget()
w.setStyleSheet("""
QDoubleSpinBox {
    background-color: #2b2b2b;
    color: #ffffff;
    border: 1px solid #555555;
    border-radius: 4px;
    padding: 0px 32px 0px 32px;
    min-height: 30px;
    max-width: 150px;
    qproperty-alignment: 'AlignHCenter';
}
QDoubleSpinBox::up-button {
    subcontrol-position: right;
    width: 32px;
}
QDoubleSpinBox::down-button {
    subcontrol-position: left;
    width: 32px;
}
""")
l = QFormLayout(w)
box1 = QDoubleSpinBox()
box1.setSuffix(" dBm")
box1.setRange(-200, 200)
box1.setValue(-120.0)
l.addRow("Ref. Level:", box1)

box2 = QDoubleSpinBox()
box2.setSuffix(" GHz")
box2.setValue(1.5)
l.addRow("Start:", box2)

w.resize(500, 100)
w.grab().save("test26.png")
app.quit()
