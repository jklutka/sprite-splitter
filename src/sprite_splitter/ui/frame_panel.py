"""Side-panel listing detected sprite frames with thumbnails and status."""

from __future__ import annotations

from typing import Optional

from PySide6.QtCore import Qt, Signal, QSize, QByteArray, QMimeData
from PySide6.QtGui import QColor, QDrag, QIcon, QImage, QKeySequence, QPixmap, QShortcut
from PySide6.QtWidgets import (
    QAbstractItemView,
    QHBoxLayout,
    QLabel,
    QListWidget,
    QListWidgetItem,
    QPushButton,
    QVBoxLayout,
    QWidget,
)
import numpy as np

from sprite_splitter.models.sprite_frame import SpriteFrame
from sprite_splitter.ui.canvas_view import ndarray_to_qimage
from sprite_splitter.ui.direction_panel import FRAME_DRAG_MIME


THUMB_SIZE = 48


def _make_thumbnail(arr: Optional[np.ndarray]) -> QPixmap:
    """Create a square thumbnail QPixmap from an RGBA array."""
    if arr is None:
        pm = QPixmap(THUMB_SIZE, THUMB_SIZE)
        pm.fill(QColor(80, 80, 80))
        return pm
    qimg = ndarray_to_qimage(arr)
    pm = QPixmap.fromImage(qimg)
    return pm.scaled(THUMB_SIZE, THUMB_SIZE, Qt.AspectRatioMode.KeepAspectRatio,
                     Qt.TransformationMode.FastTransformation)


