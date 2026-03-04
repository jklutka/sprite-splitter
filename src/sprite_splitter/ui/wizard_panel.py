"""Three-step workflow wizard shown after sprite detection.

Step 1 – **Review**:   Thumbnail grid with checkboxes to accept / reject
                        false-positive detections.
Step 2 – **Identity**: Fill *part1* (entity name) and *part2* (variant) once.
Step 3 – **Sort**:     Pick a verb, select unassigned frames, click a
                        compass direction to assign.  Frames can be reused
                        multiple times in a sequence.
"""

from __future__ import annotations

from typing import Optional

import numpy as np
from PySide6.QtCore import Qt, Signal, QSize
from PySide6.QtGui import QColor, QIcon, QImage, QPixmap
from PySide6.QtWidgets import (
    QAbstractItemView,
    QCheckBox,
    QComboBox,
    QFrame,
    QGridLayout,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QListWidget,
    QListWidgetItem,
    QPushButton,
    QScrollArea,
    QStackedWidget,
    QVBoxLayout,
    QWidget,
)

from sprite_splitter.models.sprite_frame import Direction, SpriteFrame, Verb
from sprite_splitter.naming.convention import normalize_name_token


# ── Constants ────────────────────────────────────────────────────────────────

THUMB = 64

_SHORT: dict[Direction, str] = {
    Direction.NORTH: "N",
    Direction.NORTHEAST: "NE",
    Direction.EAST: "E",
    Direction.SOUTHEAST: "SE",
    Direction.SOUTH: "S",
    Direction.SOUTHWEST: "SW",
    Direction.WEST: "W",
    Direction.NORTHWEST: "NW",
}

_COMPASS_POS: dict[Direction, tuple[int, int]] = {
    Direction.NORTHWEST:  (0, 0),
    Direction.NORTH:      (0, 1),
    Direction.NORTHEAST:  (0, 2),
    Direction.WEST:       (1, 0),
    Direction.EAST:       (1, 2),
    Direction.SOUTHWEST:  (2, 0),
    Direction.SOUTH:      (2, 1),
    Direction.SOUTHEAST:  (2, 2),
}


# ── Thumbnail helper ─────────────────────────────────────────────────────────

def _thumb_pixmap(arr: Optional[np.ndarray], size: int = THUMB) -> QPixmap:
    if arr is None:
        pm = QPixmap(size, size)
        pm.fill(QColor(60, 60, 60))
        return pm
    h, w, ch = arr.shape
    fmt = QImage.Format.Format_RGBA8888 if ch == 4 else QImage.Format.Format_RGB888
    qimg = QImage(arr.data, w, h, ch * w, fmt).copy()
    pm = QPixmap.fromImage(qimg)
    return pm.scaled(
        size, size,
        Qt.AspectRatioMode.KeepAspectRatio,
        Qt.TransformationMode.SmoothTransformation,
    )


# ══════════════════════════════════════════════════════════════════════════════
# Step bar
# ══════════════════════════════════════════════════════════════════════════════

class _StepBar(QWidget):
    """Horizontal step indicator at the top of the wizard."""

    def __init__(self, labels: list[str], parent: QWidget | None = None) -> None:
        super().__init__(parent)
        lay = QHBoxLayout(self)
        lay.setContentsMargins(16, 10, 16, 10)
        self._items: list[QLabel] = []
        for i, text in enumerate(labels):
            if i > 0:
                sep = QLabel("━━━")
                sep.setAlignment(Qt.AlignmentFlag.AlignCenter)
                sep.setStyleSheet("color: #444; font-size: 11px;")
                lay.addWidget(sep)
            lbl = QLabel(text)
            lbl.setAlignment(Qt.AlignmentFlag.AlignCenter)
            lay.addWidget(lbl)
            self._items.append(lbl)

    def set_active(self, index: int) -> None:
        for i, lbl in enumerate(self._items):
            if i < index:
                lbl.setStyleSheet(
                    "color: #6c6; font-size: 12px; padding: 5px 12px; "
                    "border-radius: 12px; background: #253025;"
                )
            elif i == index:
                lbl.setStyleSheet(
                    "color: #fff; font-size: 12px; font-weight: bold; "
                    "padding: 5px 12px; border-radius: 12px; background: #3a6ea5;"
                )
            else:
                lbl.setStyleSheet(
                    "color: #666; font-size: 12px; padding: 5px 12px;"
                )


