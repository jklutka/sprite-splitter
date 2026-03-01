"""Settings / detection-parameters panel (shown in a dock or toolbar area)."""

from __future__ import annotations

from PySide6.QtCore import Qt, Signal
from PySide6.QtGui import QColor
from PySide6.QtWidgets import (
    QCheckBox,
    QColorDialog,
    QComboBox,
    QFormLayout,
    QGroupBox,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QSlider,
    QSpinBox,
    QVBoxLayout,
    QWidget,
)

from sprite_splitter.models.sprite_project import DetectionSettings


class SettingsPanel(QWidget):
    """Controls for detection mode, background colour, tolerance, grid dims."""

    detect_requested = Signal()
    settings_changed = Signal()

    def __init__(self, parent=None):
        super().__init__(parent)
        root = QVBoxLayout(self)
        root.setContentsMargins(6, 6, 6, 6)

        # ── Detection mode ────────────────────────────────────────────────
        mode_group = QGroupBox("Detection Mode")
        mode_lay = QVBoxLayout(mode_group)
        self._mode_combo = QComboBox()
        self._mode_combo.addItems(["Auto-detect (contour)", "Grid"])
        self._mode_combo.currentIndexChanged.connect(self._on_mode_changed)
        mode_lay.addWidget(self._mode_combo)
        root.addWidget(mode_group)

        # ── Background colour ─────────────────────────────────────────────
        bg_group = QGroupBox("Background Colour")
        bg_lay = QFormLayout(bg_group)

        color_row = QHBoxLayout()
        self._color_swatch = QLabel()
        self._color_swatch.setFixedSize(28, 28)
        self._set_swatch_color((255, 0, 255))
        color_row.addWidget(self._color_swatch)
        self._btn_pick_color = QPushButton("Pick…")
        self._btn_pick_color.clicked.connect(self._pick_color)
        color_row.addWidget(self._btn_pick_color)
        self._btn_auto_color = QPushButton("Auto")
        color_row.addWidget(self._btn_auto_color)
        bg_lay.addRow("Colour:", color_row)

        self._tolerance_slider = QSlider(Qt.Orientation.Horizontal)
        self._tolerance_slider.setRange(0, 128)
        self._tolerance_slider.setValue(30)
        self._tolerance_label = QLabel("30")
        self._tolerance_slider.valueChanged.connect(
            lambda v: self._tolerance_label.setText(str(v))
        )
        tol_row = QHBoxLayout()
        tol_row.addWidget(self._tolerance_slider, stretch=1)
        tol_row.addWidget(self._tolerance_label)
        bg_lay.addRow("Tolerance:", tol_row)

        root.addWidget(bg_group)

        # ── Grid settings ─────────────────────────────────────────────────
        self._grid_group = QGroupBox("Grid Settings")
        grid_lay = QFormLayout(self._grid_group)
        self._cell_w = QSpinBox()
        self._cell_w.setRange(4, 1024)
        self._cell_w.setValue(32)
        grid_lay.addRow("Cell width:", self._cell_w)
        self._cell_h = QSpinBox()
        self._cell_h.setRange(4, 1024)
        self._cell_h.setValue(32)
        grid_lay.addRow("Cell height:", self._cell_h)
        self._margin = QSpinBox()
        self._margin.setRange(0, 128)
        grid_lay.addRow("Margin:", self._margin)
        self._padding = QSpinBox()
        self._padding.setRange(0, 128)
        grid_lay.addRow("Padding:", self._padding)
        self._auto_grid = QCheckBox("Auto-detect grid size")
        self._auto_grid.setChecked(True)
        grid_lay.addRow(self._auto_grid)
        self._grid_group.setVisible(False)
        root.addWidget(self._grid_group)

        # ── Min area (contour mode) ──────────────────────────────────────
        self._min_area_spin = QSpinBox()
        self._min_area_spin.setRange(1, 10000)
        self._min_area_spin.setValue(16)
        root.addWidget(QLabel("Min sprite area (px²):"))
        root.addWidget(self._min_area_spin)

        # ── Detect button ─────────────────────────────────────────────────
        self._btn_detect = QPushButton("Detect Sprites")
        self._btn_detect.setStyleSheet(
            "QPushButton { background: #2a7; color: white; padding: 8px; "
            "font-weight: bold; border-radius: 4px; }"
        )
        self._btn_detect.clicked.connect(self.detect_requested.emit)
        root.addWidget(self._btn_detect)

        root.addStretch()

        self._bg_color: tuple[int, int, int] = (255, 0, 255)

    # ── public API ────────────────────────────────────────────────────────

    def get_settings(self) -> DetectionSettings:
        return DetectionSettings(
            mode="grid" if self._mode_combo.currentIndex() == 1 else "contour",
            bg_color=self._bg_color,
            tolerance=self._tolerance_slider.value(),
            min_area=self._min_area_spin.value(),
            cell_width=self._cell_w.value(),
            cell_height=self._cell_h.value(),
            margin=self._margin.value(),
            padding=self._padding.value(),
        )

    def set_settings(self, s: DetectionSettings) -> None:
        self._mode_combo.setCurrentIndex(0 if s.mode == "contour" else 1)
        self._bg_color = s.bg_color
        self._set_swatch_color(s.bg_color)
        self._tolerance_slider.setValue(s.tolerance)
        self._min_area_spin.setValue(s.min_area)
        self._cell_w.setValue(s.cell_width)
        self._cell_h.setValue(s.cell_height)
        self._margin.setValue(s.margin)
        self._padding.setValue(s.padding)

    def set_bg_color(self, color: tuple[int, int, int]) -> None:
        self._bg_color = color
        self._set_swatch_color(color)

    @property
    def auto_color_button(self) -> QPushButton:
        """Expose so the main window can connect to auto-detect logic."""
        return self._btn_auto_color

    # ── internals ─────────────────────────────────────────────────────────

    def _set_swatch_color(self, rgb: tuple[int, int, int]) -> None:
        self._color_swatch.setStyleSheet(
            f"background: rgb({rgb[0]},{rgb[1]},{rgb[2]}); "
            f"border: 1px solid #888; border-radius: 3px;"
        )

    def _pick_color(self) -> None:
        initial = QColor(*self._bg_color)
        color = QColorDialog.getColor(initial, self, "Select Background Colour")
        if color.isValid():
            self._bg_color = (color.red(), color.green(), color.blue())
            self._set_swatch_color(self._bg_color)
            self.settings_changed.emit()

    def _on_mode_changed(self, idx: int) -> None:
        self._grid_group.setVisible(idx == 1)
        self.settings_changed.emit()
