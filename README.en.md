# Xiaohongshu Photography Info Card Generator

Generate Xiaohongshu/Rednote photography info cards from a folder of photos. The script reads EXIF metadata, matches camera/lens product PNGs, derives a soft background color from each photo, preserves the photo aspect ratio, and writes finished cards plus a contact sheet.

The visual direction comes from a Guizang-style social card workflow and this project's [PROMPT.en.md](/Users/vincent/Developer/code/python_code/PicFrame34/PROMPT.en.md), then narrows it into a reusable Python utility for photography cards.

Chinese version: [README.md](/Users/vincent/Developer/code/python_code/PicFrame34/README.md).

## Features

- Portrait source photos can use either the `portrait` 3:4 presentation or the `landscape` 4:3 presentation.
- Reads EXIF with `exiftool`.
- Preserves the source photo ratio without stretching or forced crop-fill.
- Supports landscape and portrait photos with contain-fit placement.
- Derives a soft card background from the source photo.
- Uses fixed camera/lens zones so exposure text never pushes lens text down.
- Compacts long exposure rows with ` | ` separators.
- Parses lens family and lens parameters from `LensModel` / `LensID` / `Lens`.
- Wraps or truncates long lens names safely.
- Shows GPS coordinates in a small top capsule when available; appends altitude when available.
- Shows a bottom copyright capsule: `© <year> Vincent Chyu PHOTOGRAPHY - All rights reserved`.
- Reads the copyright year from EXIF capture date when possible.
- Preserves embedded ICC profiles; sRGB inputs are saved with `sRGB IEC61966-2.1`.
- Generates `PicFrame34/contact-sheet.jpg` for quick review.

## Requirements

- macOS is recommended because the script uses system fonts and ColorSync profiles.
- Python 3
- `exiftool`
- Python packages in `requirements.txt`

Install `exiftool`:

```bash
brew install exiftool
```

Create the virtual environment:

```bash
python3 -m venv .venv
source .venv/bin/activate
python3 -m pip install -r requirements.txt
```

## Folder Structure

Put photos directly in any source folder. The program reads images from that folder and writes results to a `PicFrame34/` folder inside it. `20260707/` below is only an example name.

```text
.
├── generate_xhs_photo_cards.py
├── core/
│   ├── cli.py
│   ├── tui.py
│   ├── batch.py
│   ├── rendering.py
│   ├── metadata.py
│   ├── assets.py
│   ├── fonts.py
│   ├── config.py
│   └── utils.py
├── requirements.txt
├── config/
│   └── gear_assets.json
├── assets/
│   └── gear/
│       ├── default-camera.png
│       ├── default-lens.png
│       ├── Z6III.png
│       ├── NIKKOR Z 24-120mm f4 S.png
│       └── NIKKOR Z 35mm f1.8 S.png
└── 20260707/
    ├── DSC_0001.jpg
    ├── DSC_0002.png
    └── PicFrame34/
```

Built-in product PNGs live in `assets/gear/`. Task-local assets can live in the task folder's own `assets/gear/` folder or task root, and they take priority over built-in assets. Model-to-asset mappings are maintained globally in `config/gear_assets.json`.

## Usage

Activate the environment:

```bash
source .venv/bin/activate
```

Open the TUI and choose a source photo folder:

```bash
python3 generate_xhs_photo_cards.py
```

The script can also run directly as an executable:

```bash
./generate_xhs_photo_cards.py
```

You can also pass a source folder directly for batch usage:

```bash
python3 generate_xhs_photo_cards.py --source 20260707
```

`--layout` only changes output for source photos whose width is less than their height. For portrait photos that work better as a horizontal info card:

```bash
python3 generate_xhs_photo_cards.py --source 20260707 --layout landscape
```

This portrait-photo landscape output is `1440 x 1080`, with the main photo on the left, the info column on the right, and all four photo corners rounded. Landscape source photos are not changed by this option and keep the default card layout.

Or run without activation:

```bash
.venv/bin/python3 generate_xhs_photo_cards.py --source 20260707
```

For the old task-folder layout, use the explicit compatibility mode:

```bash
python3 generate_xhs_photo_cards.py --legacy-task 20260707
```

Legacy mode reads `20260707/src/` and writes `20260707/result/`.

