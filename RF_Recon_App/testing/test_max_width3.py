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
    min-width: 140px;
    max-width: 140px;
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
box = QDoubleSpinBox()
box.setSuffix(" dBm")
box.setRange(-200, 200)
box.setValue(-120.0)
l.addRow("Ref. Level:", box)

w.resize(500, 100)
w.grab().save("test25.png")
app.quit()
