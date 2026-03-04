"""8-direction classification panel – drag-drop or click to assign frames.

After sprite detection, this panel displays a compass-style grid of the
eight cardinal/intercardinal directions.  Users can:

* **Drag** frames from the Frames list and **drop** them onto a direction slot.
* **Select** frames in the Frames list and **click** a direction button.
* **Click** a populated direction slot to preview its animation.
"""

from __future__ import annotations

from typing import Optional

import numpy as np
from PySide6.QtCore import Qt, Signal
from PySide6.QtGui import (
    QImage,
    QPixmap,
)
from PySide6.QtWidgets import (
    QComboBox,
    QFormLayout,
    QFrame,
    QGridLayout,
    QLabel,
    QPushButton,
    QSizePolicy,
    QVBoxLayout,
    QWidget,
)

from sprite_splitter.models.sprite_frame import Direction, SpriteFrame, Verb


# ── Constants ────────────────────────────────────────────────────────────────

THUMB_SIZE = 52

# Compass layout positions in a 3×3 grid (row, col)
# Center cell is left empty (or used for an info label).
_COMPASS_POS: dict[Direction, tuple[int, int]] = {
    Direction.NORTHWEST:  (0, 0),
    Direction.NORTH:      (0, 1),
    Direction.NORTHEAST:  (0, 2),
    Direction.WEST:       (1, 0),
    # center = (1, 1)
    Direction.EAST:       (1, 2),
    Direction.SOUTHWEST:  (2, 0),
    Direction.SOUTH:      (2, 1),
    Direction.SOUTHEAST:  (2, 2),
}

_SHORT_LABELS: dict[Direction, str] = {
    Direction.NORTH:     "N",
    Direction.NORTHEAST: "NE",
    Direction.EAST:      "E",
    Direction.SOUTHEAST: "SE",
    Direction.SOUTH:     "S",
    Direction.SOUTHWEST: "SW",
    Direction.WEST:      "W",
    Direction.NORTHWEST: "NW",
}

# MIME type used for frame-id drag payloads
FRAME_DRAG_MIME = "application/x-sprite-frame-ids"


# ── Direction Slot Widget ────────────────────────────────────────────────────

class DirectionSlot(QFrame):
    """A single compass slot representing one direction.

    Accepts drops carrying ``FRAME_DRAG_MIME`` data and emits signals for
    the owning panel to act on.
    """

    clicked = Signal(Direction)
    frames_dropped = Signal(Direction, list)  # Direction, list[int] frame ids

    def __init__(self, direction: Direction, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.direction = direction
        self.setAcceptDrops(True)
        self.setMinimumSize(90, 100)
        self.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)
        self.setFrameShape(QFrame.Shape.Box)
        self._set_idle_style()

        layout = QVBoxLayout(self)
        layout.setContentsMargins(4, 4, 4, 4)
        layout.setSpacing(2)

        # Direction label
        self._label = QLabel(_SHORT_LABELS[direction])
        self._label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self._label.setStyleSheet("font-weight: bold; font-size: 13px; color: #ccc;")
        layout.addWidget(self._label)

        # Thumbnail area
        self._thumb_label = QLabel()
        self._thumb_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self._thumb_label.setMinimumSize(THUMB_SIZE, THUMB_SIZE)
        layout.addWidget(self._thumb_label)

        # Frame count
        self._count_label = QLabel("0")
        self._count_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self._count_label.setStyleSheet("color: #888; font-size: 11px;")
        layout.addWidget(self._count_label)

        self._frame_count = 0
        self._current_pixmap: Optional[QPixmap] = None

    # ── public API ────────────────────────────────────────────────────────

    def set_frame_info(self, count: int, preview_image: Optional[np.ndarray] = None) -> None:
        """Update the slot with the number of assigned frames and an optional thumbnail."""
        self._frame_count = count
        self._count_label.setText(f"{count} frame{'s' if count != 1 else ''}")

        if preview_image is not None and count > 0:
            h, w, ch = preview_image.shape
            bpl = ch * w
            fmt = QImage.Format.Format_RGBA8888 if ch == 4 else QImage.Format.Format_RGB888
            qimg = QImage(preview_image.data, w, h, bpl, fmt).copy()
            pm = QPixmap.fromImage(qimg).scaled(
                THUMB_SIZE, THUMB_SIZE,
                Qt.AspectRatioMode.KeepAspectRatio,
                Qt.TransformationMode.FastTransformation,
            )
            self._thumb_label.setPixmap(pm)
        elif count == 0:
            self._thumb_label.clear()
            self._thumb_label.setText("—")
            self._thumb_label.setStyleSheet("color: #555; font-size: 18px;")

        # Highlight slots that have frames
        if count > 0:
            self._set_populated_style()
        else:
            self._set_idle_style()

    # ── style helpers ─────────────────────────────────────────────────────

    def _set_idle_style(self) -> None:
        self.setStyleSheet(
            "DirectionSlot { background: #2f2f2f; border: 1px solid #444; border-radius: 4px; }"
        )

    def _set_populated_style(self) -> None:
        self.setStyleSheet(
            "DirectionSlot { background: #2a3a2a; border: 1px solid #4a7; border-radius: 4px; }"
        )

    def _set_hover_style(self) -> None:
        self.setStyleSheet(
            "DirectionSlot { background: #2a3a4a; border: 2px solid #5af; border-radius: 4px; }"
        )

    # ── mouse events ──────────────────────────────────────────────────────

    def mousePressEvent(self, event) -> None:
        if event.button() == Qt.MouseButton.LeftButton:
            self.clicked.emit(self.direction)
        super().mousePressEvent(event)

    # ── drag-drop ─────────────────────────────────────────────────────────

    def dragEnterEvent(self, event) -> None:
        if event.mimeData().hasFormat(FRAME_DRAG_MIME):
            event.acceptProposedAction()
            self._set_hover_style()
        else:
            event.ignore()

    def dragLeaveEvent(self, event) -> None:
        if self._frame_count > 0:
            self._set_populated_style()
        else:
            self._set_idle_style()
        super().dragLeaveEvent(event)

    def dropEvent(self, event) -> None:
        if event.mimeData().hasFormat(FRAME_DRAG_MIME):
            data = event.mimeData().data(FRAME_DRAG_MIME).data().decode("utf-8")
            frame_ids = [int(x) for x in data.split(",") if x]
            self.frames_dropped.emit(self.direction, frame_ids)
            event.acceptProposedAction()
        if self._frame_count > 0:
            self._set_populated_style()
        else:
            self._set_idle_style()


