from PyQt6.QtCore import QObject, pyqtSignal
class TestObj(QObject):
    sig = pyqtSignal(int, int)
def on_sig(model, uid):
    print("Received uid:", uid)
    print("Received hex:", f"{uid:016x}")
obj = TestObj()
obj.sig.connect(on_sig)
obj.sig.emit(66, 0x5230500d00220016)
