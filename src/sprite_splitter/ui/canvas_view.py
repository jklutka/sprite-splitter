"""Zoomable / pannable sprite-sheet canvas with frame overlay rectangles."""

from __future__ import annotations

from typing import Optional

from PySide6.QtCore import Qt, Signal, QPointF, QRectF
from PySide6.QtGui import (
    QColor,
    QImage,
    QMouseEvent,
    QPainter,
    QPen,
    QPixmap,
    QWheelEvent,
)
from PySide6.QtWidgets import (
    QGraphicsItem,
    QGraphicsPixmapItem,
    QGraphicsRectItem,
    QGraphicsScene,
    QGraphicsView,
)
import numpy as np

from sprite_splitter.models.sprite_frame import BBox


# ── resize cursor map ────────────────────────────────────────────────────────

_RESIZE_CURSOR: dict[str, Qt.CursorShape] = {
    "n":  Qt.CursorShape.SizeVerCursor,
    "s":  Qt.CursorShape.SizeVerCursor,
    "e":  Qt.CursorShape.SizeHorCursor,
    "w":  Qt.CursorShape.SizeHorCursor,
    "ne": Qt.CursorShape.SizeBDiagCursor,
    "sw": Qt.CursorShape.SizeBDiagCursor,
    "nw": Qt.CursorShape.SizeFDiagCursor,
    "se": Qt.CursorShape.SizeFDiagCursor,
}

# ── helpers ──────────────────────────────────────────────────────────────────


def ndarray_to_qimage(arr: np.ndarray) -> QImage:
    """Convert an RGBA uint8 ndarray to a QImage."""
    h, w, ch = arr.shape
    bytes_per_line = ch * w
    fmt = QImage.Format.Format_RGBA8888 if ch == 4 else QImage.Format.Format_RGB888
    # QImage doesn't copy the data, so we must keep a reference
    img = QImage(arr.data, w, h, bytes_per_line, fmt)
    return img.copy()  # detach from numpy buffer


# ── overlay rectangle for a detected frame ───────────────────────────────────


class FrameRectItem(QGraphicsRectItem):
    """Semi-transparent coloured rectangle drawn over a detected sprite."""

    _COLOR_UNASSIGNED = QColor(255, 80, 80, 90)
    _COLOR_ASSIGNED = QColor(80, 200, 80, 90)
    _PEN_NORMAL = QPen(QColor(255, 255, 0, 180), 1.5)
    _PEN_SELECTED = QPen(QColor(0, 255, 255, 255), 2.5)

    def __init__(self, frame_id: int, bbox: BBox, assigned: bool = False):
        super().__init__(float(bbox.x), float(bbox.y), float(bbox.w), float(bbox.h))
        self.frame_id = frame_id
        self.setFlag(QGraphicsItem.GraphicsItemFlag.ItemIsSelectable, True)
        self.setAcceptHoverEvents(True)
        self.setZValue(10)
        self.set_assigned(assigned)

    def set_assigned(self, assigned: bool) -> None:
        colour = self._COLOR_ASSIGNED if assigned else self._COLOR_UNASSIGNED
        self.setBrush(colour)
        self.setPen(self._PEN_NORMAL)

    # visual feedback on selection
    def itemChange(self, change, value):  # noqa: N802
        if change == QGraphicsItem.GraphicsItemChange.ItemSelectedHasChanged:
            self.setPen(self._PEN_SELECTED if value else self._PEN_NORMAL)
        return super().itemChange(change, value)


# ── the main canvas ─────────────────────────────────────────────────────────


