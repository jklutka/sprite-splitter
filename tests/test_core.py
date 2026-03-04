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
from sprite_splitter.export.manifest import build_manifest, write_manifest
from sprite_splitter.export.png_exporter import export_all, export_frame
from sprite_splitter.models.sprite_frame import (
    BBox,
    Direction,
    SpriteFrame,
    Verb,
    reset_frame_ids,
)
from sprite_splitter.models.sprite_project import SpriteProject
from sprite_splitter.naming.convention import (
    auto_number_frames,
    find_duplicate_filenames,
    find_duplicate_relative_paths,
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
        assert path == "hero/base/walking/east/hero-base-walking-east-001.png"

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
        assert set(manifest.keys()) == {"character", "assets", "sequence"}
        assert manifest["character"]["part1"] == "hero"
        assert manifest["character"]["part2"] == "base"
        assert manifest["character"]["source_image"] == "sheet.png"
        assert manifest["character"]["source_size"] == {"w": 128, "h": 64}

        assert len(manifest["assets"]) == 2
        first = manifest["assets"][0]
        assert first["file"] == "hero-base-walking-east-001.png"
        assert first["path"] == "hero-base-walking-east-001.png"
        assert first["verb"] == "walking"
        assert first["direction"] == "east"
        assert first["frame_number"] == 1
        assert first["bbox"] == {"x": 0, "y": 0, "w": 32, "h": 32}

        assert manifest["sequence"] == {
            "walking-east": [
                "hero-base-walking-east-001.png",
                "hero-base-walking-east-002.png",
            ]
        }

    def test_manifest_sequence_order_follows_input_order(self):
        f2 = SpriteFrame(
            bbox=BBox(32, 0, 32, 32),
            part1="hero",
            part2="base",
            verb=Verb.WALKING,
            direction=Direction.EAST,
            frame_number=2,
        )
        f1 = SpriteFrame(
            bbox=BBox(0, 0, 32, 32),
            part1="hero",
            part2="base",
            verb=Verb.WALKING,
            direction=Direction.EAST,
            frame_number=1,
        )
        manifest = build_manifest([f2, f1], "sheet.png", (128, 64))
        assert manifest["sequence"]["walking-east"] == [
            "hero-base-walking-east-002.png",
            "hero-base-walking-east-001.png",
        ]

    def test_manifest_assets_use_folder_paths_when_enabled(self):
        frame = SpriteFrame(
            bbox=BBox(0, 0, 32, 32),
            part1="hero",
            part2="base",
            verb=Verb.WALKING,
            direction=Direction.EAST,
            frame_number=1,
        )
        manifest = build_manifest([frame], "sheet.png", (128, 64), use_folders=True)
        assert (
            manifest["assets"][0]["path"]
            == "hero/base/walking/east/hero-base-walking-east-001.png"
        )
        assert manifest["sequence"]["walking-east"] == [
            "hero/base/walking/east/hero-base-walking-east-001.png"
        ]

    def test_manifest_json_handles_numpy_scalar_bbox(self):
        frame = SpriteFrame(
            bbox=BBox(np.int32(0), np.int32(0), np.int32(32), np.int32(32)),
            part1="hero",
            part2="base",
            verb=Verb.WALKING,
            direction=Direction.EAST,
            frame_number=np.int32(1),
        )
        with tempfile.TemporaryDirectory() as tmp:
            manifest_path = write_manifest(
                [frame],
                Path(tmp) / "manifest.json",
                source_image_name="sheet.png",
                source_size=(np.int32(128), np.int32(64)),
                use_folders=False,
            )
            data = json.loads(manifest_path.read_text(encoding="utf-8"))
            asset = data["assets"][0]
            assert asset["frame_number"] == 1
            assert asset["bbox"] == {"x": 0, "y": 0, "w": 32, "h": 32}

    def test_manifest_raises_for_mixed_character_identity(self):
        frames = [
            SpriteFrame(
                bbox=BBox(0, 0, 32, 32),
                part1="hero",
                part2="base",
                verb=Verb.IDLE,
                direction=Direction.SOUTH,
                frame_number=1,
            ),
            SpriteFrame(
                bbox=BBox(32, 0, 32, 32),
                part1="goblin",
                part2="base",
                verb=Verb.IDLE,
                direction=Direction.SOUTH,
                frame_number=2,
            ),
        ]
        with pytest.raises(ValueError, match="one character identity"):
            build_manifest(frames, "sheet.png", (128, 64))

    def test_export_all_raises_when_frame_is_missing_image(self):
        frame = SpriteFrame(
            bbox=BBox(0, 0, 32, 32),
            image=None,
            part1="hero",
            part2="base",
            verb=Verb.IDLE,
            direction=Direction.SOUTH,
            frame_number=1,
        )
        with tempfile.TemporaryDirectory() as tmp:
            with pytest.raises(ValueError, match="has no image data"):
                export_all([frame], Path(tmp), BG, tolerance=10)

    def test_export_integration_writes_images_and_manifest(self):
        img = _make_sheet_grid(1, 2, 32, 32)
        f1 = SpriteFrame(
            bbox=BBox(0, 0, 32, 32),
            image=img[0:32, 0:32].copy(),
            part1="hero",
            part2="base",
            verb=Verb.WALKING,
            direction=Direction.EAST,
            frame_number=1,
        )
        f2 = SpriteFrame(
            bbox=BBox(32, 0, 32, 32),
            image=img[0:32, 32:64].copy(),
            part1="hero",
            part2="base",
            verb=Verb.WALKING,
            direction=Direction.EAST,
            frame_number=2,
        )

        with tempfile.TemporaryDirectory() as tmp:
            out = Path(tmp)
            paths = export_all([f1, f2], out, BG, tolerance=10, use_folders=False)
            manifest_path = write_manifest(
                [f1, f2],
                out / "manifest.json",
                source_image_name="sheet.png",
                source_size=(64, 32),
                use_folders=False,
            )
            paths.append(manifest_path)

            assert len(paths) == 3
            assert (out / "hero-base-walking-east-001.png").exists()
            assert (out / "hero-base-walking-east-002.png").exists()
            assert manifest_path.exists()
            data = json.loads(manifest_path.read_text(encoding="utf-8"))
            assert data["sequence"]["walking-east"] == [
                "hero-base-walking-east-001.png",
                "hero-base-walking-east-002.png",
            ]

    def test_export_all_raises_on_duplicate_relative_paths(self):
        img = _make_sheet_grid(1, 1, 32, 32)
        frame1 = SpriteFrame(
            bbox=BBox(0, 0, 32, 32),
            image=img[0:32, 0:32].copy(),
            part1="hero",
            part2="base",
            verb=Verb.IDLE,
            direction=Direction.SOUTH,
            frame_number=1,
        )
        frame2 = SpriteFrame(
            bbox=BBox(0, 0, 32, 32),
            image=img[0:32, 0:32].copy(),
            part1="hero",
            part2="base",
            verb=Verb.IDLE,
            direction=Direction.SOUTH,
            frame_number=1,
        )
        with tempfile.TemporaryDirectory() as tmp:
            with pytest.raises(ValueError, match="duplicate output file paths"):
                export_all([frame1, frame2], Path(tmp), BG, tolerance=10, use_folders=True)


class TestProjectFrameReorder:
    def setup_method(self):
        reset_frame_ids()

    def _named_frame(self, frame_number: int) -> SpriteFrame:
        return SpriteFrame(
            bbox=BBox(0, 0, 32, 32),
            part1="hero",
            part2="base",
            verb=Verb.WALKING,
            direction=Direction.EAST,
            frame_number=frame_number,
        )

    def test_reorder_swaps_sequence_numbers(self):
        project = SpriteProject()
        f1 = self._named_frame(1)
        f2 = self._named_frame(2)
        f3 = self._named_frame(3)
        project.set_frames([f1, f2, f3])

        project.reorder_frames([f1.id, f3.id, f2.id])

        ordered = project.frames
        assert [f.id for f in ordered] == [f1.id, f3.id, f2.id]
        assert f1.frame_number == 1
        assert f3.frame_number == 2
        assert f2.frame_number == 3

    def test_reorder_numbers_each_group_independently(self):
        project = SpriteProject()
        e1 = self._named_frame(1)
        e2 = self._named_frame(2)
        s1 = SpriteFrame(
            bbox=BBox(0, 0, 32, 32),
            part1="hero",
            part2="base",
            verb=Verb.WALKING,
            direction=Direction.SOUTH,
            frame_number=7,
        )
        project.set_frames([e1, e2, s1])

        project.reorder_frames([e2.id, s1.id, e1.id])

        assert e2.frame_number == 1
        assert e1.frame_number == 2
        assert s1.frame_number == 1

    def test_normalize_named_sequence_numbers_resolves_duplicates(self):
        project = SpriteProject()
        f1 = self._named_frame(5)
        f2 = self._named_frame(5)
        f3 = self._named_frame(9)
        project.set_frames([f1, f2, f3])

        changed = project.normalize_named_sequence_numbers()

        assert changed is True
        assert [f.frame_number for f in project.frames] == [1, 2, 3]


class TestProjectFrameClone:
    def setup_method(self):
        reset_frame_ids()

    def test_clone_frame_creates_new_instance(self):
        project = SpriteProject()
        img = np.zeros((8, 8, 4), dtype=np.uint8)
        img[:, :] = [10, 20, 30, 255]
        source = SpriteFrame(bbox=BBox(1, 2, 8, 8), image=img)
        project.set_frames([source])

        clone = project.clone_frame(source.id)

        assert clone is not None
        assert clone.id != source.id
        assert clone.bbox == source.bbox
        assert clone.image is not None
        assert source.image is not None
        assert np.array_equal(clone.image, source.image)
        assert clone.image is not source.image
        assert len(project.frames) == 2


class TestDuplicateNameDetection:
    def setup_method(self):
        reset_frame_ids()

    def _frame(self, frame_number: int) -> SpriteFrame:
        return SpriteFrame(
            bbox=BBox(0, 0, 32, 32),
            part1="hero",
            part2="base",
            verb=Verb.WALKING,
            direction=Direction.EAST,
            frame_number=frame_number,
        )

    def test_duplicate_relative_paths(self):
        f1 = self._frame(2)
        f2 = self._frame(2)
        dup = find_duplicate_relative_paths([f1, f2], use_folders=False)
        assert dup == {"hero-base-walking-east-002.png": 2}

    def test_duplicate_filenames(self):
        f1 = self._frame(4)
        f2 = self._frame(4)
        dup = find_duplicate_filenames([f1, f2])
        assert dup == {"hero-base-walking-east-004.png": 2}
