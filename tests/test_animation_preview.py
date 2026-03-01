"""Tests for the animation preview module – direction mapping and grouping."""

import math

import numpy as np
import pytest

from sprite_splitter.models.sprite_frame import (
    BBox,
    Direction,
    SpriteFrame,
    Verb,
    reset_frame_ids,
)
from sprite_splitter.ui.animation_preview import (
    _angle_to_direction,
    _mouse_angle,
    build_animation_groups,
)
from PySide6.QtCore import QPointF


# ── angle → direction mapping ────────────────────────────────────────────────


class TestAngleToDirection:
    """Verify that angles (0=north, clockwise) map to the correct Direction."""

    @pytest.mark.parametrize(
        "angle, expected",
        [
            (0, Direction.NORTH),
            (22, Direction.NORTH),       # just inside N sector
            (23, Direction.NORTHEAST),   # just past N boundary
            (45, Direction.NORTHEAST),
            (90, Direction.EAST),
            (135, Direction.SOUTHEAST),
            (180, Direction.SOUTH),
            (225, Direction.SOUTHWEST),
            (270, Direction.WEST),
            (315, Direction.NORTHWEST),
            (350, Direction.NORTH),      # wraps around
            (359, Direction.NORTH),
            (360, Direction.NORTH),      # exactly 360 normalises to 0
        ],
    )
    def test_mapping(self, angle: float, expected: Direction):
        assert _angle_to_direction(angle) == expected


class TestMouseAngle:
    """Verify screen-coords → north-clockwise angle."""

    def test_north(self):
        # mouse directly above centre → 0° (north)
        angle = _mouse_angle(QPointF(100, 100), QPointF(100, 50))
        assert abs(angle - 0) < 1 or abs(angle - 360) < 1

    def test_east(self):
        # mouse directly right of centre → 90° (east)
        angle = _mouse_angle(QPointF(100, 100), QPointF(200, 100))
        assert abs(angle - 90) < 1

    def test_south(self):
        # mouse directly below centre → 180° (south)
        angle = _mouse_angle(QPointF(100, 100), QPointF(100, 200))
        assert abs(angle - 180) < 1

    def test_west(self):
        # mouse directly left of centre → 270° (west)
        angle = _mouse_angle(QPointF(100, 100), QPointF(0, 100))
        assert abs(angle - 270) < 1

    def test_northeast(self):
        # mouse at 45° → ~45° (northeast)
        angle = _mouse_angle(QPointF(100, 100), QPointF(150, 50))
        assert abs(angle - 45) < 1


# ── animation group building ─────────────────────────────────────────────────


class TestBuildAnimationGroups:
    def setup_method(self):
        reset_frame_ids()

    def _make_frame(
        self, part1, part2, verb, direction, frame_number
    ) -> SpriteFrame:
        """Helper to create a fully-named frame with dummy image data."""
        img = np.zeros((16, 16, 4), dtype=np.uint8)
        img[:, :] = [100, 100, 100, 255]
        return SpriteFrame(
            bbox=BBox(0, 0, 16, 16),
            image=img,
            part1=part1,
            part2=part2,
            verb=verb,
            direction=direction,
            frame_number=frame_number,
        )

    def test_basic_grouping(self):
        frames = [
            self._make_frame("hero", "base", Verb.WALKING, Direction.EAST, 1),
            self._make_frame("hero", "base", Verb.WALKING, Direction.EAST, 2),
            self._make_frame("hero", "base", Verb.WALKING, Direction.WEST, 1),
            self._make_frame("hero", "base", Verb.IDLE, Direction.SOUTH, 1),
        ]
        groups = build_animation_groups(frames)

        assert "hero-base" in groups
        assert "walking" in groups["hero-base"]
        assert "idle" in groups["hero-base"]

        walking = groups["hero-base"]["walking"]
        assert Direction.EAST in walking
        assert len(walking[Direction.EAST]) == 2
        assert walking[Direction.EAST][0].frame_number == 1
        assert walking[Direction.EAST][1].frame_number == 2
        assert Direction.WEST in walking
        assert len(walking[Direction.WEST]) == 1

    def test_ignores_unnamed_frames(self):
        frames = [
            SpriteFrame(bbox=BBox(0, 0, 16, 16)),  # unnamed
            self._make_frame("hero", "base", Verb.IDLE, Direction.SOUTH, 1),
        ]
        groups = build_animation_groups(frames)
        assert "hero-base" in groups
        # There should be exactly one entry, the unnamed frame excluded
        total_frames = sum(
            len(fl)
            for entity in groups.values()
            for verb in entity.values()
            for fl in verb.values()
        )
        assert total_frames == 1

    def test_multiple_entities(self):
        frames = [
            self._make_frame("hero", "base", Verb.IDLE, Direction.SOUTH, 1),
            self._make_frame("goblin", "base", Verb.IDLE, Direction.SOUTH, 1),
        ]
        groups = build_animation_groups(frames)
        assert "hero-base" in groups
        assert "goblin-base" in groups

    def test_frame_ordering(self):
        """Frames within a direction should be sorted by frame_number."""
        frames = [
            self._make_frame("hero", "base", Verb.WALKING, Direction.NORTH, 3),
            self._make_frame("hero", "base", Verb.WALKING, Direction.NORTH, 1),
            self._make_frame("hero", "base", Verb.WALKING, Direction.NORTH, 2),
        ]
        groups = build_animation_groups(frames)
        north_frames = groups["hero-base"]["walking"][Direction.NORTH]
        assert [f.frame_number for f in north_frames] == [1, 2, 3]
