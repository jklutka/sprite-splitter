"""Export dialog – choose output directory and options before exporting."""

from __future__ import annotations

from pathlib import Path

from PySide6.QtWidgets import (
    QCheckBox,
    QDialog,
    QDialogButtonBox,
    QFileDialog,
    QFormLayout,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QPushButton,
    QVBoxLayout,
    QWidget,
)


class ExportDialog(QDialog):
    """Modal dialog that collects export preferences."""

    def __init__(self, parent: QWidget | None = None, default_dir: str = ""):
        super().__init__(parent)
        self.setWindowTitle("Export Sprites")
        self.setMinimumWidth(480)

        layout = QVBoxLayout(self)

        form = QFormLayout()

        # Output directory
        dir_row = QHBoxLayout()
        self._dir_edit = QLineEdit(default_dir)
        self._btn_browse = QPushButton("Browse…")
        self._btn_browse.clicked.connect(self._browse)
        dir_row.addWidget(self._dir_edit, stretch=1)
        dir_row.addWidget(self._btn_browse)
        form.addRow("Output folder:", dir_row)

        # Options
        self._use_folders = QCheckBox("Organise into sub-folders (part1/part2/verb/)")
        form.addRow(self._use_folders)

        self._export_manifest = QCheckBox("Generate manifest.json")
        self._export_manifest.setChecked(True)
        form.addRow(self._export_manifest)

        self._only_named = QCheckBox("Export only fully-named frames")
        self._only_named.setChecked(True)
        form.addRow(self._only_named)

        layout.addLayout(form)

        # Summary
        self._summary = QLabel("")
        self._summary.setStyleSheet("color: #aaa;")
        layout.addWidget(self._summary)

        # Buttons
        btns = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel
        )
        btns.accepted.connect(self.accept)
        btns.rejected.connect(self.reject)
        layout.addWidget(btns)

    # ── result getters ────────────────────────────────────────────────────

    @property
    def output_dir(self) -> Path:
        return Path(self._dir_edit.text())

    @property
    def use_folders(self) -> bool:
        return self._use_folders.isChecked()

    @property
    def export_manifest(self) -> bool:
        return self._export_manifest.isChecked()

    @property
    def only_named(self) -> bool:
        return self._only_named.isChecked()

    # ── helpers ───────────────────────────────────────────────────────────

    def set_frame_count(self, total: int, named: int) -> None:
        self._summary.setText(f"{named} of {total} frames fully named.")

    def _browse(self) -> None:
        d = QFileDialog.getExistingDirectory(self, "Select Output Folder")
        if d:
            self._dir_edit.setText(d)