# ══════════════════════════════════════════════════════════════════════════════
# Page 1 – Review Detected Sprites
# ══════════════════════════════════════════════════════════════════════════════

class _ReviewPage(QWidget):
    """Scrollable thumbnail grid with accept / reject checkboxes."""

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        root = QVBoxLayout(self)
        root.setContentsMargins(20, 16, 20, 8)

        title = QLabel("Review Detected Sprites")
        title.setStyleSheet("font-size: 18px; font-weight: bold; color: #eee;")
        root.addWidget(title)

        desc = QLabel(
            "Deselect any false positives or sprites you don't want to export."
        )
        desc.setStyleSheet("color: #999; font-size: 12px; margin-bottom: 8px;")
        desc.setWordWrap(True)
        root.addWidget(desc)

        # Toolbar
        bar = QHBoxLayout()
        self._btn_all = QPushButton("Select All")
        self._btn_all.clicked.connect(self._select_all)
        self._btn_none = QPushButton("Deselect All")
        self._btn_none.clicked.connect(self._deselect_all)
        self._count_lbl = QLabel("")
        self._count_lbl.setStyleSheet("color: #aaa; font-size: 12px;")
        bar.addWidget(self._btn_all)
        bar.addWidget(self._btn_none)
        bar.addStretch()
        bar.addWidget(self._count_lbl)
        root.addLayout(bar)

        # Scrollable grid
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setStyleSheet("QScrollArea { border: none; background: transparent; }")
        self._grid_w = QWidget()
        self._grid_lay = QGridLayout(self._grid_w)
        self._grid_lay.setSpacing(8)
        scroll.setWidget(self._grid_w)
        root.addWidget(scroll, stretch=1)

        self._checks: list[tuple[QCheckBox, int]] = []  # (checkbox, frame_id)

    # ── public API ────────────────────────────────────────────────────────

    def set_frames(self, frames: list[SpriteFrame]) -> None:
        # Clear
        while self._grid_lay.count():
            item = self._grid_lay.takeAt(0)
            w = item.widget()
            if w:
                w.deleteLater()
        self._checks.clear()

        cols = 8  # fixed columns for consistent layout
        for i, frame in enumerate(frames):
            cell = QFrame()
            cell.setStyleSheet(
                "QFrame { background: #333; border: 1px solid #444; border-radius: 4px; }"
            )
            cl = QVBoxLayout(cell)
            cl.setContentsMargins(6, 6, 6, 6)
            cl.setSpacing(3)

            # Thumbnail
            t = QLabel()
            t.setPixmap(_thumb_pixmap(frame.image))
            t.setAlignment(Qt.AlignmentFlag.AlignCenter)
            cl.addWidget(t)

            # Checkbox
            sheet = frame.source_sheet_name or "sheet"
            cb = QCheckBox(f"#{frame.id} · {sheet}")
            cb.setChecked(True)
            cb.setStyleSheet("color: #bbb; font-size: 10px;")
            cb.stateChanged.connect(self._update_count)
            cl.addWidget(cb, alignment=Qt.AlignmentFlag.AlignCenter)

            # Size
            sl = QLabel(f"{frame.bbox.w}×{frame.bbox.h}")
            sl.setStyleSheet("color: #666; font-size: 9px;")
            sl.setAlignment(Qt.AlignmentFlag.AlignCenter)
            cl.addWidget(sl)

            self._grid_lay.addWidget(cell, i // cols, i % cols)
            self._checks.append((cb, frame.id))

        self._update_count()

    def accepted_ids(self) -> list[int]:
        return [fid for cb, fid in self._checks if cb.isChecked()]

    def rejected_ids(self) -> list[int]:
        return [fid for cb, fid in self._checks if not cb.isChecked()]

    # ── internals ─────────────────────────────────────────────────────────

    def _select_all(self) -> None:
        for cb, _ in self._checks:
            cb.setChecked(True)

    def _deselect_all(self) -> None:
        for cb, _ in self._checks:
            cb.setChecked(False)

    def _update_count(self, _: int = 0) -> None:
        n = sum(1 for cb, _ in self._checks if cb.isChecked())
        t = len(self._checks)
        self._count_lbl.setText(f"{n} of {t} sprites selected")


# ══════════════════════════════════════════════════════════════════════════════
# Page 2 – Define Identity
# ══════════════════════════════════════════════════════════════════════════════

class _IdentityPage(QWidget):
    """Part 1 + Part 2 text inputs, filled once for all sprites."""

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        root = QVBoxLayout(self)
        root.setContentsMargins(20, 16, 20, 8)

        title = QLabel("Define Sprite Identity")
        title.setStyleSheet("font-size: 18px; font-weight: bold; color: #eee;")
        root.addWidget(title)

        desc = QLabel(
            "These values will be applied to every frame as you assign "
            "directions in the next step."
        )
        desc.setStyleSheet("color: #999; font-size: 12px; margin-bottom: 20px;")
        desc.setWordWrap(True)
        root.addWidget(desc)

        # Part 1
        p1_lbl = QLabel("Part 1 — Entity Name")
        p1_lbl.setStyleSheet("color: #ccc; font-weight: bold; font-size: 13px;")
        root.addWidget(p1_lbl)
        p1_hint = QLabel("e.g.  hero, goblin, skeleton, npc")
        p1_hint.setStyleSheet("color: #777; font-size: 11px; font-style: italic;")
        root.addWidget(p1_hint)
        self._part1 = QLineEdit()
        self._part1.setPlaceholderText("hero")
        self._part1.setMinimumHeight(34)
        self._part1.setStyleSheet("font-size: 14px; padding: 6px;")
        root.addWidget(self._part1)
        root.addSpacing(16)

        # Part 2
        p2_lbl = QLabel("Part 2 — Variant / Style")
        p2_lbl.setStyleSheet("color: #ccc; font-weight: bold; font-size: 13px;")
        root.addWidget(p2_lbl)
        p2_hint = QLabel("e.g.  base, armored, red, alt1")
        p2_hint.setStyleSheet("color: #777; font-size: 11px; font-style: italic;")
        root.addWidget(p2_hint)
        self._part2 = QLineEdit()
        self._part2.setPlaceholderText("base")
        self._part2.setMinimumHeight(34)
        self._part2.setStyleSheet("font-size: 14px; padding: 6px;")
        root.addWidget(self._part2)

        # Preview
        root.addSpacing(24)
        plbl = QLabel("Filename preview:")
        plbl.setStyleSheet("color: #aaa; font-size: 11px;")
        root.addWidget(plbl)
        self._preview = QLabel("???-???-<verb>-<direction>-001.png")
        self._preview.setStyleSheet(
            "color: #5af; font-size: 14px; font-family: monospace; "
            "padding: 8px; background: #252530; border-radius: 4px;"
        )
        root.addWidget(self._preview)

        self._part1.textChanged.connect(self._update_preview)
        self._part2.textChanged.connect(self._update_preview)

        root.addStretch()

    # ── public ────────────────────────────────────────────────────────────

    @property
    def part1(self) -> str:
        return normalize_name_token(self._part1.text())

    @property
    def part2(self) -> str:
        return normalize_name_token(self._part2.text())

    # ── internals ─────────────────────────────────────────────────────────

    def _update_preview(self) -> None:
        p1 = self.part1 or "???"
        p2 = self.part2 or "???"
        self._preview.setText(f"{p1}-{p2}-<verb>-<direction>-001.png")


# ══════════════════════════════════════════════════════════════════════════════
# Page 3 – Sort into Frame Sequences
# ══════════════════════════════════════════════════════════════════════════════

class _SortPage(QWidget):
    """Verb selector  +  available frame list  +  8-direction compass buttons."""

    frames_assigned = Signal(object, list)  # Direction, list[int] frame_ids

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        root = QVBoxLayout(self)
        root.setContentsMargins(20, 16, 20, 8)

        title = QLabel("Sort into Frame Sequences")
        title.setStyleSheet("font-size: 18px; font-weight: bold; color: #eee;")
        root.addWidget(title)

        desc = QLabel(
            "Select frames, pick a verb, then click a compass "
            "direction to assign. Assigned frames stay available so you can "
            "reuse the same source image multiple times in a sequence."
        )
        desc.setStyleSheet("color: #999; font-size: 12px; margin-bottom: 8px;")
        desc.setWordWrap(True)
        root.addWidget(desc)

        # ── verb row ──────────────────────────────────────────────────────
        verb_row = QHBoxLayout()

        vlbl = QLabel("Verb:")
        vlbl.setStyleSheet("color: #ccc; font-weight: bold;")
        verb_row.addWidget(vlbl)

        self._verb_combo = QComboBox()
        for v in Verb:
            self._verb_combo.addItem(v.value)
        self._verb_combo.setMinimumWidth(140)
        verb_row.addWidget(self._verb_combo)

        self._custom_verb = QLineEdit()
        self._custom_verb.setPlaceholderText("custom verb…")
        self._custom_verb.setMinimumWidth(120)
        self._custom_verb.setVisible(False)
        verb_row.addWidget(self._custom_verb)

        # Add "(custom)" entry
        self._verb_combo.addItem("(custom)")
        self._verb_combo.currentTextChanged.connect(self._on_verb_changed)

        verb_row.addStretch()

        self._identity_lbl = QLabel("")
        self._identity_lbl.setStyleSheet(
            "color: #6c6; font-size: 12px; font-weight: bold;"
        )
        verb_row.addWidget(self._identity_lbl)

        root.addLayout(verb_row)

        # ── body: frame list + compass ────────────────────────────────────
        body = QHBoxLayout()

        # Left: available frames list
        left = QVBoxLayout()
        lh = QLabel("Available Frames")
        lh.setStyleSheet("color: #aaa; font-size: 12px; font-weight: bold;")
        left.addWidget(lh)
        self._list_title = lh

        self._frame_list = QListWidget()
        self._frame_list.setIconSize(QSize(48, 48))
        self._frame_list.setSelectionMode(
            QAbstractItemView.SelectionMode.ExtendedSelection
        )
        self._frame_list.setStyleSheet("QListWidget { background: #2a2a2a; }")
        left.addWidget(self._frame_list, stretch=1)

        sel_bar = QHBoxLayout()
        btn_sel_all = QPushButton("Select All")
        btn_sel_all.setFixedHeight(26)
        btn_sel_all.clicked.connect(self._frame_list.selectAll)
        sel_bar.addWidget(btn_sel_all)
        self._unassigned_lbl = QLabel("0 unassigned")
        self._unassigned_lbl.setStyleSheet("color: #888; font-size: 11px;")
        sel_bar.addStretch()
        sel_bar.addWidget(self._unassigned_lbl)
        left.addLayout(sel_bar)

        body.addLayout(left, stretch=1)

        # Right: compass direction buttons
        right = QVBoxLayout()
        rh = QLabel("Click Direction to Assign")
        rh.setAlignment(Qt.AlignmentFlag.AlignCenter)
        rh.setStyleSheet(
            "color: #aaa; font-size: 12px; font-weight: bold; margin-bottom: 4px;"
        )
        right.addWidget(rh)

        grid = QGridLayout()
        grid.setSpacing(5)
        self._dir_btns: dict[Direction, QPushButton] = {}
        for d, (r, c) in _COMPASS_POS.items():
            btn = QPushButton(_SHORT[d])
            btn.setFixedSize(72, 52)
            btn.setToolTip(f"Assign selected → {d.value}")
            btn.clicked.connect(lambda checked=False, dd=d: self._on_assign(dd))
            grid.addWidget(btn, r, c)
            self._dir_btns[d] = btn

        center = QLabel("⊕")
        center.setAlignment(Qt.AlignmentFlag.AlignCenter)
        center.setStyleSheet("font-size: 22px; color: #555;")
        grid.addWidget(center, 1, 1)

        right.addLayout(grid)

        # Assigned summary
        right.addSpacing(8)
        self._summary = QLabel("No frames assigned yet.")
        self._summary.setStyleSheet("color: #888; font-size: 11px;")
        self._summary.setWordWrap(True)
        right.addWidget(self._summary)
        right.addStretch()

        body.addLayout(right)
        root.addLayout(body, stretch=1)

        # ── internal state ────────────────────────────────────────────────
        self._all_frames: list[SpriteFrame] = []
        self._part1 = ""
        self._part2 = ""

    # ── public API ────────────────────────────────────────────────────────

    @property
    def current_verb(self) -> str:
        text = self._verb_combo.currentText()
        if text == "(custom)":
            return normalize_name_token(self._custom_verb.text())
        return text

    def set_identity(self, part1: str, part2: str) -> None:
        self._part1 = part1
        self._part2 = part2
        self._identity_lbl.setText(f"{part1} – {part2}")

    def set_frames(self, frames: list[SpriteFrame]) -> None:
        self._all_frames = list(frames)
        self._refresh()

    # ── internals ─────────────────────────────────────────────────────────

    def _on_verb_changed(self, text: str) -> None:
        self._custom_verb.setVisible(text == "(custom)")

    def _refresh(self) -> None:
        self._frame_list.clear()
        for f in self._all_frames:
            item = QListWidgetItem()
            status = "unassigned" if f.direction is None else "assigned"
            sheet = f.source_sheet_name or "sheet"
            item.setText(
                f"[{sheet}] Frame #{f.id}  ({f.bbox.w}×{f.bbox.h})  ·  {status}"
            )
            item.setData(Qt.ItemDataRole.UserRole, f.id)
            if f.image is not None:
                item.setIcon(QIcon(_thumb_pixmap(f.image, 48)))
            self._frame_list.addItem(item)
        unassigned_count = sum(1 for f in self._all_frames if f.direction is None)
        self._unassigned_lbl.setText(
            f"{len(self._all_frames)} available  ·  {unassigned_count} unassigned"
        )

        # Button & summary update
        counts: dict[Direction, int] = {d: 0 for d in Direction}
        for f in self._all_frames:
            if f.direction is not None:
                counts[f.direction] += 1

        lines: list[str] = []
        for d in Direction:
            n = counts[d]
            btn = self._dir_btns[d]
            if n > 0:
                btn.setText(f"{_SHORT[d]}\n({n})")
                btn.setStyleSheet(
                    "QPushButton { background: #253525; color: #6c6; "
                    "border: 1px solid #4a7; border-radius: 4px; "
                    "font-weight: bold; font-size: 12px; }"
                    "QPushButton:hover { background: #305530; color: #fff; }"
                )
                lines.append(f"{d.value}: {n}")
            else:
                btn.setText(_SHORT[d])
                btn.setStyleSheet(
                    "QPushButton { background: #353545; color: #bbb; "
                    "border: 1px solid #555; border-radius: 4px; "
                    "font-weight: bold; font-size: 14px; }"
                    "QPushButton:hover { background: #454565; color: #fff; "
                    "border-color: #5af; }"
                )

        assigned = sum(counts.values())
        total = len(self._all_frames)
        txt = f"{assigned} / {total} assigned"
        if lines:
            txt += "\n" + "  |  ".join(lines)
        self._summary.setText(txt)

    def _on_assign(self, direction: Direction) -> None:
        ids: list[int] = []
        for item in self._frame_list.selectedItems():
            fid = item.data(Qt.ItemDataRole.UserRole)
            if fid is not None:
                ids.append(fid)
        if ids:
            self.frames_assigned.emit(direction, ids)


# ══════════════════════════════════════════════════════════════════════════════
# Main wizard widget
# ══════════════════════════════════════════════════════════════════════════════

class WorkflowWizard(QWidget):
    """Three-step post-detection workflow: Review → Identity → Sort.

    Signals
    -------
    review_completed(list[int])
        Rejected frame IDs that should be removed from the project.
    frames_assigned(Direction, list[int])
        Frame IDs assigned to a direction (MainWindow applies metadata).
    wizard_finished()
        The user clicked *Finish* – return to normal canvas view.
    wizard_cancelled()
        The user clicked *Cancel* – discard wizard and return.
    """

    review_completed = Signal(list)
    frames_assigned = Signal(object, list)
    wizard_finished = Signal()
    wizard_cancelled = Signal()

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        root = QVBoxLayout(self)
        root.setContentsMargins(0, 0, 0, 0)
        root.setSpacing(0)

        # ── step indicator bar ────────────────────────────────────────────
        self._step_bar = _StepBar([
            "1  Review Sprites",
            "2  Define Identity",
            "3  Assign Directions",
        ])
        root.addWidget(self._step_bar)

        sep1 = QFrame()
        sep1.setFrameShape(QFrame.Shape.HLine)
        sep1.setStyleSheet("color: #444;")
        root.addWidget(sep1)

        # ── stacked pages ─────────────────────────────────────────────────
        self._stack = QStackedWidget()
        self._review = _ReviewPage()
        self._identity = _IdentityPage()
        self._sort = _SortPage()
        self._stack.addWidget(self._review)
        self._stack.addWidget(self._identity)
        self._stack.addWidget(self._sort)
        root.addWidget(self._stack, stretch=1)

        # ── navigation bar ────────────────────────────────────────────────
        sep2 = QFrame()
        sep2.setFrameShape(QFrame.Shape.HLine)
        sep2.setStyleSheet("color: #444;")
        root.addWidget(sep2)

        nav = QHBoxLayout()
        nav.setContentsMargins(16, 8, 16, 8)

        self._btn_cancel = QPushButton("Cancel")
        self._btn_cancel.setStyleSheet(
            "QPushButton { background: #4a3535; color: #da8; "
            "border: 1px solid #755; border-radius: 4px; padding: 7px 18px; }"
            "QPushButton:hover { background: #5a3535; }"
        )
        self._btn_cancel.clicked.connect(self.wizard_cancelled.emit)
        nav.addWidget(self._btn_cancel)

        nav.addStretch()

        self._btn_back = QPushButton("Back")
        self._btn_back.setStyleSheet("QPushButton { padding: 7px 18px; }")
        self._btn_back.clicked.connect(self._go_back)
        nav.addWidget(self._btn_back)

        self._btn_next = QPushButton("Next")
        self._btn_next.setStyleSheet(
            "QPushButton { background: #3a6ea5; color: #fff; font-weight: bold; "
            "padding: 7px 22px; border: none; border-radius: 4px; }"
            "QPushButton:hover { background: #4a8ec5; }"
        )
        self._btn_next.clicked.connect(self._go_next)
        nav.addWidget(self._btn_next)

        root.addLayout(nav)

        # ── wire sort-page signal ─────────────────────────────────────────
        self._sort.frames_assigned.connect(
            lambda d, ids: self.frames_assigned.emit(d, ids)
        )

        # ── internal state ────────────────────────────────────────────────
        self._frames: list[SpriteFrame] = []
        self._set_page(0)

    # ==================================================================
    # Public API
    # ==================================================================

    def start(self, frames: list[SpriteFrame]) -> None:
        """Begin the wizard with the detected frames."""
        self._frames = list(frames)
        self._review.set_frames(self._frames)
        self._set_page(0)

    def refresh_sort_page(self, frames: list[SpriteFrame]) -> None:
        """Refresh the sort page after the model has been updated externally."""
        self._frames = list(frames)
        self._sort.set_frames(self._frames)

    @property
    def part1(self) -> str:
        return self._identity.part1

    @property
    def part2(self) -> str:
        return self._identity.part2

    @property
    def current_verb(self) -> str:
        return self._sort.current_verb

    # ==================================================================
    # Navigation
    # ==================================================================

    def _set_page(self, idx: int) -> None:
        self._stack.setCurrentIndex(idx)
        self._step_bar.set_active(idx)
        self._btn_back.setVisible(idx > 0)
        self._btn_next.setText("Finish" if idx == 2 else "Next")

    def _go_back(self) -> None:
        idx = self._stack.currentIndex()
        if idx > 0:
            self._set_page(idx - 1)

    def _go_next(self) -> None:
        idx = self._stack.currentIndex()

        if idx == 0:
            # Review → Identity
            rejected = self._review.rejected_ids()
            if rejected:
                self.review_completed.emit(rejected)
                rejected_set = set(rejected)
                self._frames = [
                    f for f in self._frames if f.id not in rejected_set
                ]
            self._set_page(1)

        elif idx == 1:
            # Identity → Sort
            self._sort.set_identity(
                self._identity.part1, self._identity.part2
            )
            self._sort.set_frames(self._frames)
            self._set_page(2)

        elif idx == 2:
            # Finish
            self.wizard_finished.emit()
