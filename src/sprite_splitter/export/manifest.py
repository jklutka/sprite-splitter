"""Generate character/asset/sequence JSON manifests for exported sprites."""

from __future__ import annotations

import json
from pathlib import Path

from sprite_splitter.naming.convention import generate_filename, generate_relative_path
from sprite_splitter.models.sprite_frame import SpriteFrame


def build_manifest(
    frames: list[SpriteFrame],
    source_image_name: str = "spritesheet.png",
    source_size: tuple[int, int] = (0, 0),
    use_folders: bool = False,
) -> dict:
    """Build a manifest with ``character``, ``assets``, and ``sequence`` blocks."""
    if not frames:
        raise ValueError("Cannot build manifest: no frames provided.")

    identity_set = {(f.part1, f.part2) for f in frames if f.is_fully_named}
    if len(identity_set) != 1:
        raise ValueError(
            "Cannot build manifest: export must contain exactly one character identity "
            "(part1 + part2)."
        )
    part1, part2 = next(iter(identity_set))

    assets: list[dict] = []
    sequence: dict[str, list[str]] = {}

    for frame in frames:
        if not frame.is_fully_named:
            raise ValueError(
                f"Cannot build manifest: frame {frame.id} is missing naming metadata."
            )
        if frame.direction is None:
            raise ValueError(
                f"Cannot build manifest: frame {frame.id} is missing direction."
            )

        filename = generate_filename(frame)
        relative_path = generate_relative_path(frame, use_folders=use_folders)
        sequence_key = f"{frame.effective_verb}-{frame.direction.value}"

        assets.append(
            {
                "file": filename,
                "path": relative_path,
                "part1": frame.part1,
                "part2": frame.part2,
                "verb": frame.effective_verb,
                "direction": frame.direction.value,
                "frame_number": frame.frame_number,
                "bbox": {
                    "x": frame.bbox.x,
                    "y": frame.bbox.y,
                    "w": frame.bbox.w,
                    "h": frame.bbox.h,
                },
            }
        )
        sequence.setdefault(sequence_key, []).append(filename)

    return {
        "character": {
            "part1": part1,
            "part2": part2,
            "source_image": source_image_name,
            "source_size": {"w": source_size[0], "h": source_size[1]},
        },
        "assets": assets,
        "sequence": sequence,
    }


def write_manifest(
    frames: list[SpriteFrame],
    output_path: str | Path,
    source_image_name: str = "spritesheet.png",
    source_size: tuple[int, int] = (0, 0),
    use_folders: bool = False,
) -> Path:
    """Write the manifest JSON to disk and return its path."""
    output_path = Path(output_path)
    manifest = build_manifest(
        frames,
        source_image_name=source_image_name,
        source_size=source_size,
        use_folders=use_folders,
    )
    output_path.write_text(json.dumps(manifest, indent=2), encoding="utf-8")
    return output_path