class FramePanel(QWidget):
    """Sidebar widget listing all detected frames."""

    frame_clicked = Signal(int)          # frame_id
    assign_requested = Signal(list)      # list[int] – selected frame ids
    delete_requested = Signal(list)      # list[int] – selected frame ids
    reorder_requested = Signal(list)     # list[int] – ordered frame ids

    def __init__(self, parent=None):
        super().__init__(parent)
        self._layout = QVBoxLayout(self)
        self._layout.setContentsMargins(4, 4, 4, 4)

        # Header
        header = QLabel("Detected Frames")
        header.setStyleSheet("font-weight: bold; font-size: 13px;")
        self._layout.addWidget(header)

        # Frame list (with drag support)
        self._list = _DraggableFrameList(self)
        self._list.setIconSize(QSize(THUMB_SIZE, THUMB_SIZE))
        self._list.setSelectionMode(QAbstractItemView.SelectionMode.ExtendedSelection)
        self._list.setDragEnabled(True)
        self._list.setAcceptDrops(True)
        self._list.setDropIndicatorShown(True)
        self._list.setDragDropMode(QAbstractItemView.DragDropMode.DragDrop)
        self._list.setDragDropOverwriteMode(False)
        self._list.setDefaultDropAction(Qt.DropAction.MoveAction)
        self._list.currentItemChanged.connect(self._on_current_changed)
        self._list.order_changed.connect(
            lambda: self.reorder_requested.emit(self._ordered_ids())
        )
        self._layout.addWidget(self._list, stretch=1)

        # Action buttons
        btn_row = QHBoxLayout()
        self._btn_assign = QPushButton("Assign Name…")
        self._btn_assign.clicked.connect(self._on_assign)
        self._btn_delete = QPushButton("Delete")
        self._btn_delete.clicked.connect(self._on_delete)
        self._btn_up = QPushButton("Move Up")
        self._btn_up.clicked.connect(lambda: self._move_current(-1))
        self._btn_down = QPushButton("Move Down")
        self._btn_down.clicked.connect(lambda: self._move_current(1))
        btn_row.addWidget(self._btn_assign)
        btn_row.addWidget(self._btn_delete)
        btn_row.addWidget(self._btn_up)
        btn_row.addWidget(self._btn_down)
        self._layout.addLayout(btn_row)

        # Count label
        self._count_label = QLabel("0 frames")
        self._layout.addWidget(self._count_label)

        self._shortcut_move_up = QShortcut(QKeySequence("Alt+Up"), self)
        self._shortcut_move_up.activated.connect(lambda: self._move_current(-1))
        self._shortcut_move_down = QShortcut(QKeySequence("Alt+Down"), self)
        self._shortcut_move_down.activated.connect(lambda: self._move_current(1))

        self._frame_map: dict[int, QListWidgetItem] = {}
        self._frame_data: dict[int, SpriteFrame] = {}

    # ── public API ────────────────────────────────────────────────────────

    def set_frames(self, frames: list[SpriteFrame]) -> None:
        """Rebuild the list from scratch."""
        self._list.clear()
        self._frame_map.clear()
        self._frame_data = {f.id: f for f in frames}
        for f in frames:
            self._add_item(f)
        self._count_label.setText(f"{len(frames)} frames")

    def update_frame(self, frame: SpriteFrame) -> None:
        """Refresh the display for a single frame."""
        item = self._frame_map.get(frame.id)
        if item is None:
            return
        self._frame_data[frame.id] = frame
        item.setText(self._item_label(frame))
        item.setIcon(QIcon(_make_thumbnail(frame.image)))
        if frame.is_fully_named:
            item.setForeground(QColor(80, 200, 80))
        else:
            item.setForeground(QColor(255, 120, 120))

    def select_frame(self, frame_id: int) -> None:
        """Select the item for a given frame_id from the outside."""
        item = self._frame_map.get(frame_id)
        if item:
            self._list.setCurrentItem(item)

    def selected_ids(self) -> list[int]:
        """Return currently selected frame IDs."""
        ids = []
        for item in self._list.selectedItems():
            fid = item.data(Qt.ItemDataRole.UserRole)
            if fid is not None:
                ids.append(fid)
        return ids

    # ── internals ─────────────────────────────────────────────────────────

    def _add_item(self, frame: SpriteFrame) -> None:
        item = QListWidgetItem()
        item.setText(self._item_label(frame))
        item.setIcon(QIcon(_make_thumbnail(frame.image)))
        item.setData(Qt.ItemDataRole.UserRole, frame.id)
        if frame.is_fully_named:
            item.setForeground(QColor(80, 200, 80))
        else:
            item.setForeground(QColor(255, 120, 120))
        self._list.addItem(item)
        self._frame_map[frame.id] = item

    def _item_label(self, frame: SpriteFrame) -> str:
        sheet = frame.source_sheet_name or "sheet"
        return f"[{sheet}] {frame.display_name}"

    def _on_current_changed(self, current: Optional[QListWidgetItem], _prev):
        if current is not None:
            fid = current.data(Qt.ItemDataRole.UserRole)
            if fid is not None:
                self.frame_clicked.emit(fid)

    def _on_assign(self):
        ids = self.selected_ids()
        if ids:
            self.assign_requested.emit(ids)

    def _on_delete(self):
        ids = self.selected_ids()
        if ids:
            self.delete_requested.emit(ids)

    def _ordered_ids(self) -> list[int]:
        ids: list[int] = []
        for row in range(self._list.count()):
            item = self._list.item(row)
            if item is None:
                continue
            fid = item.data(Qt.ItemDataRole.UserRole)
            if fid is not None:
                ids.append(fid)
        return ids

    def _move_current(self, offset: int) -> None:
        current_row = self._list.currentRow()
        if current_row < 0:
            return

        target_row = current_row + offset
        if target_row < 0 or target_row >= self._list.count():
            return

        item = self._list.takeItem(current_row)
        self._list.insertItem(target_row, item)
        self._list.setCurrentItem(item)
        item.setSelected(True)
        self.reorder_requested.emit(self._ordered_ids())


# ── Draggable list widget ────────────────────────────────────────────────────

class _DraggableFrameList(QListWidget):
    """QListWidget subclass that initiates a drag carrying frame IDs."""

    order_changed = Signal()

    def startDrag(self, supportedActions) -> None:  # noqa: N802
        items = self.selectedItems()
        if not items:
            return
        ids = []
        for item in items:
            fid = item.data(Qt.ItemDataRole.UserRole)
            if fid is not None:
                ids.append(str(fid))
        if not ids:
            return

        mime = QMimeData()
        mime.setData(FRAME_DRAG_MIME, QByteArray(",".join(ids).encode("utf-8")))

        drag = QDrag(self)
        drag.setMimeData(mime)

        # Use the first item's icon as the drag pixmap
        first = items[0]
        icon = first.icon()
        if not icon.isNull():
            drag.setPixmap(icon.pixmap(THUMB_SIZE, THUMB_SIZE))

        drag.exec(
            Qt.DropAction.MoveAction | Qt.DropAction.CopyAction,
            Qt.DropAction.MoveAction,
        )

    def dropEvent(self, event) -> None:  # noqa: N802
        internal_move = event.source() is self
        super().dropEvent(event)
        if internal_move and event.isAccepted():
            self.order_changed.emit()
