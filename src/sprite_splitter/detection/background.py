"""Background colour detection and transparency application."""

from __future__ import annotations

from collections import Counter
from typing import Optional

import numpy as np


def detect_background_color(
    image: np.ndarray,
    sample_size: int = 64,
) -> tuple[int, int, int]:
    """Auto-detect the solid background colour by sampling image corners.

    Parameters
    ----------
    image : np.ndarray
        RGBA or RGB image, shape (H, W, C).
    sample_size : int
        How many pixels to sample along each edge from each corner.

    Returns
    -------
    tuple[int, int, int]
        The most frequent (R, G, B) colour among corner samples.
    """
    h, w = image.shape[:2]
    s = min(sample_size, h, w)
    corners = [
        image[:s, :s],          # top-left
        image[:s, w - s:],      # top-right
        image[h - s:, :s],      # bottom-left
        image[h - s:, w - s:],  # bottom-right
    ]
    pixels = np.concatenate([c.reshape(-1, image.shape[2]) for c in corners], axis=0)
    # Only look at RGB
    rgb = [tuple(int(v) for v in p[:3]) for p in pixels]
    counter = Counter(rgb)
    return counter.most_common(1)[0][0]


def create_background_mask(
    image: np.ndarray,
    bg_color: tuple[int, int, int],
    tolerance: int = 30,
) -> np.ndarray:
    """Return a boolean mask where ``True`` = background pixel.

    Uses Euclidean distance in RGB space with the given tolerance.
    """
    rgb = image[:, :, :3].astype(np.float32)
    bg = np.array(bg_color, dtype=np.float32)
    dist = np.linalg.norm(rgb - bg, axis=2)
    return dist <= tolerance  # type: ignore[return-value]


def apply_transparency(
    image: np.ndarray,
    bg_color: tuple[int, int, int],
    tolerance: int = 30,
    soft_edge: bool = True,
) -> np.ndarray:
    """Replace the solid background colour with transparency.

    Parameters
    ----------
    image : np.ndarray
        RGBA uint8 array, shape (H, W, 4).
    bg_color : tuple[int, int, int]
        Background colour to remove.
    tolerance : int
        Euclidean distance threshold in RGB space.
    soft_edge : bool
        If ``True``, pixels near the threshold get semi-transparent alpha
        for smoother anti-aliased edges.

    Returns
    -------
    np.ndarray
        A new RGBA array with background pixels made transparent.
    """
    out = image.copy()
    rgb = out[:, :, :3].astype(np.float32)
    bg = np.array(bg_color, dtype=np.float32)
    dist = np.linalg.norm(rgb - bg, axis=2)

    exact_mask = dist <= (tolerance * 0.5)
    out[exact_mask, 3] = 0

    if soft_edge:
        edge_mask = (dist > tolerance * 0.5) & (dist <= tolerance)
        # Linearly ramp alpha from 0 → 255 across the edge band
        if np.any(edge_mask):
            alpha_frac = (dist[edge_mask] - tolerance * 0.5) / (tolerance * 0.5 + 1e-6)
            alpha_frac = np.clip(alpha_frac, 0.0, 1.0)
            out[edge_mask, 3] = (alpha_frac * 255).astype(np.uint8)
    else:
        out[dist <= tolerance, 3] = 0

    return out
