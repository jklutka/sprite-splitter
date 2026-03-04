"""Project-level state: source image, detected frames, and project persistence."""

from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Optional

import numpy as np
from PIL import Image
from PySide6.QtCore import QObject, Signal

from sprite_splitter.models.sprite_frame import (
    BBox,
    Direction,
    SpriteFrame,
    Verb,
    reset_frame_ids,
)


@dataclass
class SourceSheet:
    """Loaded source sprite sheet and its ID."""

    id: int
    path: Path
    array: np.ndarray


@dataclass
class DetectionSettings:
    """Parameters that control how sprites are detected."""
    mode: str = "contour"              # "contour" or "grid"
    bg_color: tuple[int, int, int] = (255, 0, 255)  # default magenta
    tolerance: int = 30
    min_area: int = 16                 # minimum sprite area in px²

    # grid-specific
    cell_width: int = 32
    cell_height: int = 32
    margin: int = 0
    padding: int = 0

    def to_dict(self) -> dict:
        return {
            "mode": self.mode,
            "bg_color": list(self.bg_color),
            "tolerance": self.tolerance,
            "min_area": self.min_area,
            "cell_width": self.cell_width,
            "cell_height": self.cell_height,
            "margin": self.margin,
            "padding": self.padding,
        }

    @classmethod
    def from_dict(cls, d: dict) -> "DetectionSettings":
        return cls(
            mode=d.get("mode", "contour"),
            bg_color=tuple(d.get("bg_color", [255, 0, 255])),
            tolerance=d.get("tolerance", 30),
            min_area=d.get("min_area", 16),
            cell_width=d.get("cell_width", 32),
            cell_height=d.get("cell_height", 32),
            margin=d.get("margin", 0),
            padding=d.get("padding", 0),
        )


