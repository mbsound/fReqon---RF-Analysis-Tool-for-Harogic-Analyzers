"""
combo_popups.py - Drop-down lists as wide as their longest entry.

A combo box's list opens at the width of the combo itself. Where the combo is squeezed (a
table cell, a crowded bar) its entries are cut off: "GNS", "Man". This filter, installed once
on the application, widens any combo's list to fit its entries as it opens.
"""

from PyQt6.QtCore import QEvent, QObject
from PyQt6.QtWidgets import QComboBox

LIST_EXTRA_PX = 44      # the tick mark, the item padding and the frame


def fit_list(combo: QComboBox) -> int:
    """Give a combo's list the width its longest entry needs; returns that width."""
    view = combo.view()
    fm = view.fontMetrics()
    widest = max((fm.horizontalAdvance(combo.itemText(i)) for i in range(combo.count())), default=0)
    width = widest + LIST_EXTRA_PX
    if view.minimumWidth() < width:
        view.setMinimumWidth(width)
    return width


class ComboPopupFitter(QObject):
    """Application event filter: fits a combo's list the moment before it is shown."""

    def eventFilter(self, obj, event):
        # The press (or key) that opens the list reaches the combo first
        if isinstance(obj, QComboBox) and event.type() in (QEvent.Type.MouseButtonPress, QEvent.Type.KeyPress):
            try:
                fit_list(obj)
            except RuntimeError:
                pass                    # the combo is being deleted
        return False


def install(app) -> ComboPopupFitter:
    fitter = ComboPopupFitter(app)
    app.installEventFilter(fitter)
    return fitter
