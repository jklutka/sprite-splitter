"""Naming convention logic for sprite frames.

File name format:
    {part1}-{part2}-{verb}-{direction}-{NNN}.png

Examples:
    hero-base-walking-east-001.png
    goblin-armored-idle-south-001.png
"""

from __future__ import annotations

from sprite_splitter.models.sprite_frame import SpriteFrame


def generate_filename(frame: SpriteFrame, extension: str = ".png") -> str:
    """Build the canonical output filename for *frame*."""
    return frame.filename_stem + extension


def generate_relative_path(
    frame: SpriteFrame,
    use_folders: bool = False,
    extension: str = ".png",
) -> str:
    """Build possibly nested relative path.

    When *use_folders* is ``True`` the structure is::

        {part1}/{part2}/{verb}/{filename}

    Otherwise just the flat filename.
    """
    fname = generate_filename(frame, extension)
    if not use_folders:
        return fname
    parts: list[str] = []
    if frame.part1:
        parts.append(frame.part1)
    if frame.part2:
        parts.append(frame.part2)
    if frame.effective_verb:
        parts.append(frame.effective_verb)
    parts.append(fname)
    return "/".join(parts)


def auto_number_frames(
    frames: list[SpriteFrame],
    group_key: str | None = None,
) -> None:
    """Assign sequential ``frame_number`` values to *frames*.

    If *group_key* is given (e.g. ``"verb+direction"``), numbering restarts
    for each unique combination of the relevant fields.  Otherwise all
    frames are numbered 1 … N in order.
    """
    if group_key is None:
        for idx, f in enumerate(frames, start=1):
            f.frame_number = idx
        return

    from itertools import groupby

    def _key(f: SpriteFrame) -> tuple:
        return (f.part1, f.part2, f.effective_verb,
                f.direction.value if f.direction else "")

    # Stable sort by the grouping key so groupby works correctly
    frames.sort(key=_key)
    for _k, group in groupby(frames, key=_key):
        for idx, f in enumerate(group, start=1):
            f.frame_number = idx


def find_duplicate_relative_paths(
    frames: list[SpriteFrame],
    use_folders: bool = False,
    extension: str = ".png",
) -> dict[str, int]:
    """Return duplicate export relative paths and their counts."""
    counts: dict[str, int] = {}
    for frame in frames:
        rel = generate_relative_path(frame, use_folders=use_folders, extension=extension)
        counts[rel] = counts.get(rel, 0) + 1
    return {path: count for path, count in counts.items() if count > 1}


def find_duplicate_filenames(
    frames: list[SpriteFrame],
    extension: str = ".png",
) -> dict[str, int]:
    """Return duplicate flat filenames and their counts."""
    counts: dict[str, int] = {}
    for frame in frames:
        name = generate_filename(frame, extension=extension)
        counts[name] = counts.get(name, 0) + 1
    return {name: count for name, count in counts.items() if count > 1}
