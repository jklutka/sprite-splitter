"""Data model for an individual sprite frame detected within a sprite sheet."""

from __future__ import annotations

import enum
from dataclasses import dataclass, field
from typing import Optional

import numpy as np


# ---------------------------------------------------------------------------
# Enums for the structured naming convention
# ---------------------------------------------------------------------------

class Verb(enum.Enum):
    """Action descriptor for a sprite animation."""
    IDLE = "idle"
    WALKING = "walking"
    RUNNING = "running"
    ATTACKING = "attacking"

    @classmethod
    def names(cls) -> list[str]:
        return [v.value for v in cls]


class Direction(enum.Enum):
    """Compass direction the sprite is facing."""
    NORTH = "north"
    NORTHEAST = "northeast"
    EAST = "east"
    SOUTHEAST = "southeast"
    SOUTH = "south"
    SOUTHWEST = "southwest"
    WEST = "west"
    NORTHWEST = "northwest"

    @classmethod
    def names(cls) -> list[str]:
        return [d.value for d in cls]


# ---------------------------------------------------------------------------
# Bounding box helper
# ---------------------------------------------------------------------------

@dataclass(frozen=True)
class BBox:
    """Axis-aligned bounding box (pixel coordinates)."""
    x: int
    y: int
    w: int
    h: int

    @property
    def right(self) -> int:
        return self.x + self.w

    @property
    def bottom(self) -> int:
        return self.y + self.h

    @property
    def area(self) -> int:
        return self.w * self.h

    def to_tuple(self) -> tuple[int, int, int, int]:
        """Return (x, y, w, h)."""
        return (self.x, self.y, self.w, self.h)


# ---------------------------------------------------------------------------
# Sprite Frame
# ---------------------------------------------------------------------------

_next_frame_id: int = 0


def _auto_id() -> int:
    global _next_frame_id
    _next_frame_id += 1
    return _next_frame_id


def reset_frame_ids() -> None:
    """Reset the auto-increment counter (useful for tests)."""
    global _next_frame_id
    _next_frame_id = 0


@dataclass
class SpriteFrame:
    """Represents a single detected sprite frame and its naming metadata."""

    # Geometry ------------------------------------------------------------------
    bbox: BBox

    # Pixel data (RGBA uint8 ndarray, shape H×W×4)  – set after cropping
    image: Optional[np.ndarray] = field(default=None, repr=False)

    # Source sheet metadata ----------------------------------------------------
    source_sheet_id: int = 0
    source_sheet_name: str = ""

    # Naming metadata -----------------------------------------------------------
    part1: str = ""
    part2: str = ""
    verb: Optional[Verb] = None
    custom_verb: str = ""          # used when verb is not one of the built-in enum values
    direction: Optional[Direction] = None
    frame_number: int = 1

    # Internal bookkeeping ------------------------------------------------------
    id: int = field(default_factory=_auto_id)

    # ── helpers ───────────────────────────────────────────────────────────────

    @property
    def is_fully_named(self) -> bool:
        """True when all four naming parts have been assigned."""
        return bool(
            self.part1
            and self.part2
            and (self.verb is not None or self.custom_verb)
            and self.direction is not None
        )

    @property
    def effective_verb(self) -> str:
        """Return the verb string – custom override takes priority."""
        if self.custom_verb:
            return self.custom_verb
        if self.verb is not None:
            return self.verb.value
        return ""

    @property
    def display_name(self) -> str:
        """Human-readable label shown in the UI frame list."""
        if self.is_fully_named:
            return self.filename_stem
        parts: list[str] = []
        if self.part1:
            parts.append(self.part1)
        if self.part2:
            parts.append(self.part2)
        if self.effective_verb:
            parts.append(self.effective_verb)
        if self.direction is not None:
            parts.append(self.direction.value)
        if parts:
            return "-".join(parts)
        return f"frame-{self.id}"

    @property
    def filename_stem(self) -> str:
        """Generate the file stem: part1-part2-verb-direction-NNN"""
        verb_str = self.effective_verb or "unset"
        dir_str = self.direction.value if self.direction else "unset"
        return (
            f"{self.part1 or 'unset'}-{self.part2 or 'unset'}"
            f"-{verb_str}-{dir_str}-{self.frame_number:03d}"
        )

    def to_dict(self) -> dict:
        """Serialise to a JSON-friendly dict (for project save / manifest)."""
        return {
            "id": self.id,
            "bbox": self.bbox.to_tuple(),
            "source_sheet_id": self.source_sheet_id,
            "source_sheet_name": self.source_sheet_name,
            "part1": self.part1,
            "part2": self.part2,
            "verb": self.effective_verb,
            "direction": self.direction.value if self.direction else None,
            "frame_number": self.frame_number,
        }
