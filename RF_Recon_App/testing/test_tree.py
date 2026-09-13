import sys
from PyQt6.QtWidgets import QApplication, QWidget, QLayout
from gui import MainWindow

def dump_tree(obj, depth=0):
    indent = "  " * depth
    name = obj.objectName() or type(obj).__name__
    if isinstance(obj, QWidget):
        print(f"{indent}Widget: {name}, max: {obj.maximumSize()}")
        layout = obj.layout()
        if layout:
            print(f"{indent}  Layout: {type(layout).__name__}, constraint: {layout.sizeConstraint()}")
    for child in obj.children():
        if isinstance(child, (QWidget, QLayout)):
            dump_tree(child, depth + 1)

app = QApplication(sys.argv)
win = MainWindow()
dump_tree(win)
