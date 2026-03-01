"""Connected-component / contour-based sprite detection (irregular layout)."""

from __future__ import annotations

import cv2
import numpy as np

from sprite_splitter.detection.background import create_background_mask
from sprite_splitter.detection.base import BaseDetector
from sprite_splitter.models.sprite_frame import BBox, SpriteFrame


class ContourDetector(BaseDetector):
    """Detect sprites using OpenCV connected-component analysis.

    Works on arbitrarily-packed sheets where sprites are separated by
    the solid background colour.
    """

    def detect(
        self,
        image: np.ndarray,
        bg_color: tuple[int, int, int],
        tolerance: int = 30,
        *,
        min_area: int = 16,
        padding: int = 1,
        **_kwargs,
    ) -> list[SpriteFrame]:
        """Return a list of SpriteFrame objects for every detected sprite.

        Parameters
        ----------
        min_area
            Ignore connected components smaller than this (noise filter).
        padding
            Extra pixels added around each bounding box to avoid clipping.
        """
        h, w = image.shape[:2]
        bg_mask = create_background_mask(image, bg_color, tolerance)

        # Foreground mask: 255 where sprite pixels are
        fg = (~bg_mask).astype(np.uint8) * 255

        # Connected component analysis (8-connectivity)
        num_labels, labels, stats, _centroids = cv2.connectedComponentsWithStats(
            fg, connectivity=8, ltype=cv2.CV_32S,
        )

        frames: list[SpriteFrame] = []
        for i in range(1, num_labels):  # skip label 0 (background)
            area = stats[i, cv2.CC_STAT_AREA]
            if area < min_area:
                continue

            bx = max(stats[i, cv2.CC_STAT_LEFT] - padding, 0)
            by = max(stats[i, cv2.CC_STAT_TOP] - padding, 0)
            bw = min(stats[i, cv2.CC_STAT_WIDTH] + 2 * padding, w - bx)
            bh = min(stats[i, cv2.CC_STAT_HEIGHT] + 2 * padding, h - by)

            bbox = BBox(bx, by, bw, bh)
            region = image[by: by + bh, bx: bx + bw].copy()
            frames.append(SpriteFrame(bbox=bbox, image=region))

        # Sort top-to-bottom, left-to-right for consistent ordering
        frames.sort(key=lambda f: (f.bbox.y, f.bbox.x))
        return frames
