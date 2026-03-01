"""Unit tests for detection, background removal, naming, and manifest."""

import json
import tempfile
from pathlib import Path

import numpy as np
import pytest

from sprite_splitter.detection.background import (
    apply_transparency,
    create_background_mask,
    detect_background_color,
)
from sprite_splitter.detection.contour import ContourDetector
from sprite_splitter.detection.grid import GridDetector
from sprite_splitter.export.manifest import build_manifest
from sprite_splitter.export.png_exporter import export_frame
from sprite_splitter.models.sprite_frame import (
    BBox,
    Direction,
    SpriteFrame,
    Verb,
    reset_frame_ids,
)
from sprite_splitter.naming.convention import (
    auto_number_frames,
    generate_filename,
    generate_relative_path,
)


# ── helpers ──────────────────────────────────────────────────────────────────

BG = (255, 0, 255)  # magenta background


def _make_sheet_grid(
    rows: int = 3,
    cols: int = 4,
    cell_w: int = 32,
    cell_h: int = 32,
) -> np.ndarray:
    """Create a synthetic sprite sheet with a magenta background and
    solid-coloured rectangles as 'sprites'."""
    h = rows * cell_h
    w = cols * cell_w
    img = np.zeros((h, w, 4), dtype=np.uint8)
    # fill background
    img[:, :, 0] = BG[0]
    img[:, :, 1] = BG[1]
    img[:, :, 2] = BG[2]
    img[:, :, 3] = 255

    # draw 'sprites' inside each cell (inset by 4px)
    for r in range(rows):
        for c in range(cols):
            y0 = r * cell_h + 4
            y1 = (r + 1) * cell_h - 4
            x0 = c * cell_w + 4
            x1 = (c + 1) * cell_w - 4
            # Different colour per sprite so they're distinguishable
            img[y0:y1, x0:x1] = [60 + c * 30, 80 + r * 40, 120, 255]

    return img


def _make_sheet_irregular() -> np.ndarray:
    """Create a sheet with three irregular blobs on magenta background."""
    h, w = 128, 128
    img = np.zeros((h, w, 4), dtype=np.uint8)
    img[:, :, :3] = BG
    img[:, :, 3] = 255

    # blob 1 – top-left 20×20
    img[10:30, 10:30] = [100, 100, 200, 255]
    # blob 2 – center 15×25
    img[50:75, 55:70] = [200, 100, 100, 255]
    # blob 3 – bottom-right 10×10
    img[100:110, 100:110] = [100, 200, 100, 255]

    return img


# ── background tests ─────────────────────────────────────────────────────────


class TestBackgroundDetection:
    def test_detect_background_color(self):
        img = _make_sheet_grid()
        assert detect_background_color(img) == BG

    def test_create_background_mask(self):
        img = _make_sheet_grid(1, 1, 32, 32)
        mask = create_background_mask(img, BG, tolerance=10)
        # Corners should be background
        assert mask[0, 0]
        assert mask[0, 31]
        # Centre of sprite should NOT be background
        assert not mask[16, 16]

    def test_apply_transparency(self):
        img = _make_sheet_grid(1, 1, 32, 32)
        result = apply_transparency(img, BG, tolerance=10)
        # Background pixel should be transparent
        assert result[0, 0, 3] == 0
        # Sprite pixel should be opaque
        assert result[16, 16, 3] == 255


# ── grid detection tests ─────────────────────────────────────────────────────


class TestGridDetector:
    def setup_method(self):
        reset_frame_ids()

    def test_grid_detect_known_cells(self):
        img = _make_sheet_grid(3, 4, 32, 32)
        det = GridDetector()
        frames = det.detect(img, BG, tolerance=10, cell_width=32, cell_height=32)
        assert len(frames) == 12  # 3 rows × 4 cols, all non-empty

    def test_grid_detect_with_empty_cells(self):
        img = _make_sheet_grid(2, 2, 32, 32)
        # Make one cell entirely background (erase the sprite)
        img[4:28, 4:28] = [*BG, 255]
        det = GridDetector()
        frames = det.detect(img, BG, tolerance=10, cell_width=32, cell_height=32)
        assert len(frames) == 3  # one cell is now empty


