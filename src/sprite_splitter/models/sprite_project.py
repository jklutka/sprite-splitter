"""Project-level state: source image, detected frames, and project persistence."""

from __future__ import annotations

import json
from dataclasses import dataclass, field
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

    def __init__(self, parent: Optional[QObject] = None) -> None:
        super().__init__(parent)
        self.source_path: Optional[Path] = None
        self.source_array: Optional[np.ndarray] = None   # RGBA uint8, shape H×W×4
        self.settings = DetectionSettings()
        self._frames: list[SpriteFrame] = []

    # ── frame access ──────────────────────────────────────────────────────────

    @property
    def frames(self) -> list[SpriteFrame]:
        return list(self._frames)

    def frame_by_id(self, frame_id: int) -> Optional[SpriteFrame]:
        for f in self._frames:
            if f.id == frame_id:
                return f
        return None

    # ── image loading ─────────────────────────────────────────────────────────

    def load_image(self, path: str | Path) -> None:
        """Load a sprite sheet PNG into the project."""
        path = Path(path)
        if not path.is_file():
            raise FileNotFoundError(f"Image not found: {path}")
        img = Image.open(path).convert("RGBA")
        self.source_path = path
        self.source_array = np.array(img, dtype=np.uint8)
        self._frames.clear()
        reset_frame_ids()
        self.project_loaded.emit()

    # ── frame management ──────────────────────────────────────────────────────

    def set_frames(self, frames: list[SpriteFrame]) -> None:
        """Replace all detected frames (e.g. after running detection)."""
        self._frames = list(frames)
        self.frames_changed.emit()

    def add_frame(self, frame: SpriteFrame) -> None:
        self._frames.append(frame)
        self.frames_changed.emit()

    def remove_frame(self, frame_id: int) -> None:
        self._frames = [f for f in self._frames if f.id != frame_id]
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

    # ── project persistence ───────────────────────────────────────────────────

    def save_project(self, path: str | Path) -> None:
        """Persist project state to a .spriteproj JSON file."""
        path = Path(path)
        data = {
            "version": 1,
            "source_path": str(self.source_path) if self.source_path else None,
            "settings": self.settings.to_dict(),
            "frames": [f.to_dict() for f in self._frames],
        }
        path.write_text(json.dumps(data, indent=2), encoding="utf-8")

    def load_project(self, path: str | Path) -> None:
        """Restore project state from a .spriteproj JSON file."""
        path = Path(path)
        data = json.loads(path.read_text(encoding="utf-8"))
        self.settings = DetectionSettings.from_dict(data.get("settings", {}))
        src = data.get("source_path")
        if src:
            self.load_image(src)
        reset_frame_ids()
        frames: list[SpriteFrame] = []
        for fd in data.get("frames", []):
            bbox = BBox(*fd["bbox"])
            sf = SpriteFrame(bbox=bbox)
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
            if self.source_array is not None:
                sf.image = self.source_array[bbox.y:bbox.bottom, bbox.x:bbox.right].copy()
            frames.append(sf)
        self._frames = frames
        self.frames_changed.emit()
        self.project_loaded.emit()
