"""
input_chain_dialog.py - Edit antenna/cable/amplifier input chains and choose
which one each analyzer uses.
"""

import copy

import numpy as np
import pyqtgraph as pg
from PyQt6.QtCore import Qt
from PyQt6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QLabel, QPushButton, QComboBox, QListWidget,
    QTableWidget, QTableWidgetItem, QHeaderView, QDoubleSpinBox, QCheckBox, QLineEdit,
    QFileDialog, QInputDialog, QMessageBox, QSplitter, QWidget, QGridLayout,
)

from core.input_chain import (
    InputChain, Element, KINDS, KIND_LABEL, load_response_file,
)

MODE_LABEL = {"flat": "Fixed dB", "cable": "Cable (∝√f)", "table": "Measured table"}
NONE_LABEL = "None (no correction)"


class InputChainDialog(QDialog):
    COLS = ("On", "Type", "Label", "Model", "Value (dB)", "At (MHz)", "")

    def __init__(self, store, slots: dict, parent=None):
        """
        store: InputChainStore (edited on a copy; written back on Save).
        slots: {slot_id: display name} of the analyzers that can be assigned.
        """
        super().__init__(parent)
        self.setWindowTitle("Input Chains (Antenna / Cable / Amplifier)")
        self.resize(1040, 680)
        self.store = store
        self.chains = {n: copy.deepcopy(c) for n, c in store.chains.items()}
        self.assignment = dict(store.assignment)
        self.slots = slots
        self._loading = False

        root = QVBoxLayout(self)
        intro = QLabel(
            "List what sits between the air and each analyzer. fReqon adds the chain's losses and "
            "removes its gains, so levels read as they would at the antenna's output. Include the "
            "antenna's gain to refer levels to a 0 dBi antenna instead.")
        intro.setWordWrap(True)
        intro.setStyleSheet("color: #8b949e;")
        root.addWidget(intro)

        split = QSplitter(Qt.Orientation.Horizontal)
        root.addWidget(split, 1)

        # Chains list
        left = QWidget(); ll = QVBoxLayout(left); ll.setContentsMargins(0, 0, 0, 0)
        ll.addWidget(QLabel("Chains"))
        self.chain_list = QListWidget()
        self.chain_list.currentTextChanged.connect(self._show_chain)
        ll.addWidget(self.chain_list, 1)
        grid = QGridLayout()
        for i, (text, fn) in enumerate((("New", self._new_chain), ("Duplicate", self._dup_chain),
                                        ("Rename", self._rename_chain), ("Delete", self._delete_chain))):
            b = QPushButton(text); b.clicked.connect(fn); grid.addWidget(b, i // 2, i % 2)
        ll.addLayout(grid)
        split.addWidget(left)

        # Chain editor
        right = QWidget(); rl = QVBoxLayout(right); rl.setContentsMargins(0, 0, 0, 0)
        self.table = QTableWidget(0, len(self.COLS))
        self.table.setHorizontalHeaderLabels(self.COLS)
        hh = self.table.horizontalHeader()
        hh.setSectionResizeMode(QHeaderView.ResizeMode.ResizeToContents)
        hh.setSectionResizeMode(2, QHeaderView.ResizeMode.Stretch)
        self.table.verticalHeader().setVisible(False)
        self.table.setMinimumHeight(190)
        rl.addWidget(self.table, 2)
        er = QHBoxLayout()
        for text, fn in (("Add antenna", lambda: self._add("antenna")), ("Add cable", lambda: self._add("cable")),
                         ("Add amplifier", lambda: self._add("amplifier")), ("Add other", lambda: self._add("attenuator")),
                         ("Remove", self._remove_element), ("▲", lambda: self._move(-1)), ("▼", lambda: self._move(1))):
            b = QPushButton(text); b.clicked.connect(fn); er.addWidget(b)
        er.addStretch()
        rl.addLayout(er)
        self.include_ant_cb = QCheckBox("Include antenna gain (refer levels to a 0 dBi antenna)")
        self.include_ant_cb.toggled.connect(self._on_include_antenna)
        rl.addWidget(self.include_ant_cb)

        self.plot = pg.PlotWidget()
        self.plot.setMinimumHeight(150)
        self.plot.setMaximumHeight(210)
        self.plot.setLabel("left", "Correction", units="dB")
        self.plot.setLabel("bottom", "Frequency (MHz)")
        self.plot.showGrid(x=True, y=True, alpha=0.25)
        self.curve = self.plot.plot(pen=pg.mkPen("#38bdf8", width=2))
        self.plot.setXRange(30, 2500)
        rl.addWidget(self.plot)
        self.summary_lbl = QLabel("")
        self.summary_lbl.setStyleSheet("color: #8b949e;")
        rl.addWidget(self.summary_lbl)
        split.addWidget(right)
        left.setMaximumWidth(240)
        split.setSizes([200, 900])

        # Assignment
        btns = QHBoxLayout()
        btns.addWidget(QLabel("Use on"))
        self.slot_combos = {}
        for sid, label in slots.items():
            cb = QComboBox(); cb.setMinimumWidth(170)
            btns.addWidget(QLabel(f"  {label}:")); btns.addWidget(cb)
            self.slot_combos[sid] = cb
        btns.addStretch()
        cancel = QPushButton("Cancel"); cancel.clicked.connect(self.reject)
        save = QPushButton("Save && Apply"); save.setObjectName("primaryActionBtn"); save.clicked.connect(self._save)
        btns.addWidget(cancel); btns.addWidget(save)
        root.addLayout(btns)

        self._refresh_lists()
        if self.chain_list.count():
            self.chain_list.setCurrentRow(0)
        else:
            self._show_chain("")

    # --- chains ---
    def _refresh_lists(self, select=None):
        cur = select or (self.chain_list.currentItem().text() if self.chain_list.currentItem() else None)
        for sid, cb in self.slot_combos.items():   # keep unsaved choices across refreshes
            if cb.count():
                t = cb.currentText()
                if t in self.chains:
                    self.assignment[sid] = t
                elif t == NONE_LABEL:
                    self.assignment.pop(sid, None)
        self.chain_list.blockSignals(True)
        self.chain_list.clear()
        self.chain_list.addItems(sorted(self.chains))
        self.chain_list.blockSignals(False)
        for sid, cb in self.slot_combos.items():
            want = self.assignment.get(sid, NONE_LABEL)
            cb.blockSignals(True); cb.clear(); cb.addItem(NONE_LABEL); cb.addItems(sorted(self.chains))
            i = cb.findText(want); cb.setCurrentIndex(max(i, 0)); cb.blockSignals(False)
        if cur in self.chains:
            items = self.chain_list.findItems(cur, Qt.MatchFlag.MatchExactly)
            if items:
                self.chain_list.setCurrentItem(items[0])
        if cur not in self.chains:
            self._show_chain(self.chain_list.currentItem().text() if self.chain_list.currentItem() else "")

    def _unique(self, base):
        name, i = base, 2
        while name in self.chains:
            name = f"{base} {i}"; i += 1
        return name

    def _new_chain(self):
        name, ok = QInputDialog.getText(self, "New input chain", "Name (e.g. 'Stage left paddle + 50 ft LMR-400'):")
        if ok and name.strip():
            name = self._unique(name.strip())
            self.chains[name] = InputChain(name, [Element("antenna", "Antenna", "flat", 0.0),
                                                  Element("cable", "Coax", "cable", 0.0, 600.0)])
            self._refresh_lists(select=name)

    def _dup_chain(self):
        c = self._current()
        if c:
            name = self._unique(c.name + " copy")
            self.chains[name] = copy.deepcopy(c); self.chains[name].name = name
            self._refresh_lists(select=name)

    def _rename_chain(self):
        c = self._current()
        if not c:
            return
        name, ok = QInputDialog.getText(self, "Rename input chain", "Name:", text=c.name)
        name = name.strip()
        if ok and name and name != c.name:
            name = self._unique(name)
            old = c.name
            self.chains[name] = self.chains.pop(old); self.chains[name].name = name
            self.assignment = {k: (name if v == old else v) for k, v in self.assignment.items()}
            self._refresh_lists(select=name)

    def _delete_chain(self):
        c = self._current()
        if c:
            del self.chains[c.name]
            self.assignment = {k: v for k, v in self.assignment.items() if v != c.name}
            self._refresh_lists()
            if self.chain_list.count():
                self.chain_list.setCurrentRow(0)
            else:
                self._show_chain("")

    def _current(self):
        it = self.chain_list.currentItem()
        return self.chains.get(it.text()) if it else None

    # --- elements ---
    def _show_chain(self, name):
        c = self.chains.get(name)
        self._loading = True
        self.table.setRowCount(0)
        self.include_ant_cb.setEnabled(c is not None)
        self.include_ant_cb.setChecked(bool(c and c.include_antenna))
        if c:
            for e in c.elements:
                self._append_row(e)
        self._loading = False
        self._update_preview()

    def _append_row(self, e: Element):
        r = self.table.rowCount()
        self.table.insertRow(r)
        on = QCheckBox(); on.setChecked(e.enabled)
        on.toggled.connect(lambda v, e=e: self._set(e, "enabled", v))
        self.table.setCellWidget(r, 0, on)

        kind = QComboBox()
        for k in KINDS:
            kind.addItem(KIND_LABEL[k], k)
        kind.setCurrentIndex(KINDS.index(e.kind) if e.kind in KINDS else len(KINDS) - 1)
        kind.currentIndexChanged.connect(lambda i, e=e, w=kind: self._set(e, "kind", w.currentData()))
        self.table.setCellWidget(r, 1, kind)

        lbl = QLineEdit(e.label); lbl.setPlaceholderText("Make / model / length"); lbl.setMinimumWidth(140)
        lbl.editingFinished.connect(lambda e=e, w=lbl: self._set(e, "label", w.text().strip()))
        self.table.setCellWidget(r, 2, lbl)

        mode = QComboBox()
        for m, t in MODE_LABEL.items():
            mode.addItem(t, m)
        mode.setCurrentIndex(list(MODE_LABEL).index(e.mode) if e.mode in MODE_LABEL else 0)
        mode.currentIndexChanged.connect(lambda i, e=e, w=mode: self._set_mode(e, w.currentData()))
        self.table.setCellWidget(r, 3, mode)

        val = QDoubleSpinBox(); val.setRange(-80, 80); val.setDecimals(2); val.setSingleStep(0.5)
        val.setValue(e.gain_db)
        val.setToolTip("Fixed dB: + for gain (antenna dBi, amplifier), − for loss (attenuator, splitter).\n"
                       "Cable: the loss at the frequency to the right, as a positive number.")
        val.valueChanged.connect(lambda v, e=e: self._set(e, "gain_db", v))
        self.table.setCellWidget(r, 4, val)

        ref = QDoubleSpinBox(); ref.setRange(1, 9500); ref.setDecimals(0); ref.setValue(e.ref_mhz)
        ref.valueChanged.connect(lambda v, e=e: self._set(e, "ref_mhz", v))
        self.table.setCellWidget(r, 5, ref)

        imp = QPushButton("Import…")
        imp.setToolTip("Measured response: CSV of frequency and dB, or a Harogic *_ampcomp.txt file")
        imp.clicked.connect(lambda _=False, e=e: self._import_table(e))
        self.table.setCellWidget(r, 6, imp)
        self._sync_row_enabled(r, e)

    def _sync_row_enabled(self, r, e):
        self.table.cellWidget(r, 4).setEnabled(e.mode != "table")
        self.table.cellWidget(r, 5).setEnabled(e.mode == "cable")
        self.table.cellWidget(r, 6).setEnabled(e.mode == "table")
        if e.mode == "table":
            self.table.cellWidget(r, 6).setText(f"{len(e.table)} pts…" if e.table else "Import…")

    def _row_of(self, e):
        c = self._current()
        return c.elements.index(e) if c and e in c.elements else -1

    def _set(self, e, attr, v):
        if self._loading:
            return
        setattr(e, attr, v)
        self._update_preview()

    def _set_mode(self, e, mode):
        if self._loading:
            return
        e.mode = mode
        if mode == "cable":
            e.gain_db = abs(e.gain_db)
        r = self._row_of(e)
        if r >= 0:
            self.table.cellWidget(r, 4).setValue(e.gain_db)
            self._sync_row_enabled(r, e)
        if mode == "table" and not e.table:
            self._import_table(e)
        self._update_preview()

    def _import_table(self, e):
        fn, _ = QFileDialog.getOpenFileName(self, "Import frequency response", "",
                                            "Response files (*.csv *.txt);;All files (*)")
        if not fn:
            return
        try:
            pts = load_response_file(fn)
        except (OSError, ValueError) as ex:
            QMessageBox.warning(self, "Import failed", f"Could not read {fn}:\n{ex}")
            return
        vals = [v for _, v in pts]
        # Ask what the numbers mean: measurements are quoted either way round
        if e.kind in ("cable", "attenuator", "filter", "splitter") and all(v >= 0 for v in vals):
            default = 1   # positive numbers for a passive part are almost always loss
        else:
            default = 0
        choice, ok = QInputDialog.getItem(
            self, "Table values",
            f"{len(pts)} points, {pts[0][0] / 1e6:g}–{pts[-1][0] / 1e6:g} MHz, "
            f"{min(vals):+.1f} to {max(vals):+.1f} dB.\nThe values are:",
            ["Gain (+ means the signal gets stronger)", "Loss (+ means the signal gets weaker)"],
            default, False)
        if not ok:
            return
        sign = -1.0 if choice.startswith("Loss") else 1.0
        e.table = [(f, sign * v) for f, v in pts]
        e.source = fn
        e.mode = "table"
        self._show_chain(self._current().name)

    def _add(self, kind):
        c = self._current()
        if not c:
            self._new_chain(); c = self._current()
            if not c:
                return
        defaults = {"antenna": Element("antenna", "Antenna", "flat", 0.0),
                    "cable": Element("cable", "Coax", "cable", 0.0, 600.0),
                    "amplifier": Element("amplifier", "Amplifier", "flat", 0.0)}
        c.elements.append(defaults.get(kind, Element(kind, "", "flat", 0.0)))
        self._show_chain(c.name)

    def _remove_element(self):
        c = self._current(); r = self.table.currentRow()
        if c and 0 <= r < len(c.elements):
            del c.elements[r]
            self._show_chain(c.name)

    def _move(self, d):
        c = self._current(); r = self.table.currentRow()
        if c and 0 <= r < len(c.elements) and 0 <= r + d < len(c.elements):
            c.elements[r], c.elements[r + d] = c.elements[r + d], c.elements[r]
            self._show_chain(c.name)
            self.table.setCurrentCell(r + d, 2)

    def _on_include_antenna(self, v):
        c = self._current()
        if c and not self._loading:
            c.include_antenna = v
            self._update_preview()

    def _update_preview(self):
        c = self._current()
        if not c:
            self.curve.setData([], [])
            self.summary_lbl.setText("Create a chain to describe an antenna system.")
            return
        f = np.linspace(30e6, 2500e6, 600)
        self.curve.setData(f / 1e6, c.correction(f))
        warn = ""
        if any(e.enabled and e.mode == "table" and not e.table for e in c.elements):
            warn = "  ⚠ A table element has no data yet."
        self.summary_lbl.setText(f"Correction added to readings: {c.summary()}.{warn}")

    def _save(self):
        for sid, cb in self.slot_combos.items():
            t = cb.currentText()
            if t == NONE_LABEL or t not in self.chains:
                self.assignment.pop(sid, None)
            else:
                self.assignment[sid] = t
        self.store.chains = self.chains
        self.store.assignment = self.assignment
        self.store.save()
        self.accept()
