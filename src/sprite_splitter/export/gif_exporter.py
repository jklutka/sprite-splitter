"""Export named sprite sequences as animated GIFs."""

from __future__ import annotations

from pathlib import Path

from PIL import Image

from sprite_splitter.detection.background import apply_transparency
from sprite_splitter.models.sprite_frame import SpriteFrame


def export_sequence_as_gif(
    frames: list[SpriteFrame],
    output_path: Path,
    bg_color: tuple[int, int, int],
    tolerance: int = 30,
    fps: int = 12,
) -> Path:
    """Export a sorted list of frames as a single animated GIF.

    Returns the path of the written file.
    """
    if not frames:
        raise ValueError("Cannot export GIF: no frames provided.")

    output_path.parent.mkdir(parents=True, exist_ok=True)

    pil_images: list[Image.Image] = []
    for frame in frames:
        if frame.image is None:
            raise ValueError(f"Frame {frame.id} has no image data.")
        transparent = apply_transparency(frame.image, bg_color, tolerance, soft_edge=False)
        pil_images.append(Image.fromarray(transparent, "RGBA"))

    duration = int(1000 / fps)
    pil_images[0].save(
        str(output_path),
        format="GIF",
        save_all=True,
        append_images=pil_images[1:],
        loop=0,
        duration=duration,
        disposal=2,
    )
    return output_path


def export_all_as_gif(
    frames: list[SpriteFrame],
    output_dir: str | Path,
    bg_color: tuple[int, int, int],
    tolerance: int = 30,
    fps: int = 12,
    use_folders: bool = False,
) -> list[Path]:
    """Export every named sequence as an animated GIF.

    Groups frames by (verb, direction), sorts by frame_number within each group,
    and writes one .gif file per sequence. Returns the list of written paths.
    """
    output_dir = Path(output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)

    # Group frames by sequence key
    sequences: dict[tuple, list[SpriteFrame]] = {}
    for frame in frames:
        if not frame.is_fully_named:
            continue
        key = (frame.part1, frame.part2, frame.effective_verb, frame.direction)
        sequences.setdefault(key, []).append(frame)

    if not sequences:
        raise ValueError("No fully named frames to export.")

    paths: list[Path] = []
    for (part1, part2, verb, direction) in sequences:
        group = sorted(sequences[(part1, part2, verb, direction)], key=lambda f: f.frame_number)
        dir_value = direction.value if direction is not None else "none"
        stem = f"{part1}-{part2}-{verb}-{dir_value}"
        filename = stem + ".gif"

        if use_folders:
            rel_dir = Path(part1) / part2 / verb / dir_value
            dest = output_dir / rel_dir / filename
        else:
            dest = output_dir / filename

        path = export_sequence_as_gif(group, dest, bg_color, tolerance, fps)
        paths.append(path)

    return paths
