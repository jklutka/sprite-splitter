"""Animation preview panel – mouse-driven direction, timer-driven frame playback.

The user moves the mouse around the preview area to control the facing
direction of the sprite.  The widget continuously plays through the
animation frames for the current ``part1-part2-verb-direction`` group,
giving an in-engine-style visual test of the classified sprite frames.
"""

from __future__ import annotations

import math
from collections import defaultdict
from typing import Optional

import numpy as np
from PySide6.QtCore import Qt, QTimer, QPointF, QRectF, Signal, QSize
from PySide6.QtGui import (
    QBrush,
    QColor,
    QFont,
    QImage,
    QMouseEvent,
    QPainter,
    QPen,
    QPixmap,
)
from PySide6.QtWidgets import (
    QComboBox,
    QFormLayout,
    QHBoxLayout,
    QLabel,
    QSlider,
    QSpinBox,
    QVBoxLayout,
    QWidget,
)

from sprite_splitter.detection.background import apply_transparency
from sprite_splitter.models.sprite_frame import Direction, SpriteFrame


# ── Direction mapping from angle ─────────────────────────────────────────────

# Ordered by clockwise angle from +Y (screen up).  Sector boundaries are at
# ±22.5° around each cardinal/intercardinal direction.
_DIRECTION_ORDER: list[Direction] = [
    Direction.NORTH,
    Direction.NORTHEAST,
    Direction.EAST,
    Direction.SOUTHEAST,
    Direction.SOUTH,
    Direction.SOUTHWEST,
    Direction.WEST,
    Direction.NORTHWEST,
]

_DIRECTION_ANGLES: dict[Direction, float] = {
    d: i * 45.0 for i, d in enumerate(_DIRECTION_ORDER)
}


