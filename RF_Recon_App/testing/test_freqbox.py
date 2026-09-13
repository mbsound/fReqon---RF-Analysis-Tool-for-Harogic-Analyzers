import sys
from PyQt6.QtWidgets import QApplication, QDoubleSpinBox
from PyQt6.QtCore import Qt

class FreqSpinBox(QDoubleSpinBox):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        # Store internal value in Hz
        self.setRange(0, 30e9) # 0 to 30 GHz
        self.setDecimals(3)
        self.setSingleStep(1e6) # 1 MHz step
        self._internal_val = 0.0

    def valueFromText(self, text):
        text = text.lower().strip()
        text = text.replace(" ", "")
        multiplier = 1e6 # default is MHz
        if text.endswith("ghz"):
            multiplier = 1e9
            text = text[:-3]
        elif text.endswith("mhz"):
            multiplier = 1e6
            text = text[:-3]
        elif text.endswith("khz"):
            multiplier = 1e3
            text = text[:-3]
        elif text.endswith("hz"):
            multiplier = 1
            text = text[:-2]
        
        try:
            val = float(text) * multiplier
            return val
        except ValueError:
            return 0.0

    def textFromValue(self, value):
        if value >= 1e9:
            return f"{value / 1e9:g} GHz"
        elif value >= 1e6:
            return f"{value / 1e6:g} MHz"
        elif value >= 1e3:
            return f"{value / 1e3:g} kHz"
        else:
            return f"{value:g} Hz"
            
    def validate(self, text, pos):
        # Very permissive validation to allow user typing
        return (self.ValidatorState.Acceptable, text, pos)

app = QApplication(sys.argv)
box = FreqSpinBox()
box.setValue(1500e6) # 1.5 GHz
box.show()

# Test text parsing
print(box.valueFromText("1.5 gHz"))
print(box.valueFromText(".5 mHz"))
print(box.valueFromText(".5 kHz"))
print(box.valueFromText("500"))

app.quit()
