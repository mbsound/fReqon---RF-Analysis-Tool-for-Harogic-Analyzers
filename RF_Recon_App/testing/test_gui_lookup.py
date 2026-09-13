import sys
from PyQt6.QtWidgets import QApplication
from gui import MainWindow
import time

app = QApplication(sys.argv)
win = MainWindow()
win.populate_dtv_table("20148")

print("Active channels dict:", win.active_channels)

table_channels = []
for i in range(win.dtv_table.rowCount()):
    ch_item = win.dtv_table.item(i, 0)
    if ch_item:
        table_channels.append(ch_item.text())

print("Table channels:", table_channels)
