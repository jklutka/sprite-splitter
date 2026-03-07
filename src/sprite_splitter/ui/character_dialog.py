"""Dialog for creating or editing a character identity (part1 + part2)."""

from __future__ import annotations

from PySide6.QtWidgets import (
    QDialog,
    QDialogButtonBox,
    QFormLayout,
    QLabel,
    QLineEdit,
    QVBoxLayout,
    QWidget,
)

from sprite_splitter.naming.convention import normalize_name_token


class CharacterDialog(QDialog):
    """Collects the character's entity name (part1) and variant (part2)."""

    def __init__(
        self,
        parent: QWidget | None = None,
        part1: str = "",
        part2: str = "",
    ) -> None:
        super().__init__(parent)
        self.setWindowTitle("New Character")
        self.setMinimumWidth(400)

        layout = QVBoxLayout(self)

        form = QFormLayout()
        form.setFieldGrowthPolicy(QFormLayout.FieldGrowthPolicy.ExpandingFieldsGrow)

        self._part1_edit = QLineEdit(part1)
        self._part1_edit.setPlaceholderText("e.g. hero, goblin, skeleton")
        self._part1_edit.setMinimumHeight(32)
        form.addRow("Entity name (Part 1):", self._part1_edit)

        self._part2_edit = QLineEdit(part2)
        self._part2_edit.setPlaceholderText("e.g. base, armored, red")
        self._part2_edit.setMinimumHeight(32)
        form.addRow("Variant (Part 2):", self._part2_edit)

        layout.addLayout(form)
        layout.addSpacing(12)

        # Live filename preview
        preview_lbl = QLabel("Filename preview:")
        preview_lbl.setStyleSheet("color: #aaa; font-size: 11px;")
        layout.addWidget(preview_lbl)

        self._preview = QLabel()
        self._preview.setStyleSheet(
            "color: #5af; font-size: 13px; font-family: monospace; "
            "padding: 8px; background: #252530; border-radius: 4px;"
        )
        layout.addWidget(self._preview)
        layout.addSpacing(8)

        # OK / Cancel
        self._btns = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel
        )
        self._btns.button(QDialogButtonBox.StandardButton.Ok).setText("Create \u2192")
        self._btns.accepted.connect(self.accept)
        self._btns.rejected.connect(self.reject)
        layout.addWidget(self._btns)

        self._part1_edit.textChanged.connect(self._update)
        self._part2_edit.textChanged.connect(self._update)
        self._update()

    # ── result properties ─────────────────────────────────────────────────

    @property
    def part1(self) -> str:
        return normalize_name_token(self._part1_edit.text())

    @property
    def part2(self) -> str:
        return normalize_name_token(self._part2_edit.text())

    # ── internals ─────────────────────────────────────────────────────────

    def _update(self) -> None:
        p1 = self.part1 or "???"
        p2 = self.part2 or "???"
        self._preview.setText(f"{p1}-{p2}-<verb>-<direction>-001.png")
        ok_btn = self._btns.button(QDialogButtonBox.StandardButton.Ok)
        ok_btn.setEnabled(bool(self.part1) and bool(self.part2))