To write new-mode output somewhere else:

```bash
python3 generate_xhs_photo_cards.py --source 20260707 --output 20260707-cards
```

Outputs are written to:

```text
20260707/PicFrame34/
```

Each source photo produces:

```text
<photo_stem>_card.png
```

The script also writes:

```text
20260707/PicFrame34/contact-sheet.jpg
```

## Assets

`config/gear_assets.json` is the global config file for default camera/lens PNGs and camera/lens model mappings. Current default config:

```json
{
  "defaults": {
    "camera": "../assets/gear/default-camera.png",
    "lens": "../assets/gear/default-lens.png"
  },
  "cameras": {
    "NIKON Z6_3": "../assets/gear/Z6III.png",
    "Nikon Z6III": "../assets/gear/Z6III.png"
  },
  "lenses": {
    "NIKKOR Z 24-120mm f/4 S": "../assets/gear/NIKKOR Z 24-120mm f4 S.png",
    "NIKKOR Z 35mm f/1.8 S": "../assets/gear/NIKKOR Z 35mm f1.8 S.png"
  }
}
```

If no camera or lens match is found, the script prints a warning and uses `default-camera.png` or `default-lens.png` without stopping the batch. To support more gear later, add the EXIF `Model` / `CameraModelName` or `LensModel` / `LensID` / `Lens` string to `config/gear_assets.json`, then place the matching PNG in `assets/gear/`.

iPhone `LensModel` / `LensID` values include the active focal length and aperture, for example `iPhone 14 Pro back triple camera 6.86mm f/1.78`. Asset matching also tries the module-level key `iPhone 14 Pro back triple camera`, because iPhone lenses are not interchangeable and the PNG should represent the camera module. The card text still keeps the full focal length and aperture.

## Lens Text Parsing

Lens display text is no longer hard-coded to `Nikon`, and `NIKKOR Z` is not stripped away. The script finds the focal-length number before `mm`; everything before that number becomes the lens family, while the focal length and aperture stay in the parameter line.

Examples:

```text
NIKKOR Z 24-120mm f/4 S
Family: NIKKOR Z
Parameters: 24-120mm f/4 S

iPhone 13 Pro back triple camera 9mm f/2.8
Family: iPhone 13 Pro back triple camera
Parameters: 9mm f/2.8
```

An independent `S` in the parameter line is rendered with a heavier weight because it identifies Nikon S-Line high-quality lenses.

## Output Notes

- The main photo is contain-fit, not cropped or stretched.
- The card background is generated per photo, then softened for UI readability.
- Camera and lens areas are fixed; text in one area should not drift into the other.
- The GPS capsule is shown only when EXIF GPS data exists. If altitude exists, it uses a format like `43°48'N 87°34'E · 1018m`.
- ICC profile handling keeps source color behavior predictable for Preview/Finder and publishing workflows.

## Development Notes

`generate_xhs_photo_cards.py` is now a thin executable entry point. The implementation lives in the `core/` package:

- `core/cli.py`: command-line arguments and default TUI launch.
- `core/tui.py`: `curses` folder picker, layout picker, and progress screens.
- `core/batch.py`: source scanning, output folders, batch generation, and legacy task compatibility.
- `core/rendering.py`: Pillow/numpy card rendering, layouts, rounded masks, text drawing, and contact sheets.
- `core/metadata.py`: EXIF, GPS, altitude, lens text, and ICC profile handling.
- `core/assets.py`: `config/gear_assets.json` and camera/lens PNG lookup.
- `core/fonts.py`: macOS font lookup and `.ttc` face indices.
- `core/config.py`: paths, canvas sizes, extensions, and layout constants.

The implementation intentionally keeps the layout deterministic instead of template-fluid:

- Default canvas: `1080 x 1440`
- Portrait-source `landscape` canvas: `1440 x 1080`
- Default main photo frame: fixed top area
- Portrait-source landscape layout: main photo on the left, info column on the right
- Info area: fixed camera zone and fixed lens zone
- Typography: explicit `.ttc` face indices to avoid accidentally loading a bold face
- Contact sheet: generated automatically after cards

See [PROMPT.en.md](/Users/vincent/Developer/code/python_code/PicFrame34/PROMPT.en.md) for the design and implementation constraints that should guide future changes.
