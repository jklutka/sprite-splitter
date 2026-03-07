# Sprite Splitter

A desktop utility to **detect**, **organize**, **name**, and **export** individual sprite frames from PNG sprite sheets with a solid-colour background (e.g. magenta).

![Python 3.11+](https://img.shields.io/badge/python-3.11%2B-blue)
![License: MIT](https://img.shields.io/badge/license-MIT-green)

---

## Features

| Feature | Description |
|---|---|
| **Character-first workflow** | Name your character (entity + variant) before loading sheets; identity persists in a header bar throughout the session |
| **Auto-detect sprites** | Connected-component analysis (OpenCV) for irregular layouts, or uniform grid splitting |
| **Multi-sheet processing** | Import multiple sheets at once, detect all in one run, and keep source-sheet context per frame |
| **Background removal** | Tolerance-based transparency with soft anti-aliased edges |
| **Visual canvas** | Zoom (Ctrl+scroll), pan (middle-click), overlay rectangles for detected frames |
| **Frame bbox editing** | Drag the edge or corner of any selected frame rect to resize its bounding box after detection |
| **Name organizer** | Structured naming: `{part1}-{part2}-{verb}-{direction}-{NNN}.png` |
| **Batch assignment** | Select multiple frames → assign verb/direction → auto-number |
| **Animated GIF export** | Export each named sequence as a self-contained `.gif` with configurable FPS |
| **JSON manifest** | Character-centric JSON with `character`, `assets`, and `sequence` blocks |
| **Project save/load** | Persist work-in-progress as `.spriteproj` files |

## Naming Convention

Files are named with four user-controlled segments plus an auto-incremented frame number:

```
{part1}-{part2}-{verb}-{direction}-{NNN}.png
```

| Segment | Examples |
|---|---|
| **part1** | `hero`, `goblin`, `npc` |
| **part2** | `base`, `armored`, `mage` |
| **verb** | `idle`, `walking`, `running`, `attacking` (or custom) |
| **direction** | `north`, `northeast`, `east`, `southeast`, `south`, `southwest`, `west`, `northwest` |
| **NNN** | `001`, `002`, … (animation frame index) |

Example output:
```
hero-base-walking-east-001.png
hero-base-walking-east-002.png
hero-base-idle-south-001.png
```

## Installation

```bash
# Clone or download the project
cd sprite-splitter

# Create a virtual environment (recommended)
python -m venv .venv
.venv\Scripts\activate      # Windows
# source .venv/bin/activate  # macOS/Linux

# Install in editable (development) mode
pip install -e ".[dev]"
```

### Dependencies

| Package | Purpose |
|---|---|
| PySide6 | Qt6 GUI framework (LGPL) |
| Pillow | Image I/O and PNG export |
| NumPy | Fast pixel-level operations |
| opencv-python-headless | Connected-component sprite detection |

## Usage

```bash
# Launch the GUI
sprite-splitter

# Or run directly
python -m sprite_splitter.main
```

### Quick Start

1. **New Character** – enter an entity name (`part1`) and variant (`part2`) on the start screen
2. **File → Open Sprite Sheet(s)** – load one or more sheets with a solid-colour background
3. Click **Auto** to detect the background colour, or use **Pick…** to choose manually
4. Adjust **Tolerance** if needed (higher = more aggressive background matching)
5. Choose **Auto-detect (contour)** or **Grid** mode in the Settings panel
6. Click **Detect Sprites** – all loaded sheets are processed in one run; the guided wizard opens automatically
7. **Review step** – deselect any false positives, then click Next
8. **Identity step** – entity name and variant are pre-filled from your character; adjust if needed
9. **Sort step** – pick a verb, select frames, click a compass direction to assign; frames stay available for reuse across directions
10. After the wizard, use **View → Switch Active Sheet…** to inspect overlays per sheet on the canvas
11. **Resize a frame** – click a frame rect on the canvas to select it, then drag any edge or corner to adjust its bounding box
12. Use **Move Up / Move Down** or drag-and-drop in the sidebar to reorder frames (numbers auto-adjust)
13. Click **Export →** in the header bar (or **File → Export Sprites…** / Ctrl+E) – choose Individual PNGs or Animated GIFs, set output folder, click OK

> Note: Export auto-normalizes frame numbering per sequence and requires one character identity (`part1` + `part2`) per export run.
> Note: Export aborts if duplicate naming would produce the same output path.

### Keyboard Shortcuts

| Shortcut | Action |
|---|---|
| Ctrl+Shift+N | New Character |
| Ctrl+O | Open sprite sheet |
| Ctrl+S | Save project |
| Ctrl+E | Export sprites |
| Ctrl+N | Assign name to selected frames |
| Ctrl+P | Toggle animation preview panel |
| Ctrl+D | Toggle direction panel |
| Ctrl+Shift+Up | Expand animation preview |
| Ctrl+Shift+Down | Shrink animation preview |
| Alt+Up / Alt+Down | Move selected frame up/down in sequence |
| Delete | Remove selected frames |
| Ctrl+Scroll | Zoom canvas |
| Middle-click drag | Pan canvas |
| Drag frame edge/corner | Resize selected frame bounding box |

## Export Format

Two formats are available in the Export dialog:

### Individual PNGs + manifest.json

Each frame is exported as an RGBA PNG with the background colour replaced by full transparency. Optional sub-folder organisation:

```
output/
├── hero/base/walking/east/hero-base-walking-east-001.png
├── hero/base/walking/east/hero-base-walking-east-002.png
└── hero/base/idle/south/hero-base-idle-south-001.png
```

### Animated GIFs

Exports one `.gif` per named sequence (e.g. `hero-base-walking-east.gif`). Playback speed is configurable (1–30 FPS) in the Export dialog. Useful for web, Discord, and tools that expect a single animation file per sequence.

### manifest.json

The PNG export also writes a character-focused manifest:

```json
{
  "character": {
    "part1": "hero",
    "part2": "base",
    "source_image": "spritesheet.png",
    "source_size": {"w": 256, "h": 256}
  },
  "assets": [
    {
      "file": "hero-base-walking-east-001.png",
      "path": "hero/base/walking/east/hero-base-walking-east-001.png",
      "part1": "hero",
      "part2": "base",
      "verb": "walking",
      "direction": "east",
      "frame_number": 1,
      "bbox": {"x": 0, "y": 0, "w": 32, "h": 48}
    }
  ],
  "sequence": {
    "walking-east": [
      "hero/base/walking/east/hero-base-walking-east-001.png",
      "hero/base/walking/east/hero-base-walking-east-002.png"
    ]
  }
}
```

## Development

```bash
# Run tests
pytest tests/ -v

# Run the app without installing
python -m sprite_splitter.main
```

## Branding / App Logo

To use a custom app logo (window icon + large About dialog image), place this file in the project:

```
src/sprite_splitter/assets/app_logo.png
```

Recommended: square PNG at 512×512 or larger.

## License

MIT
