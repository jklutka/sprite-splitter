"""Generate a TexturePacker-compatible JSON manifest for exported sprites."""

from __future__ import annotations

import json
from collections import defaultdict
from pathlib import Path

from sprite_splitter.naming.convention import generate_filename
from sprite_splitter.models.sprite_frame import SpriteFrame


def build_manifest(
    frames: list[SpriteFrame],
    source_image_name: str = "spritesheet.png",
    source_size: tuple[int, int] = (0, 0),
) -> dict:
    """Build a TexturePacker JSON-Hash-compatible manifest dict.

    Also includes a custom ``animations`` block that groups frames by
    their part1+part2+verb+direction combination for easy game-engine
    consumption.
    """
    frames_dict: dict[str, dict] = {}
    animations: dict[str, list[str]] = defaultdict(list)

    for f in frames:
        fname = generate_filename(f)
        frames_dict[fname] = {
            "frame": {"x": f.bbox.x, "y": f.bbox.y, "w": f.bbox.w, "h": f.bbox.h},
            "rotated": False,
            "trimmed": False,
            "spriteSourceSize": {"x": 0, "y": 0, "w": f.bbox.w, "h": f.bbox.h},
            "sourceSize": {"w": f.bbox.w, "h": f.bbox.h},
        }

        # Group key for the animation block
        if f.is_fully_named:
            anim_key = (
                f"{f.part1}-{f.part2}-{f.effective_verb}"
                f"-{f.direction.value if f.direction else 'none'}"
            )
            animations[anim_key].append(fname)

    manifest = {
        "frames": frames_dict,
        "animations": dict(animations),
        "meta": {
            "app": "sprite-splitter",
            "version": "1.0.0",
            "image": source_image_name,
            "format": "RGBA8888",
            "size": {"w": source_size[0], "h": source_size[1]},
            "scale": "1",
        },
    }
    return manifest


def write_manifest(
    frames: list[SpriteFrame],
    output_path: str | Path,
    source_image_name: str = "spritesheet.png",
    source_size: tuple[int, int] = (0, 0),
) -> Path:
    """Write the manifest JSON to disk and return its path."""
    output_path = Path(output_path)
    manifest = build_manifest(frames, source_image_name, source_size)
    output_path.write_text(json.dumps(manifest, indent=2), encoding="utf-8")
    return output_path