class SpriteProject(QObject):
    """Central model object that owns all project state.

    Emits Qt signals so the UI can react to changes.
    """

    frames_changed = Signal()          # emitted after detect / add / remove
    frame_updated = Signal(int)        # emitted when a single frame's metadata changes (id)
    project_loaded = Signal()          # emitted after loading a saved project or new image
    active_sheet_changed = Signal(int)

    def __init__(self, parent: Optional[QObject] = None) -> None:
        super().__init__(parent)
        self._sheets: list[SourceSheet] = []
        self._active_sheet_id: Optional[int] = None
        self._next_sheet_id: int = 1
        self.settings = DetectionSettings()
        self._frames: list[SpriteFrame] = []

    # ── frame access ──────────────────────────────────────────────────────────

    @property
    def frames(self) -> list[SpriteFrame]:
        return list(self._frames)

    @property
    def sheets(self) -> list[SourceSheet]:
        return list(self._sheets)

    @property
    def active_sheet_id(self) -> Optional[int]:
        return self._active_sheet_id

    @property
    def source_path(self) -> Optional[Path]:
        """Backwards-compatible alias for active source sheet path."""
        active = self.active_sheet
        return active.path if active is not None else None

    @property
    def source_array(self) -> Optional[np.ndarray]:
        """Backwards-compatible alias for active source sheet array."""
        active = self.active_sheet
        return active.array if active is not None else None

    @property
    def active_sheet(self) -> Optional[SourceSheet]:
        if self._active_sheet_id is None:
            return None
        for sheet in self._sheets:
            if sheet.id == self._active_sheet_id:
                return sheet
        return None

    def frame_by_id(self, frame_id: int) -> Optional[SpriteFrame]:
        for f in self._frames:
            if f.id == frame_id:
                return f
        return None

    def frames_for_sheet(self, sheet_id: int) -> list[SpriteFrame]:
        return [f for f in self._frames if f.source_sheet_id == sheet_id]

    # ── image loading ─────────────────────────────────────────────────────────

    def load_image(self, path: str | Path) -> None:
        """Load a sprite sheet PNG into the project."""
        self.load_images([path], clear_frames=True)

    def load_images(self, paths: list[str | Path], *, clear_frames: bool = True) -> None:
        """Load one or more sprite sheets into the project."""
        resolved: list[Path] = []
        for raw_path in paths:
            path = Path(raw_path)
            if not path.is_file():
                raise FileNotFoundError(f"Image not found: {path}")
            resolved.append(path)

        self._sheets.clear()
        self._next_sheet_id = 1
        for path in resolved:
            img = Image.open(path).convert("RGBA")
            self._sheets.append(
                SourceSheet(
                    id=self._next_sheet_id,
                    path=path,
                    array=np.array(img, dtype=np.uint8),
                )
            )
            self._next_sheet_id += 1

        self._active_sheet_id = self._sheets[0].id if self._sheets else None
        if clear_frames:
            self._frames.clear()
            reset_frame_ids()
        self.project_loaded.emit()
        if self._active_sheet_id is not None:
            self.active_sheet_changed.emit(self._active_sheet_id)

    def set_active_sheet(self, sheet_id: int) -> None:
        if self._active_sheet_id == sheet_id:
            return
        if not any(sheet.id == sheet_id for sheet in self._sheets):
            return
        self._active_sheet_id = sheet_id
        self.active_sheet_changed.emit(sheet_id)

    def set_active_sheet_by_path(self, path: str | Path) -> None:
        target = Path(path)
        for sheet in self._sheets:
            if sheet.path == target:
                self.set_active_sheet(sheet.id)
                return

    # ── frame management ──────────────────────────────────────────────────────

    def set_frames(self, frames: list[SpriteFrame]) -> None:
        """Replace all detected frames (e.g. after running detection)."""
        self._frames = list(frames)
        self.frames_changed.emit()

    def add_frame(self, frame: SpriteFrame) -> None:
        self._frames.append(frame)
        self.frames_changed.emit()

    def clone_frame(self, frame_id: int) -> Optional[SpriteFrame]:
        """Create and append a new frame instance copied from an existing frame."""
        source = self.frame_by_id(frame_id)
        if source is None:
            return None

        clone = SpriteFrame(
            bbox=BBox(source.bbox.x, source.bbox.y, source.bbox.w, source.bbox.h),
            image=source.image.copy() if source.image is not None else None,
            source_sheet_id=source.source_sheet_id,
            source_sheet_name=source.source_sheet_name,
        )
        self._frames.append(clone)
        self.frames_changed.emit()
        return clone

    def remove_frame(self, frame_id: int) -> None:
        self._frames = [f for f in self._frames if f.id != frame_id]
        self.frames_changed.emit()

    def reorder_frames(self, ordered_ids: list[int]) -> None:
        """Reorder frames by ID and re-sequence named animation frames."""
        if not ordered_ids:
            return

        by_id = {f.id: f for f in self._frames}
        seen: set[int] = set()
        reordered: list[SpriteFrame] = []

        for frame_id in ordered_ids:
            frame = by_id.get(frame_id)
            if frame is None or frame_id in seen:
                continue
            reordered.append(frame)
            seen.add(frame_id)

        for frame in self._frames:
            if frame.id not in seen:
                reordered.append(frame)

        self._frames = reordered
        self._renumber_named_sequences()
        self.frames_changed.emit()

    def update_frame(self, frame_id: int, **kwargs) -> None:  # noqa: ANN003
        """Update naming metadata on a frame.  Accepted kwargs match SpriteFrame fields."""
        frame = self.frame_by_id(frame_id)
        if frame is None:
            return
        for key, value in kwargs.items():
            if hasattr(frame, key):
                setattr(frame, key, value)
        self.frame_updated.emit(frame_id)

    def batch_update(self, frame_ids: list[int], **kwargs) -> None:  # noqa: ANN003
        """Apply the same metadata to multiple frames, auto-incrementing frame_number."""
        for idx, fid in enumerate(frame_ids):
            kw = dict(kwargs)
            if "frame_number" not in kw:
                kw["frame_number"] = idx + 1
            self.update_frame(fid, **kw)
        self.frames_changed.emit()

    def _renumber_named_sequences(self) -> None:
        """Assign contiguous frame_number values per named animation sequence."""
        counts: dict[tuple[str, str, str, str], int] = {}
        for frame in self._frames:
            if not frame.is_fully_named:
                continue
            key = (
                frame.part1,
                frame.part2,
                frame.effective_verb,
                frame.direction.value if frame.direction else "",
            )
            next_number = counts.get(key, 0) + 1
            counts[key] = next_number
            frame.frame_number = next_number

    # ── project persistence ───────────────────────────────────────────────────

    def save_project(self, path: str | Path) -> None:
        """Persist project state to a .spriteproj JSON file."""
        path = Path(path)
        data = {
            "version": 1,
            "source_path": str(self.source_path) if self.source_path else None,
            "sources": [
                {
                    "id": sheet.id,
                    "path": str(sheet.path),
                }
                for sheet in self._sheets
            ],
            "active_sheet_id": self._active_sheet_id,
            "settings": self.settings.to_dict(),
            "frames": [f.to_dict() for f in self._frames],
        }
        path.write_text(json.dumps(data, indent=2), encoding="utf-8")

    def load_project(self, path: str | Path) -> None:
        """Restore project state from a .spriteproj JSON file."""
        path = Path(path)
        data = json.loads(path.read_text(encoding="utf-8"))
        self.settings = DetectionSettings.from_dict(data.get("settings", {}))

        src_list = data.get("sources")
        if src_list:
            src_paths = [entry.get("path") for entry in src_list if entry.get("path")]
            if src_paths:
                self.load_images(src_paths, clear_frames=True)
        else:
            src = data.get("source_path")
            if src:
                self.load_image(src)

        active_sheet_id = data.get("active_sheet_id")
        if isinstance(active_sheet_id, int):
            self.set_active_sheet(active_sheet_id)

        sheet_arrays = {sheet.id: sheet.array for sheet in self._sheets}
        sheet_names = {sheet.id: sheet.path.name for sheet in self._sheets}

        reset_frame_ids()
        frames: list[SpriteFrame] = []
        for fd in data.get("frames", []):
            bbox = BBox(*fd["bbox"])
            frame_sheet_id = fd.get("source_sheet_id", self._active_sheet_id or 0)
            sf = SpriteFrame(
                bbox=bbox,
                source_sheet_id=frame_sheet_id,
                source_sheet_name=fd.get("source_sheet_name", sheet_names.get(frame_sheet_id, "")),
            )
            sf.part1 = fd.get("part1", "")
            sf.part2 = fd.get("part2", "")
            verb_str = fd.get("verb", "")
            try:
                sf.verb = Verb(verb_str) if verb_str else None
            except ValueError:
                sf.custom_verb = verb_str
            dir_str = fd.get("direction")
            sf.direction = Direction(dir_str) if dir_str else None
            sf.frame_number = fd.get("frame_number", 1)
            # crop image data if source loaded
            source_arr = sheet_arrays.get(frame_sheet_id)
            if source_arr is not None:
                sf.image = source_arr[bbox.y:bbox.bottom, bbox.x:bbox.right].copy()
            frames.append(sf)
        self._frames = frames
        self.frames_changed.emit()
        self.project_loaded.emit()