# ── Main Direction Panel ─────────────────────────────────────────────────────

class DirectionPanel(QWidget):
    """Compass-grid panel for classifying frames into 8 directions.

    Signals
    -------
    direction_selected(Direction)
        Emitted when user clicks a direction slot (to trigger preview).
    frames_assigned(Direction, list[int])
        Emitted when frames are dropped or button-assigned to a direction.
    """

    direction_selected = Signal(object)     # Direction enum
    frames_assigned = Signal(object, list)  # Direction, list[int] frame_ids

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setMinimumWidth(300)

        root = QVBoxLayout(self)
        root.setContentsMargins(6, 6, 6, 6)
        root.setSpacing(6)

        # ── Header ────────────────────────────────────────────────────────
        header = QLabel("Direction Classification")
        header.setStyleSheet("font-weight: bold; font-size: 13px; color: #ccc;")
        root.addWidget(header)

        info = QLabel("Drag frames here or select frames then click a direction.")
        info.setStyleSheet("color: #888; font-size: 11px; font-style: italic;")
        info.setWordWrap(True)
        root.addWidget(info)

        # ── Verb selector ─────────────────────────────────────────────────
        verb_row = QFormLayout()
        self._verb_combo = QComboBox()
        self._verb_combo.addItem("(all verbs)")
        for v in Verb:
            self._verb_combo.addItem(v.value)
        self._verb_combo.currentTextChanged.connect(self._refresh_slots)
        verb_row.addRow("Filter verb:", self._verb_combo)

        self._sheet_combo = QComboBox()
        self._sheet_combo.addItem("(all sheets)")
        self._sheet_combo.currentTextChanged.connect(self._refresh_slots)
        verb_row.addRow("Filter sheet:", self._sheet_combo)
        root.addLayout(verb_row)

        # ── Compass grid ──────────────────────────────────────────────────
        self._compass_grid = QGridLayout()
        self._compass_grid.setSpacing(4)

        self._slots: dict[Direction, DirectionSlot] = {}
        for direction, (row, col) in _COMPASS_POS.items():
            slot = DirectionSlot(direction)
            slot.clicked.connect(self._on_slot_clicked)
            slot.frames_dropped.connect(self._on_frames_dropped)
            self._compass_grid.addWidget(slot, row, col)
            self._slots[direction] = slot

        # Center info
        center_label = QLabel("⊕")
        center_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        center_label.setStyleSheet("font-size: 24px; color: #555;")
        self._compass_grid.addWidget(center_label, 1, 1)

        root.addLayout(self._compass_grid)

        # ── Quick-assign buttons ──────────────────────────────────────────
        assign_header = QLabel("Quick Assign Selected →")
        assign_header.setStyleSheet("color: #aaa; font-size: 11px; margin-top: 6px;")
        root.addWidget(assign_header)

        quick_grid = QGridLayout()
        quick_grid.setSpacing(3)
        self._quick_btns: dict[Direction, QPushButton] = {}
        for direction, (row, col) in _COMPASS_POS.items():
            btn = QPushButton(_SHORT_LABELS[direction])
            btn.setToolTip(f"Assign selected frames → {direction.value}")
            btn.setFixedSize(56, 32)
            btn.setStyleSheet(
                "QPushButton { background: #3a3a3a; color: #bbb; border: 1px solid #555; "
                "border-radius: 3px; font-weight: bold; }"
                "QPushButton:hover { background: #4a5a6a; color: #fff; }"
            )
            btn.clicked.connect(lambda checked=False, d=direction: self._on_quick_assign(d))
            quick_grid.addWidget(btn, row, col)
            self._quick_btns[direction] = btn

        root.addLayout(quick_grid)

        # ── Summary ───────────────────────────────────────────────────────
        self._summary_label = QLabel("No frames classified yet.")
        self._summary_label.setStyleSheet("color: #888; font-size: 11px; margin-top: 4px;")
        self._summary_label.setWordWrap(True)
        root.addWidget(self._summary_label)

        root.addStretch()

        # ── State ─────────────────────────────────────────────────────────
        self._all_frames: list[SpriteFrame] = []
        self._get_selected_ids_fn = None  # callback set by MainWindow

    # ── public API ────────────────────────────────────────────────────────

    def set_frames(self, frames: list[SpriteFrame]) -> None:
        """Update the panel with the latest project frames."""
        self._all_frames = list(frames)
        self._rebuild_sheet_filter()
        self._refresh_slots()

    def set_selected_ids_callback(self, fn) -> None:
        """Register a callback that returns the currently selected frame IDs."""
        self._get_selected_ids_fn = fn

    # ── internal: refresh slot displays ───────────────────────────────────

    def _refresh_slots(self, _text: str = "") -> None:
        """Rebuild every direction slot from the current frame list."""
        verb_filter = self._verb_combo.currentText()
        filter_all = verb_filter == "(all verbs)"

        sheet_filter = self._sheet_combo.currentText()
        filter_all_sheets = sheet_filter == "(all sheets)"

        visible_frames = [
            f for f in self._all_frames
            if filter_all_sheets or (f.source_sheet_name == sheet_filter)
        ]

        classified = 0
        for direction in Direction:
            matching = [
                f for f in visible_frames
                if f.direction == direction
                and (filter_all or f.effective_verb == verb_filter)
            ]
            preview_img = matching[0].image if matching and matching[0].image is not None else None
            self._slots[direction].set_frame_info(len(matching), preview_img)
            classified += len(matching)

        total = len(visible_frames)
        unclassified = total - sum(
            1 for f in visible_frames if f.direction is not None
        )
        scope = "all sheets" if filter_all_sheets else sheet_filter
        self._summary_label.setText(
            f"{classified} classified · {unclassified} unassigned · {total} total · {scope}"
        )

    def _rebuild_sheet_filter(self) -> None:
        selected = self._sheet_combo.currentText()
        names = sorted({f.source_sheet_name for f in self._all_frames if f.source_sheet_name})

        self._sheet_combo.blockSignals(True)
        self._sheet_combo.clear()
        self._sheet_combo.addItem("(all sheets)")
        for name in names:
            self._sheet_combo.addItem(name)
        self._sheet_combo.blockSignals(False)

        idx = self._sheet_combo.findText(selected)
        self._sheet_combo.setCurrentIndex(idx if idx >= 0 else 0)

    # ── slot callbacks ────────────────────────────────────────────────────

    def _on_slot_clicked(self, direction: Direction) -> None:
        self.direction_selected.emit(direction)

    def _on_frames_dropped(self, direction: Direction, frame_ids: list[int]) -> None:
        self.frames_assigned.emit(direction, frame_ids)

    def _on_quick_assign(self, direction: Direction) -> None:
        """Assign currently selected frames to the given direction."""
        if self._get_selected_ids_fn is None:
            return
        ids = self._get_selected_ids_fn()
        if not ids:
            return
        self.frames_assigned.emit(direction, ids)
