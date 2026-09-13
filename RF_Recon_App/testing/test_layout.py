import sys
from PyQt6.QtWidgets import QApplication
from PyQt6.QtCore import QTimer

# mock to run the gui and dump geometry
def run():
    from gui import MainWindow
    app = QApplication(sys.argv)
    window = MainWindow()
    window.show()

    def dump():
        p1 = window.plot_widget.getViewBox().sceneBoundingRect()
        p2 = window.spectrum_channels.getViewBox().sceneBoundingRect()
        print(f"plot_widget ViewBox: x={p1.x()}, width={p1.width()}")
        print(f"spectrum_channels ViewBox: x={p2.x()}, width={p2.width()}")
        app.quit()

    QTimer.singleShot(1000, dump)
    app.exec()

if __name__ == "__main__":
    run()
