"""
freq_inputs.py - Precision Numeric SpinBoxes for RF Frequencies & Bandwidth.
Supports human unit inputs (e.g., '470M', '1.5G', '12.5k', '500Hz'),
standard 1-3-10 decade steps for RBW/VBW, and clean monospace formatting.
"""

import math
from PyQt6.QtWidgets import QDoubleSpinBox
from PyQt6.QtGui import QValidator
from PyQt6.QtCore import Qt

class FreqSpinBox(QDoubleSpinBox):
    """
    Frequency spinbox storing values internally in MHz.
    Formats dynamically to GHz / MHz / kHz / Hz based on magnitude.
    """
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setRange(0.001, 20000.0) # 1 kHz to 20 GHz
        self.setDecimals(4)
        self.setSingleStep(1.0)
        self.setSuffix("")
        self.setMinimumWidth(110)
        self.setAlignment(Qt.AlignmentFlag.AlignRight)
        self.setKeyboardTracking(False)

    def valueFromText(self, text: str) -> float:
        text = text.lower().strip().replace(" ", "")
        multiplier = 1.0 # default MHz
        
        if text.endswith("ghz") or text.endswith("g"):
            multiplier = 1000.0
            text = text.rstrip("ghz")
        elif text.endswith("mhz") or text.endswith("m"):
            multiplier = 1.0
            text = text.rstrip("mhz")
        elif text.endswith("khz") or text.endswith("k"):
            multiplier = 1e-3
            text = text.rstrip("khz")
        elif text.endswith("hz"):
            multiplier = 1e-6
            text = text.rstrip("hz")
            
        try:
            return float(text) * multiplier
        except ValueError:
            return self.value()

    def textFromValue(self, value: float) -> str:
        if value >= 1000.0:
            return f"{value / 1000.0:.4g} GHz"
        elif value >= 1.0:
            return f"{value:.4g} MHz"
        elif value >= 1e-3:
            return f"{value * 1000.0:.4g} kHz"
        else:
            return f"{value * 1e6:.4g} Hz"

    def validate(self, text: str, pos: int):
        return (QValidator.State.Acceptable, text, pos)


class BWSpinBox(FreqSpinBox):
    """
    Bandwidth spinbox for RBW / VBW with 1-3-10 decade progression.
    """
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setRange(1e-6, 100.0) # 1 Hz to 100 MHz
        self.setValue(0.001) # 1 kHz
        self.setKeyboardTracking(False)

    def valueFromText(self, text: str) -> float:
        text = text.lower().strip().replace(" ", "")
        multiplier = 1e-3 # Default to kHz for bandwidth if no unit suffix
        
        if text.endswith("ghz") or text.endswith("g"):
            multiplier = 1000.0
            text = text.rstrip("ghz").rstrip("g")
        elif text.endswith("mhz") or text.endswith("m"):
            multiplier = 1.0
            text = text.rstrip("mhz").rstrip("m")
        elif text.endswith("khz") or text.endswith("k"):
            multiplier = 1e-3
            text = text.rstrip("khz").rstrip("k")
        elif text.endswith("hz"):
            multiplier = 1e-6
            text = text.rstrip("hz")
            
        try:
            return float(text) * multiplier
        except ValueError:
            return self.value()

    def textFromValue(self, value: float) -> str:
        val_hz = value * 1e6
        if val_hz >= 1e6:
            return f"{val_hz / 1e6:g} MHz"
        elif val_hz >= 1e3:
            return f"{val_hz / 1e3:g} kHz"
        else:
            return f"{val_hz:g} Hz"

    def stepBy(self, steps: int):
        current_val = self.value()
        if current_val <= 0:
            current_val = 1e-6
            
        if steps > 0:
            for _ in range(steps):
                order = math.floor(math.log10(current_val))
                base = round(current_val / (10**order), 5)
                
                if base < 1.0:
                    base = 1.0
                elif base < 3.0:
                    base = 3.0
                elif base < 10.0:
                    order += 1
                    base = 1.0
                current_val = base * (10**order)
        elif steps < 0:
            for _ in range(-steps):
                order = math.floor(math.log10(current_val))
                base = round(current_val / (10**order), 5)
                
                if base > 3.0:
                    base = 3.0
                elif base > 1.0:
                    base = 1.0
                else:
                    order -= 1
                    base = 3.0
                current_val = base * (10**order)
                
        self.setValue(current_val)
