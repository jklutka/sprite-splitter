# Sprite Splitter

A desktop utility to **detect**, **organize**, **name**, and **export** individual sprite frames from PNG sprite sheets with a solid-colour background (e.g. magenta).

![Python 3.11+](https://img.shields.io/badge/python-3.11%2B-blue)
![License: MIT](https://img.shields.io/badge/license-MIT-green)

---

## Features

| Feature | Description |
|---|---|
| **Auto-detect sprites** | Connected-component analysis (OpenCV) for irregular layouts, or uniform grid splitting |
| **Background removal** | Tolerance-based transparency with soft anti-aliased edges |
| **Visual canvas** | Zoom (Ctrl+scroll), pan (middle-click), overlay rectangles for detected frames |
| **Name organizer** | Structured naming: `{part1}-{part2}-{verb}-{direction}-{NNN}.png` |
| **Batch assignment** | Select multiple frames → assign verb/direction → auto-number |
| **JSON manifest** | TexturePacker-compatible JSON Hash + custom `animations` block |
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

1. **File → Open Sprite Sheet** – load a PNG with a solid-colour background
2. Click **Auto** to detect the background colour, or use **Pick…** to choose manually
3. Adjust **Tolerance** if needed (higher = more aggressive background matching)
4. Choose **Auto-detect (contour)** or **Grid** mode in the Settings panel
5. Click **Detect Sprites** – frames appear as coloured overlays on the canvas
6. Select frames in the right sidebar → click **Assign Name…** → fill in part1, part2, verb, direction
7. In the workflow **Sort into Frame Sequences** step, you can assign the same source frame multiple times (it stays available after assignment)
8. Use **Move Up / Move Down** or drag-and-drop in the right sidebar to reorder frame sequence (numbers auto-adjust)
9. **File → Export Sprites…** → choose output folder → OK
10. Individual transparent PNGs + `manifest.json` are written to the output folder

> Note: Export now blocks if two sequence entries would produce the same output filename.

### Keyboard Shortcuts

| Shortcut | Action |
|---|---|
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

## Export Format

### Individual PNGs

Each frame is exported as an RGBA PNG with the background colour replaced by full transparency. Optional sub-folder organisation:

```
output/
├── hero/base/walking/hero-base-walking-east-001.png
├── hero/base/walking/hero-base-walking-east-002.png
└── hero/base/idle/hero-base-idle-south-001.png
```

### manifest.json

TexturePacker JSON Hash compatible, with an extra `animations` block:

```json
{
  "frames": {
    "hero-base-walking-east-001.png": {
      "frame": {"x": 0, "y": 0, "w": 32, "h": 48},
      "rotated": false,
      "trimmed": false,
      "spriteSourceSize": {"x": 0, "y": 0, "w": 32, "h": 48},
      "sourceSize": {"w": 32, "h": 48}
    }
  },
  "animations": {
    "hero-base-walking-east": [
      "hero-base-walking-east-001.png",
      "hero-base-walking-east-002.png"
    ]
  },
  "meta": {
    "app": "sprite-splitter",
    "version": "1.0.0",
    "image": "spritesheet.png",
    "format": "RGBA8888",
    "size": {"w": 256, "h": 256},
    "scale": "1"
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
