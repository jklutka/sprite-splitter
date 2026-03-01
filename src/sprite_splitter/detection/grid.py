"""Grid-based sprite detection – splits the sheet into uniform cells."""

from __future__ import annotations

import numpy as np

from sprite_splitter.detection.background import create_background_mask
from sprite_splitter.detection.base import BaseDetector
from sprite_splitter.models.sprite_frame import BBox, SpriteFrame


class GridDetector(BaseDetector):
    """Splits the sprite sheet into a regular grid and yields non-empty cells.

    Can optionally **auto-detect** grid dimensions by finding uniformly
    spaced rows/columns that consist entirely of the background colour.
    """

    def detect(
        self,
        image: np.ndarray,
        bg_color: tuple[int, int, int],
        tolerance: int = 30,
        *,
        cell_width: int = 0,
        cell_height: int = 0,
        margin: int = 0,
        padding: int = 0,
        auto: bool = False,
        **_kwargs,
    ) -> list[SpriteFrame]:
        """Return a list of SpriteFrame objects for every non-empty grid cell.

        Parameters
        ----------
        cell_width, cell_height
            Size of each cell in pixels.  If *auto* is True these are ignored
            and computed automatically.
        margin
            Outer margin around the entire sheet (pixels).
        padding
            Spacing between cells (pixels).
        auto
            When True, attempt to auto-detect cell dimensions by scanning
            for background-only rows/columns.
        """
        h, w = image.shape[:2]
        bg_mask = create_background_mask(image, bg_color, tolerance)

        if auto or (cell_width <= 0 or cell_height <= 0):
            cell_width, cell_height = self._auto_grid(bg_mask, margin)
            if cell_width <= 0 or cell_height <= 0:
                return []

        frames: list[SpriteFrame] = []
        y = margin
        while y + cell_height <= h - margin:
            x = margin
            while x + cell_width <= w - margin:
                cell_mask = bg_mask[y: y + cell_height, x: x + cell_width]
                # skip completely-background cells
                if not cell_mask.all():
                    bbox = BBox(x, y, cell_width, cell_height)
                    region = image[y: y + cell_height, x: x + cell_width].copy()
                    frames.append(SpriteFrame(bbox=bbox, image=region))
                x += cell_width + padding
            y += cell_height + padding

        return frames

    # ------------------------------------------------------------------
    @staticmethod
    def _auto_grid(
        bg_mask: np.ndarray,
        margin: int,
    ) -> tuple[int, int]:
        """Infer cell dimensions from background-only row/column gaps.

        We find rows that are 100 % background, group consecutive runs,
        then derive the most common interval between run centres.
        """
        h, w = bg_mask.shape

        def _most_common_interval(full_bg: np.ndarray) -> int:
            """Return the dominant spacing between consecutive bg-only lines."""
            indices = np.where(full_bg)[0]
            if len(indices) < 2:
                return 0
            # Find starts of runs
            runs_start: list[int] = [indices[0]]
            for i in range(1, len(indices)):
                if indices[i] != indices[i - 1] + 1:
                    runs_start.append(indices[i])
            if len(runs_start) < 2:
                return int(indices[-1] - indices[0]) if len(indices) > 1 else 0
            diffs = np.diff(runs_start)
            if len(diffs) == 0:
                return 0
            # Most frequent diff
            vals, counts = np.unique(diffs, return_counts=True)
            return int(vals[counts.argmax()])

        row_bg = np.all(bg_mask[margin: h - margin, :], axis=1)
        col_bg = np.all(bg_mask[:, margin: w - margin], axis=0)

        cw = _most_common_interval(col_bg)
        ch = _most_common_interval(row_bg)
        return cw, ch
