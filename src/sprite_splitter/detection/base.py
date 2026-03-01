"""Abstract base interface for sprite detectors."""

from __future__ import annotations

import abc

import numpy as np

from sprite_splitter.models.sprite_frame import SpriteFrame


class BaseDetector(abc.ABC):
    """Strategy interface – all detectors yield a list of SpriteFrame objects."""

    @abc.abstractmethod
    def detect(
        self,
        image: np.ndarray,
        bg_color: tuple[int, int, int],
        tolerance: int,
        **kwargs,
    ) -> list[SpriteFrame]:
        """Detect and return sprite frames from *image* (RGBA uint8)."""
        ...