class CanvasView(QGraphicsView):
    """QGraphicsView subclass supporting zoom (Ctrl+scroll), pan (mid-click),
    and click-selection of frame overlay rectangles.
    """

    frame_selected = Signal(int)        # emits frame_id when user clicks a rect
    frame_deselected = Signal()
    manual_rect_drawn = Signal(QRectF)  # emits rect when user rubber-band selects
    frame_bbox_changed = Signal(int, QRectF)  # frame_id, new scene rect after resize

    def __init__(self, parent=None):
        super().__init__(parent)
        self._scene = QGraphicsScene(self)
        self.setScene(self._scene)

        self._pixmap_item: Optional[QGraphicsPixmapItem] = None
        self._frame_rects: dict[int, FrameRectItem] = {}

        # interaction
        self.setDragMode(QGraphicsView.DragMode.RubberBandDrag)
        self.setRenderHint(QPainter.RenderHint.Antialiasing, False)
        self.setRenderHint(QPainter.RenderHint.SmoothPixmapTransform, False)
        self.setTransformationAnchor(QGraphicsView.ViewportAnchor.AnchorUnderMouse)
        self.setResizeAnchor(QGraphicsView.ViewportAnchor.AnchorUnderMouse)
        self.setVerticalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOn)
        self.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOn)
        self.setBackgroundBrush(QColor(48, 48, 48))

        self._zoom_factor = 1.0
        self._panning = False
        self._pan_start = None

        self._selected_frame_id: Optional[int] = None
        self._resize_state: Optional[dict] = None

    # ── public API ────────────────────────────────────────────────────────

    def load_image(self, arr: np.ndarray) -> None:
        """Display an RGBA ndarray on the canvas."""
        qimg = ndarray_to_qimage(arr)
        pixmap = QPixmap.fromImage(qimg)
        self.clear()
        self._pixmap_item = self._scene.addPixmap(pixmap)
        self._pixmap_item.setZValue(0)
        self.setSceneRect(QRectF(pixmap.rect()))
        self.fitInView(self._pixmap_item, Qt.AspectRatioMode.KeepAspectRatio)
        self._zoom_factor = 1.0

    def clear(self) -> None:
        self._scene.clear()
        self._pixmap_item = None
        self._frame_rects.clear()
        self._selected_frame_id = None
        self._resize_state = None
        self.setCursor(Qt.CursorShape.ArrowCursor)

    def set_frame_overlays(self, frames) -> None:
        """Draw overlay rects for each detected SpriteFrame."""
        # remove old rects
        for item in list(self._frame_rects.values()):
            self._scene.removeItem(item)
        self._frame_rects.clear()

        for f in frames:
            rect_item = FrameRectItem(f.id, f.bbox, assigned=f.is_fully_named)
            self._scene.addItem(rect_item)
            self._frame_rects[f.id] = rect_item

    def highlight_frame(self, frame_id: int) -> None:
        """Programmatically select a frame overlay (e.g. from sidebar click)."""
        self._scene.clearSelection()
        item = self._frame_rects.get(frame_id)
        if item:
            item.setSelected(True)
            self.centerOn(item)

    def update_frame_overlay(self, frame_id: int, assigned: bool) -> None:
        item = self._frame_rects.get(frame_id)
        if item:
            item.set_assigned(assigned)

    # ── resize helpers ────────────────────────────────────────────────────

    def _resize_edge(self, item: FrameRectItem, scene_pos: QPointF) -> Optional[str]:
        """Return which resize edge/corner is nearest to scene_pos, or None."""
        r = item.rect().translated(item.pos())
        m = 8.0 / self._zoom_factor
        nl = abs(scene_pos.x() - r.left())   < m
        nr = abs(scene_pos.x() - r.right())  < m
        nt = abs(scene_pos.y() - r.top())    < m
        nb = abs(scene_pos.y() - r.bottom()) < m
        if nt and nl: return "nw"
        if nt and nr: return "ne"
        if nb and nl: return "sw"
        if nb and nr: return "se"
        if nl: return "w"
        if nr: return "e"
        if nt: return "n"
        if nb: return "s"
        return None

    @staticmethod
    def _apply_resize(start_rect: QRectF, edge: str, delta: QPointF) -> QRectF:
        """Return a new QRectF after applying delta to the given edge."""
        r = QRectF(start_rect)
        if "n" in edge:
            r.setTop(r.top() + delta.y())
        if "s" in edge:
            r.setBottom(r.bottom() + delta.y())
        if "w" in edge:
            r.setLeft(r.left() + delta.x())
        if "e" in edge:
            r.setRight(r.right() + delta.x())
        return r.normalized()

    # ── zoom ──────────────────────────────────────────────────────────────

    def wheelEvent(self, event: QWheelEvent) -> None:  # noqa: N802
        if event.modifiers() & Qt.KeyboardModifier.ControlModifier:
            factor = 1.15 if event.angleDelta().y() > 0 else 1 / 1.15
            self._zoom_factor *= factor
            self.scale(factor, factor)
            event.accept()
        else:
            super().wheelEvent(event)

    # ── middle-click pan ──────────────────────────────────────────────────

    def mousePressEvent(self, event: QMouseEvent) -> None:  # noqa: N802
        if event.button() == Qt.MouseButton.MiddleButton:
            self._panning = True
            self._pan_start = event.position().toPoint()
            self.setCursor(Qt.CursorShape.ClosedHandCursor)
            event.accept()
            return

        if event.button() == Qt.MouseButton.LeftButton and self._selected_frame_id is not None:
            item = self._frame_rects.get(self._selected_frame_id)
            if item is not None:
                scene_pos = self.mapToScene(event.position().toPoint())
                edge = self._resize_edge(item, scene_pos)
                if edge is not None:
                    self._resize_state = {
                        "frame_id": self._selected_frame_id,
                        "item": item,
                        "edge": edge,
                        "start_rect": QRectF(item.rect()),
                        "start_pos": scene_pos,
                    }
                    self.setDragMode(QGraphicsView.DragMode.NoDrag)
                    self.setCursor(_RESIZE_CURSOR[edge])
                    event.accept()
                    return

        super().mousePressEvent(event)

    def mouseMoveEvent(self, event: QMouseEvent) -> None:  # noqa: N802
        if self._panning and self._pan_start is not None:
            delta = event.position().toPoint() - self._pan_start
            self._pan_start = event.position().toPoint()
            self.horizontalScrollBar().setValue(
                self.horizontalScrollBar().value() - delta.x()
            )
            self.verticalScrollBar().setValue(
                self.verticalScrollBar().value() - delta.y()
            )
            event.accept()
            return

        if self._resize_state is not None:
            scene_pos = self.mapToScene(event.position().toPoint())
            delta = scene_pos - self._resize_state["start_pos"]
            new_rect = self._apply_resize(self._resize_state["start_rect"],
                                          self._resize_state["edge"], delta)
            # Clamp to image bounds
            bounds = self._scene.sceneRect()
            new_rect = new_rect.intersected(bounds)
            self._resize_state["item"].setRect(new_rect)
            event.accept()
            return

        # Update cursor when hovering near a selected frame's edges
        if self._selected_frame_id is not None:
            item = self._frame_rects.get(self._selected_frame_id)
            if item is not None:
                scene_pos = self.mapToScene(event.position().toPoint())
                edge = self._resize_edge(item, scene_pos)
                if edge is not None:
                    self.setCursor(_RESIZE_CURSOR[edge])
                    super().mouseMoveEvent(event)
                    return
        self.setCursor(Qt.CursorShape.ArrowCursor)
        super().mouseMoveEvent(event)

    def mouseReleaseEvent(self, event: QMouseEvent) -> None:  # noqa: N802
        if event.button() == Qt.MouseButton.MiddleButton:
            self._panning = False
            self.setCursor(Qt.CursorShape.ArrowCursor)
            event.accept()
            return

        if event.button() == Qt.MouseButton.LeftButton and self._resize_state is not None:
            state = self._resize_state
            self._resize_state = None
            self.setDragMode(QGraphicsView.DragMode.RubberBandDrag)
            final_rect = state["item"].rect()
            self.frame_bbox_changed.emit(state["frame_id"], final_rect)
            self.setCursor(Qt.CursorShape.ArrowCursor)
            event.accept()
            return

        # Check if a frame rect was clicked
        if event.button() == Qt.MouseButton.LeftButton:
            items = self.items(event.position().toPoint())
            for item in items:
                if isinstance(item, FrameRectItem):
                    self._selected_frame_id = item.frame_id
                    self.frame_selected.emit(item.frame_id)
                    return
            self._selected_frame_id = None
            self.frame_deselected.emit()

        super().mouseReleaseEvent(event)

    # ── rubber-band selection for manual frame definition ─────────────────

    def _handle_rubber_band(self, rect):
        """Called when a rubber-band selection completes."""
        if not rect.isEmpty():
            scene_rect = self.mapToScene(rect).boundingRect()
            self.manual_rect_drawn.emit(scene_rect)
