import sys
from PyQt6.QtWidgets import QApplication, QWidget, QHBoxLayout, QVBoxLayout, QFormLayout, QDoubleSpinBox, QLabel
app = QApplication(sys.argv)
app.setStyle("Fusion")
w = QWidget()
w.setStyleSheet("background-color: #2b2b2b;")
h_layout = QHBoxLayout(w)

left_panel = QWidget()
left_layout = QVBoxLayout(left_panel)
amp_form = QFormLayout()
ref_spin = QDoubleSpinBox()
ref_spin.setRange(-200.0, 100.0)
ref_spin.setValue(-200.0)
ref_spin.setSuffix(" dBm")
ref_spin.setDecimals(1)
amp_form.addRow("Ref. Level:", ref_spin)
left_layout.addLayout(amp_form)

right_panel = QWidget()
right_layout = QVBoxLayout(right_panel)
start_spin = QDoubleSpinBox()
start_spin.setRange(0.1, 20000.0)
start_spin.setValue(20000.0)
start_spin.setSuffix(" MHz")
start_spin.setDecimals(1)
right_layout.addWidget(start_spin)

h_layout.addWidget(left_panel)
h_layout.addWidget(right_panel)

# Apply QSS
w.setStyleSheet("""
    QDoubleSpinBox {
        border: 1px solid #555555;
        border-radius: 4px;
        padding: 0px 32px 0px 32px;
        min-height: 30px;
        min-width: 170px;
        background-color: #111111;
        color: white;
    }
    QDoubleSpinBox::up-button {
        subcontrol-origin: border;
        subcontrol-position: right;
        width: 32px;
        height: 32px;
        border-left: 1px solid #555555;
        background-color: #333333;
        border-top-right-radius: 4px;
        border-bottom-right-radius: 4px;
    }
    QDoubleSpinBox::down-button {
        subcontrol-origin: border;
        subcontrol-position: left;
        width: 32px;
        height: 32px;
        border-right: 1px solid #555555;
        background-color: #333333;
        border-top-left-radius: 4px;
        border-bottom-left-radius: 4px;
    }
    QLabel { color: white; }
""")

w.resize(600, 200) # Simulating a small-ish window
w.grab().save("test16.png")
app.quit()
