"""Dialog for assigning naming metadata to one or more sprite frames."""

from __future__ import annotations

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QComboBox,
    QDialog,
    QDialogButtonBox,
    QFormLayout,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QSpinBox,
    QVBoxLayout,
    QWidget,
)

from sprite_splitter.models.sprite_frame import Direction, Verb


class NamingDialog(QDialog):
    """Modal dialog for assigning part1, part2, verb, direction, and frame number.

    When multiple frames are selected the dialog works in *batch mode*:
    frame_number is auto-incremented starting from 1.
    """

    def __init__(
        self,
        parent: QWidget | None = None,
        *,
        batch: bool = False,
        initial_part1: str = "",
        initial_part2: str = "",
        initial_verb: str = "",
        initial_direction: str = "",
        initial_frame_number: int = 1,
    ):
        super().__init__(parent)
        self.setWindowTitle("Assign Sprite Name")
        self.setMinimumWidth(380)

        layout = QVBoxLayout(self)

        # -- info label for batch mode --
        if batch:
            info = QLabel("Batch mode — frame numbers will auto-increment.")
            info.setStyleSheet("color: #aaa; font-style: italic;")
            layout.addWidget(info)

        # -- form --
        form = QFormLayout()

        self._part1 = QLineEdit(initial_part1)
        self._part1.setPlaceholderText("e.g. hero, goblin")
        form.addRow("Part 1:", self._part1)

        self._part2 = QLineEdit(initial_part2)
        self._part2.setPlaceholderText("e.g. base, armored")
        form.addRow("Part 2:", self._part2)

        # Verb: combo + custom text
        verb_row = QHBoxLayout()
        self._verb_combo = QComboBox()
        self._verb_combo.addItem("(custom)")
        for v in Verb:
            self._verb_combo.addItem(v.value)
        self._verb_custom = QLineEdit()
        self._verb_custom.setPlaceholderText("custom verb…")
        verb_row.addWidget(self._verb_combo, stretch=1)
        verb_row.addWidget(self._verb_custom, stretch=1)
        self._verb_combo.currentTextChanged.connect(self._on_verb_combo_changed)
        # Set initial
        if initial_verb:
            idx = self._verb_combo.findText(initial_verb)
            if idx >= 0:
                self._verb_combo.setCurrentIndex(idx)
            else:
                self._verb_combo.setCurrentIndex(0)
                self._verb_custom.setText(initial_verb)
        form.addRow("Verb:", verb_row)

        # Direction combo
        self._direction_combo = QComboBox()
        self._direction_combo.addItem("")  # empty = unset
        for d in Direction:
            self._direction_combo.addItem(d.value)
        if initial_direction:
            idx = self._direction_combo.findText(initial_direction)
            if idx >= 0:
                self._direction_combo.setCurrentIndex(idx)
        form.addRow("Direction:", self._direction_combo)

        # Frame number (hidden in batch mode)
        if not batch:
            self._frame_num = QSpinBox()
            self._frame_num.setRange(1, 9999)
            self._frame_num.setValue(initial_frame_number)
            form.addRow("Frame #:", self._frame_num)
        else:
            self._frame_num = None

        layout.addLayout(form)

        # -- preview --
        self._preview = QLabel()
        self._preview.setStyleSheet("color: #ccc; font-family: monospace;")
        layout.addWidget(self._preview)
        self._update_preview()
        self._part1.textChanged.connect(self._update_preview)
        self._part2.textChanged.connect(self._update_preview)
        self._verb_combo.currentTextChanged.connect(self._update_preview)
        self._verb_custom.textChanged.connect(self._update_preview)
        self._direction_combo.currentTextChanged.connect(self._update_preview)
        if self._frame_num:
            self._frame_num.valueChanged.connect(self._update_preview)

        # -- buttons --
        btns = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel
        )
        btns.accepted.connect(self.accept)
        btns.rejected.connect(self.reject)
        layout.addWidget(btns)

    # ── result getters ────────────────────────────────────────────────────

    @property
    def part1(self) -> str:
        return self._part1.text().strip().lower().replace(" ", "-")

    @property
    def part2(self) -> str:
        return self._part2.text().strip().lower().replace(" ", "-")

    @property
    def verb_value(self) -> str:
        sel = self._verb_combo.currentText()
        if sel == "(custom)":
            return self._verb_custom.text().strip().lower().replace(" ", "-")
        return sel

    @property
    def verb_enum(self) -> Verb | None:
        try:
            return Verb(self.verb_value)
        except ValueError:
            return None

    @property
    def custom_verb(self) -> str:
        if self.verb_enum is None:
            return self.verb_value
        return ""

    @property
    def direction(self) -> Direction | None:
        txt = self._direction_combo.currentText()
        if not txt:
            return None
        try:
            return Direction(txt)
        except ValueError:
            return None

    @property
    def frame_number(self) -> int:
        if self._frame_num:
            return self._frame_num.value()
        return 1

    # ── helpers ───────────────────────────────────────────────────────────

    def _on_verb_combo_changed(self, text: str):
        self._verb_custom.setEnabled(text == "(custom)")
        if text != "(custom)":
            self._verb_custom.clear()

    def _update_preview(self):
        p1 = self.part1 or "part1"
        p2 = self.part2 or "part2"
        v = self.verb_value or "verb"
        d = self.direction.value if self.direction else "direction"
        n = self.frame_number
        self._preview.setText(f"Preview: {p1}-{p2}-{v}-{d}-{n:03d}.png")