def _angle_to_direction(angle_deg: float) -> Direction:
    """Map a 0-360° angle (0 = north / up, clockwise) to the nearest Direction."""
    # Normalise
    angle_deg = angle_deg % 360
    idx = int((angle_deg + 22.5) // 45) % 8
    return _DIRECTION_ORDER[idx]


def _mouse_angle(center: QPointF, pos: QPointF) -> float:
    """Return the angle in degrees (0=north, clockwise) from *center* to *pos*."""
    dx = pos.x() - center.x()
    dy = center.y() - pos.y()  # invert Y (screen coords)
    rad = math.atan2(dx, dy)   # atan2(x, y) gives angle from +Y axis
    deg = math.degrees(rad) % 360
    return deg


# ── Helper: build a checkerboard for transparency ────────────────────────────

def _checkerboard_pixmap(size: int = 256, cell: int = 8) -> QPixmap:
    img = QImage(size, size, QImage.Format.Format_RGB32)
    c1 = QColor(200, 200, 200)
    c2 = QColor(240, 240, 240)
    for y in range(size):
        for x in range(size):
            colour = c1 if ((x // cell) + (y // cell)) % 2 == 0 else c2
            img.setPixelColor(x, y, colour)
    return QPixmap.fromImage(img)


# ── Animation group index ────────────────────────────────────────────────────

AnimationGroup = dict[Direction, list[SpriteFrame]]
# key = Direction, value = list of SpriteFrame sorted by frame_number


def build_animation_groups(
    frames: list[SpriteFrame],
) -> dict[str, dict[str, AnimationGroup]]:
    """Index fully-named frames into a nested structure::

        { "part1-part2": { "verb": { Direction: [frame, …] } } }
    """
    tree: dict[str, dict[str, dict[Direction, list[SpriteFrame]]]] = defaultdict(
        lambda: defaultdict(lambda: defaultdict(list))
    )
    for f in frames:
        if not f.is_fully_named or f.image is None:
            continue
        entity_key = f"{f.part1}-{f.part2}"
        verb_key = f.effective_verb
        tree[entity_key][verb_key][f.direction].append(f)

    # sort each direction's frames by frame_number
    for entity in tree.values():
        for verb in entity.values():
            for direction in verb:
                verb[direction].sort(key=lambda fr: fr.frame_number)

    return tree


# ── The preview widget ───────────────────────────────────────────────────────

class AnimationPreview(QWidget):
    """Interactive animation preview controlled by mouse direction.

    Signals
    -------
    direction_changed(str)
        Emitted when the active direction changes (value is e.g. "east").
    """

    direction_changed = Signal(str)

    # ── construction ──────────────────────────────────────────────────────

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setMinimumSize(280, 340)
        self.setMouseTracking(True)

        # layout: controls on top, preview canvas fills remaining space
        root = QVBoxLayout(self)
        root.setContentsMargins(6, 6, 6, 6)

        # -- controls row --
        ctrl = QFormLayout()

        self._entity_combo = QComboBox()
        self._entity_combo.currentTextChanged.connect(self._on_entity_changed)
        ctrl.addRow("Entity:", self._entity_combo)

        self._verb_combo = QComboBox()
        self._verb_combo.currentTextChanged.connect(self._on_verb_changed)
        ctrl.addRow("Action:", self._verb_combo)

        fps_row = QHBoxLayout()
        self._fps_slider = QSlider(Qt.Orientation.Horizontal)
        self._fps_slider.setRange(1, 30)
        self._fps_slider.setValue(8)
        self._fps_label = QLabel("8 FPS")
        self._fps_slider.valueChanged.connect(self._on_fps_changed)
        fps_row.addWidget(self._fps_slider, stretch=1)
        fps_row.addWidget(self._fps_label)
        ctrl.addRow("Speed:", fps_row)

        self._zoom_spin = QSpinBox()
        self._zoom_spin.setRange(1, 16)
        self._zoom_spin.setValue(1)
        self._zoom_spin.setSuffix("×")
        self._zoom_spin.valueChanged.connect(self._request_repaint)
        ctrl.addRow("Zoom:", self._zoom_spin)

        root.addLayout(ctrl)

        # -- info labels --
        self._info_label = QLabel("Move mouse to control direction")
        self._info_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self._info_label.setStyleSheet("color: #999; font-style: italic;")
        root.addWidget(self._info_label)

        # remaining space is painted in paintEvent
        root.addStretch(1)

        # -- state --
        self._groups: dict[str, dict[str, AnimationGroup]] = {}
        self._current_entity: str = ""
        self._current_verb: str = ""
        self._current_direction: Direction = Direction.SOUTH
        self._current_frame_idx: int = 0
        self._current_pixmaps: dict[Direction, list[QPixmap]] = {}
        self._bg_color: tuple[int, int, int] = (255, 0, 255)
        self._tolerance: int = 30
        self._checker = _checkerboard_pixmap(512, 8)

        # animation timer
        self._timer = QTimer(self)
        self._timer.timeout.connect(self._advance_frame)
        self._timer.start(1000 // 8)

    # ── public API ────────────────────────────────────────────────────────

    def set_frames(
        self,
        frames: list[SpriteFrame],
        bg_color: tuple[int, int, int] = (255, 0, 255),
        tolerance: int = 30,
    ) -> None:
        """Rebuild animation groups from the current project frames."""
        self._bg_color = bg_color
        self._tolerance = tolerance
        self._groups = build_animation_groups(frames)
        self._current_pixmaps.clear()

        # populate entity combo
        prev_entity = self._entity_combo.currentText()
        self._entity_combo.blockSignals(True)
        self._entity_combo.clear()
        for key in sorted(self._groups.keys()):
            self._entity_combo.addItem(key)
        self._entity_combo.blockSignals(False)

        # try to restore previous selection
        idx = self._entity_combo.findText(prev_entity)
        if idx >= 0:
            self._entity_combo.setCurrentIndex(idx)
        elif self._entity_combo.count() > 0:
            self._entity_combo.setCurrentIndex(0)

        self._on_entity_changed(self._entity_combo.currentText())

    def set_direction(self, direction: Direction) -> None:
        """Programmatically switch the active direction (called from DirectionPanel)."""
        if direction != self._current_direction:
            self._current_direction = direction
            self._current_frame_idx = 0
            self.direction_changed.emit(direction.value)
            self.update()

    # ── internals: combo changes ──────────────────────────────────────────

    def _on_entity_changed(self, entity: str) -> None:
        self._current_entity = entity
        verbs = self._groups.get(entity, {})

        prev_verb = self._verb_combo.currentText()
        self._verb_combo.blockSignals(True)
        self._verb_combo.clear()
        for v in sorted(verbs.keys()):
            self._verb_combo.addItem(v)
        self._verb_combo.blockSignals(False)

        idx = self._verb_combo.findText(prev_verb)
        if idx >= 0:
            self._verb_combo.setCurrentIndex(idx)
        elif self._verb_combo.count() > 0:
            self._verb_combo.setCurrentIndex(0)

        self._on_verb_changed(self._verb_combo.currentText())

    def _on_verb_changed(self, verb: str) -> None:
        self._current_verb = verb
        self._current_frame_idx = 0
        self._rebuild_pixmaps()
        self.update()

    def _on_fps_changed(self, fps: int) -> None:
        self._fps_label.setText(f"{fps} FPS")
        self._timer.setInterval(1000 // max(fps, 1))

    def _request_repaint(self) -> None:
        self.update()

    # ── pixmap cache ──────────────────────────────────────────────────────

    def _rebuild_pixmaps(self) -> None:
        """Pre-render transparent QPixmaps for the current entity+verb."""
        self._current_pixmaps.clear()
        anim_group = (
            self._groups
            .get(self._current_entity, {})
            .get(self._current_verb, {})
        )
        if not anim_group:
            return

        for direction, frame_list in anim_group.items():
            pms: list[QPixmap] = []
            for sf in frame_list:
                rgba = apply_transparency(sf.image, self._bg_color, self._tolerance,
                                          soft_edge=False)
                h, w, ch = rgba.shape
                bpl = ch * w
                qimg = QImage(rgba.data, w, h, bpl, QImage.Format.Format_RGBA8888).copy()
                pms.append(QPixmap.fromImage(qimg))
            self._current_pixmaps[direction] = pms

    # ── animation timer ───────────────────────────────────────────────────

    def _advance_frame(self) -> None:
        frames = self._current_pixmaps.get(self._current_direction, [])
        if not frames:
            self._current_frame_idx = 0
        else:
            self._current_frame_idx = (self._current_frame_idx + 1) % len(frames)
        self.update()

    # ── mouse → direction ─────────────────────────────────────────────────

    def mouseMoveEvent(self, event: QMouseEvent) -> None:  # noqa: N802
        preview_rect = self._preview_rect()
        center = preview_rect.center()
        pos = event.position()

        # only update if mouse is reasonably inside the preview area
        if preview_rect.adjusted(-40, -40, 40, 40).contains(pos):
            angle = _mouse_angle(QPointF(center), QPointF(pos.x(), pos.y()))
            new_dir = _angle_to_direction(angle)
            if new_dir != self._current_direction:
                self._current_direction = new_dir
                self._current_frame_idx = 0
                self.direction_changed.emit(new_dir.value)
                self.update()

        super().mouseMoveEvent(event)

    # ── paint ─────────────────────────────────────────────────────────────

    def _preview_rect(self) -> QRectF:
        """Compute the rectangle used for the sprite preview area."""
        w = self.width()
        h = self.height()
        # Reserve top ~140px for controls; rest is preview
        top = 140
        side = min(w - 12, h - top - 12)
        side = max(side, 64)
        x = (w - side) / 2
        y = top + (h - top - side) / 2
        return QRectF(x, y, side, side)

    def paintEvent(self, event) -> None:  # noqa: N802
        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.Antialiasing, True)

        rect = self._preview_rect()
        center = rect.center()

        # ── checkerboard bg ───────────────────────────────────────────────
        p.save()
        p.setClipRect(rect)
        p.drawPixmap(int(rect.x()), int(rect.y()), self._checker)
        p.restore()

        # ── compass ring ──────────────────────────────────────────────────
        ring_r = min(rect.width(), rect.height()) / 2 - 4
        p.setPen(QPen(QColor(100, 100, 100, 120), 1))
        p.drawEllipse(center, ring_r, ring_r)

        font = QFont("Segoe UI", 8)
        p.setFont(font)
        for d in _DIRECTION_ORDER:
            angle_rad = math.radians(_DIRECTION_ANGLES[d])
            # Convert our north=0 clockwise to screen coords
            sx = center.x() + (ring_r + 12) * math.sin(angle_rad)
            sy = center.y() - (ring_r + 12) * math.cos(angle_rad)
            label = d.value[0].upper()  # N, S, E, W, etc
            if d in (Direction.NORTHEAST, Direction.NORTHWEST,
                     Direction.SOUTHEAST, Direction.SOUTHWEST):
                label = d.value[:2].upper()  # NE, NW, SE, SW

            if d == self._current_direction:
                p.setPen(QPen(QColor(0, 220, 255), 2))
                font.setBold(True)
                p.setFont(font)
            else:
                p.setPen(QPen(QColor(150, 150, 150, 180), 1))
                font.setBold(False)
                p.setFont(font)

            p.drawText(QRectF(sx - 14, sy - 10, 28, 20),
                       Qt.AlignmentFlag.AlignCenter, label)

        # ── direction indicator line ──────────────────────────────────────
        angle_rad = math.radians(_DIRECTION_ANGLES.get(self._current_direction, 0))
        lx = center.x() + (ring_r - 8) * math.sin(angle_rad)
        ly = center.y() - (ring_r - 8) * math.cos(angle_rad)
        p.setPen(QPen(QColor(0, 220, 255, 200), 2, Qt.PenStyle.DashLine))
        p.drawLine(center, QPointF(lx, ly))

        # ── sprite frame ─────────────────────────────────────────────────
        frames = self._current_pixmaps.get(self._current_direction, [])
        if frames:
            idx = self._current_frame_idx % len(frames)
            pm = frames[idx]
            zoom = self._zoom_spin.value()
            sw = pm.width() * zoom
            sh = pm.height() * zoom
            target = QRectF(center.x() - sw / 2, center.y() - sh / 2, sw, sh)
            # Nearest-neighbour scaling for pixel art
            p.setRenderHint(QPainter.RenderHint.SmoothPixmapTransform, False)
            p.drawPixmap(target.toRect(), pm)

            # frame counter
            p.setPen(QColor(200, 200, 200))
            p.setFont(QFont("Consolas", 9))
            total = len(frames)
            p.drawText(
                QRectF(rect.x(), rect.bottom() - 20, rect.width(), 20),
                Qt.AlignmentFlag.AlignCenter,
                f"Frame {idx + 1}/{total}  │  {self._current_direction.value}",
            )
        else:
            # No frames for this direction
            p.setPen(QColor(120, 120, 120))
            p.setFont(QFont("Segoe UI", 10))
            p.drawText(rect, Qt.AlignmentFlag.AlignCenter,
                       f"No frames for\n{self._current_direction.value}")

        # ── info ──────────────────────────────────────────────────────────
        if self._current_entity and self._current_verb:
            self._info_label.setText(
                f"{self._current_entity}  ·  {self._current_verb}  ·  "
                f"{self._current_direction.value}"
            )
        elif not self._groups:
            self._info_label.setText("No named animation groups yet")

        p.end()

    # ── sizing ────────────────────────────────────────────────────────────

    def sizeHint(self) -> QSize:  # noqa: N802
        return QSize(320, 480)