# ── contour detection tests ──────────────────────────────────────────────────


class TestContourDetector:
    def setup_method(self):
        reset_frame_ids()

    def test_contour_detect_irregular(self):
        img = _make_sheet_irregular()
        det = ContourDetector()
        frames = det.detect(img, BG, tolerance=10, min_area=10)
        assert len(frames) == 3

    def test_contour_sorted_order(self):
        img = _make_sheet_irregular()
        det = ContourDetector()
        frames = det.detect(img, BG, tolerance=10, min_area=10)
        # Should be sorted top→bottom, left→right
        ys = [f.bbox.y for f in frames]
        assert ys == sorted(ys)


# ── naming tests ─────────────────────────────────────────────────────────────


class TestNaming:
    def setup_method(self):
        reset_frame_ids()

    def test_generate_filename(self):
        f = SpriteFrame(
            bbox=BBox(0, 0, 32, 32),
            part1="hero",
            part2="base",
            verb=Verb.WALKING,
            direction=Direction.EAST,
            frame_number=3,
        )
        assert generate_filename(f) == "hero-base-walking-east-003.png"

    def test_generate_relative_path_flat(self):
        f = SpriteFrame(
            bbox=BBox(0, 0, 32, 32),
            part1="hero",
            part2="base",
            verb=Verb.IDLE,
            direction=Direction.SOUTH,
            frame_number=1,
        )
        assert generate_relative_path(f, use_folders=False) == "hero-base-idle-south-001.png"

    def test_generate_relative_path_folders(self):
        f = SpriteFrame(
            bbox=BBox(0, 0, 32, 32),
            part1="hero",
            part2="base",
            verb=Verb.WALKING,
            direction=Direction.EAST,
            frame_number=1,
        )
        path = generate_relative_path(f, use_folders=True)
        assert path == "hero/base/walking/hero-base-walking-east-001.png"

    def test_custom_verb(self):
        f = SpriteFrame(
            bbox=BBox(0, 0, 32, 32),
            part1="hero",
            part2="base",
            custom_verb="casting",
            direction=Direction.NORTH,
            frame_number=1,
        )
        assert generate_filename(f) == "hero-base-casting-north-001.png"

    def test_auto_number_frames(self):
        frames = [
            SpriteFrame(bbox=BBox(0, 0, 32, 32)),
            SpriteFrame(bbox=BBox(32, 0, 32, 32)),
            SpriteFrame(bbox=BBox(64, 0, 32, 32)),
        ]
        auto_number_frames(frames)
        assert [f.frame_number for f in frames] == [1, 2, 3]


# ── export tests (integration) ──────────────────────────────────────────────


class TestExport:
    def setup_method(self):
        reset_frame_ids()

    def test_export_frame_creates_png(self):
        img = _make_sheet_grid(1, 1, 32, 32)
        region = img[4:28, 4:28].copy()
        frame = SpriteFrame(
            bbox=BBox(4, 4, 24, 24),
            image=region,
            part1="hero",
            part2="base",
            verb=Verb.IDLE,
            direction=Direction.SOUTH,
            frame_number=1,
        )
        with tempfile.TemporaryDirectory() as tmp:
            path = export_frame(frame, Path(tmp), BG, tolerance=10)
            assert path.exists()
            assert path.name == "hero-base-idle-south-001.png"

    def test_manifest_structure(self):
        frames = [
            SpriteFrame(
                bbox=BBox(0, 0, 32, 32),
                part1="hero",
                part2="base",
                verb=Verb.WALKING,
                direction=Direction.EAST,
                frame_number=1,
            ),
            SpriteFrame(
                bbox=BBox(32, 0, 32, 32),
                part1="hero",
                part2="base",
                verb=Verb.WALKING,
                direction=Direction.EAST,
                frame_number=2,
            ),
        ]
        manifest = build_manifest(frames, "sheet.png", (128, 64))
        assert "hero-base-walking-east-001.png" in manifest["frames"]
        assert "hero-base-walking-east-002.png" in manifest["frames"]
        assert "hero-base-walking-east" in manifest["animations"]
        assert len(manifest["animations"]["hero-base-walking-east"]) == 2
        assert manifest["meta"]["app"] == "sprite-splitter"
