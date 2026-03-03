"""Export detected frames as individual transparent PNGs."""

from __future__ import annotations

from pathlib import Path

from PIL import Image

from sprite_splitter.detection.background import apply_transparency
from sprite_splitter.naming.convention import generate_relative_path
from sprite_splitter.models.sprite_frame import SpriteFrame


def export_frame(
    frame: SpriteFrame,
    output_dir: Path,
    bg_color: tuple[int, int, int],
    tolerance: int = 30,
    use_folders: bool = False,
) -> Path:
    """Export a single sprite frame as an RGBA PNG with transparency.

    Returns the path of the written file.
    """
    if frame.image is None:
        raise ValueError(f"Frame {frame.id} has no image data.")

    transparent = apply_transparency(frame.image, bg_color, tolerance)
    rel = generate_relative_path(frame, use_folders=use_folders)
    dest = output_dir / rel
    dest.parent.mkdir(parents=True, exist_ok=True)

    pil_img = Image.fromarray(transparent, "RGBA")
    pil_img.save(str(dest), "PNG")
    return dest


def export_all(
    frames: list[SpriteFrame],
    output_dir: str | Path,
    bg_color: tuple[int, int, int],
    tolerance: int = 30,
    use_folders: bool = False,
) -> list[Path]:
    """Export every frame and return the list of written paths."""
    output_dir = Path(output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)
    paths: list[Path] = []
    for frame in frames:
        p = export_frame(frame, output_dir, bg_color, tolerance, use_folders)
        paths.append(p)
    return paths
