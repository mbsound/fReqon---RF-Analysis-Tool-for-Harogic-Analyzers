import sys
from PyQt6.QtWidgets import QApplication
from gui import MainWindow

def main():
    app = QApplication(sys.argv)
    
    # Modern dark style for PyQtGraph
    import pyqtgraph as pg
    pg.setConfigOption('background', 'k')
    pg.setConfigOption('foreground', 'w')
    
    window = MainWindow()
    window.show()
    
    sys.exit(app.exec())

if __name__ == "__main__":
    main()
