import sys
from PyQt6.QtWidgets import QApplication, QWidget, QFormLayout, QDoubleSpinBox, QVBoxLayout
from PyQt6.QtCore import Qt

app = QApplication(sys.argv)
win = QWidget()
win.resize(600, 200)

layout = QVBoxLayout(win)
form = QFormLayout()

# How we currently have it
form.setFieldGrowthPolicy(QFormLayout.FieldGrowthPolicy.FieldsStayAtSizeHint)

# Fix for the gap stretching!
form.setFormAlignment(Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignTop)
form.setLabelAlignment(Qt.AlignmentFlag.AlignLeft)

box = QDoubleSpinBox()
box.setMaximumWidth(110)

form.addRow("Ref. Level:", box)
layout.addLayout(form)

print("Test configured.")

sys.exit(0)
