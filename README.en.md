# PicFrame - Photo Info Card & Watermark Frame Generator

Batch generate polished photography info cards and watermark frames for photos in a source folder. The script reads EXIF metadata, matches camera/lens product PNGs, matches brand logos, derives soft background colors from photos, preserves 100% original resolution and aspect ratio, supports lossless uncompressed exports as well as social media (Xiaohongshu, WeChat, etc.) compression policies, and outputs finished cards plus contact sheet previews.

The visual direction comes from a Guizang-style social card workflow and this project's [PROMPT.en.md](/Users/vincent/Developer/code/python_code/PicFrame/PROMPT.en.md), then expands it into a reusable Python utility for photo presentation cards and watermarks.

Chinese version: [README.md](/Users/vincent/Developer/code/python_code/PicFrame/README.md).

## Features

- Configurable presentation schemes: `scheme1` is the current visual system, while `portrait` and `landscape` are layouts within scheme1.
- `scheme2` (Watermark Right Logo layout `watermark_right_logo`): Preserves the source photo aspect ratio and appends a bottom watermark band. Displays exposure parameters (focal length/aperture/shutter speed/ISO), lens model, camera brand Logo, capture date, copyright text, and optional outer white borders.
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
- Generates `PicFrame/contact-sheet.jpg` for quick review.

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

Put photos directly in any source folder. The program reads images from that folder and writes results to a `PicFrame/` folder inside it. `20260707/` below is only an example name.

```text
.
├── generate_photo_cards.py
├── core/
│   ├── cli.py
│   ├── tui.py
│   ├── batch.py
│   ├── presentation.py
│   ├── renderer.py
│   ├── context.py
│   ├── output.py
│   ├── renderers/
│   │   ├── scheme1/
│   │   │   ├── renderer.py
│   │   │   ├── cards.py
│   │   │   └── assets.py
│   │   └── scheme2/
│   │       ├── renderer.py
│   │       └── watermark.py
│   ├── rendering.py
│   ├── metadata.py
│   ├── fonts.py
│   ├── config.py
│   └── utils.py
├── requirements.txt
├── config/
│   ├── presentation_schemes.json
│   └── schemes/
│       ├── scheme1/
│       │   └── gear_assets.json
│       └── scheme2/
│           └── config.yaml
├── assets/
│   ├── scheme1/
│   │   └── gear/
│   │       ├── default-camera.png
│   │       ├── default-lens.png
│   │       ├── Z6III.png
│   │       ├── NIKKOR Z 24-120mm f4 S.png
│   │       └── NIKKOR Z 35mm f1.8 S.png
│   └── scheme2/
│       ├── fonts/
│       └── logos/
└── 20260707/
    ├── DSC_0001.jpg
    ├── DSC_0002.png
    └── PicFrame/
```

Scheme resources are isolated by scheme. Scheme1 product PNGs live in `assets/scheme1/gear/`, and their mapping config lives in `config/schemes/scheme1/gear_assets.json`. Scheme2 fonts and logos live in `assets/scheme2/`, with config in `config/schemes/scheme2/config.yaml`. Task-local assets can still live in the task folder's own `assets/gear/` folder or task root, and they take priority over built-in assets.

Presentation schemes are registered in `config/presentation_schemes.json`. The configuration contains the scheme ID, display name, supported layouts, default layout, and renderer ID; coordinates, typography, and drawing behavior remain in Python. A future scheme can therefore add one config entry and one renderer without changing EXIF, asset matching, or batch processing.

The source scheme2 configuration is migrated as `config/schemes/scheme2/config.yaml`, with its fonts and manufacturer logos under `assets/scheme2/`. Scheme2 preserves the original photo ratio, appends a bottom watermark information band, matches a logo from EXIF manufacturer data, and uses the configured four text areas, colors, weights, and copyright settings.

## Usage

Activate the environment:

```bash
source .venv/bin/activate
```

Open the TUI and choose a source photo folder:

```bash
python3 generate_photo_cards.py
```

The script can also run directly as an executable:

```bash
./generate_photo_cards.py
```

You can also pass a source folder directly for batch usage:

```bash
python3 generate_photo_cards.py --source 20260707
```

To select a presentation scheme explicitly:

```bash
python3 generate_photo_cards.py --source 20260707 --scheme scheme1 --layout portrait
```

To use scheme2:

```bash
python3 generate_photo_cards.py --source 20260707 --scheme scheme2
```

Scheme2 currently provides only the `watermark_right_logo` layout and uses it as the default when no layout is specified.

`--scheme` defaults to `scheme1`, so existing commands keep their behavior. `--layout` selects a layout within the chosen scheme; landscape source photos still fall back to the scheme's default layout under the current rules.

`--layout` only changes output for source photos whose width is less than their height. For portrait photos that work better as a horizontal info card:

```bash
python3 generate_photo_cards.py --source 20260707 --layout landscape
```

This portrait-photo landscape output is `1440 x 1080`, with the main photo on the left, the info column on the right, and all four photo corners rounded. Landscape source photos are not changed by this option and keep the default card layout.

Or run without activation:

```bash
.venv/bin/python3 generate_photo_cards.py --source 20260707
```

For the old task-folder layout, use the explicit compatibility mode:

```bash
python3 generate_photo_cards.py --legacy-task 20260707
```

Legacy mode reads `20260707/src/` and writes `20260707/result/`.

To write new-mode output somewhere else:

```bash
python3 generate_photo_cards.py --source 20260707 --output 20260707-cards
```

New-mode outputs are isolated by scheme, layout, and format:

```text
20260707/PicFrame/<scheme>/<layout>/<format>/
```

Each source photo produces:

```text
<photo_stem>_card.png or <photo_stem>_card.jpg
```

The script also writes:

```text
20260707/PicFrame/<scheme>/<layout>/<format>/contact-sheet.jpg
```

Each output folder also gets a `manifest.json` with the selected scheme, renderer, layout, compression, format, source folder, output folder, and output file list.

## Assets

`config/schemes/scheme1/gear_assets.json` is scheme1's config file for default camera/lens PNGs and camera/lens model mappings. Current default config:

```json
{
  "defaults": {
    "camera": "../../../assets/scheme1/gear/default-camera.png",
    "lens": "../../../assets/scheme1/gear/default-lens.png"
  },
  "cameras": {
    "NIKON Z6_3": "../../../assets/scheme1/gear/Z6III.png",
    "Nikon Z6III": "../../../assets/scheme1/gear/Z6III.png"
  },
  "lenses": {
    "NIKKOR Z 24-120mm f/4 S": "../../../assets/scheme1/gear/NIKKOR Z 24-120mm f4 S.png",
    "NIKKOR Z 35mm f/1.8 S": "../../../assets/scheme1/gear/NIKKOR Z 35mm f1.8 S.png"
  }
}
```

If no camera or lens match is found, the script prints a warning and uses `default-camera.png` or `default-lens.png` without stopping the batch. To support more gear later, add the EXIF `Model` / `CameraModelName` or `LensModel` / `LensID` / `Lens` string to `config/schemes/scheme1/gear_assets.json`, then place the matching PNG in `assets/scheme1/gear/`.

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

`generate_photo_cards.py` is now a thin executable entry point. The implementation lives in the `core/` package:

- `core/cli.py`: command-line arguments and default TUI launch.
- `core/tui.py`: `curses` folder picker, layout picker, and progress screens.
- `core/presentation.py`: presentation-scheme configuration, validation, and scheme/layout resolution.
- `core/renderer.py`: renderer abstraction, dynamic loading, and selected-scheme config/resources/dependencies validation.
- `core/context.py`: shared EXIF, background color, and exposure context without scheme-specific layout.
- `core/renderers/scheme1/`: scheme1 package containing renderer (`renderer.py`), original-resolution 3:4/4:3 card drawing (`cards.py`), and gear lookup (`assets.py`).
- `core/renderers/scheme2/`: scheme2 package containing renderer (`renderer.py`) and original-resolution watermark band rendering (`watermark.py`).
- `core/output.py`: PNG/JPEG output policy and encoding.
- `core/batch.py`: source scanning, output folders, batch generation, and legacy task compatibility.
- `core/rendering.py`: shared Pillow image primitives, renderer invocation, unified card output compression (`apply_card_compression`), and contact sheets.
- `core/metadata.py`: EXIF, GPS, altitude, lens text, and ICC profile handling.
- `core/fonts.py`: macOS font lookup and `.ttc` face indices.
- `core/config.py`: paths, canvas sizes, extensions, and layout constants.

The relationship is one scheme per batch, followed by one layout within that scheme. `scheme1` currently registers `portrait` and `landscape`; a future scheme should be registered in `config/presentation_schemes.json` and implemented by a corresponding renderer.

The implementation intentionally keeps the layout deterministic instead of template-fluid:

- Default canvas: `1080 x 1440`
- Portrait-source `landscape` canvas: `1440 x 1080`
- Default main photo frame: fixed top area
- Portrait-source landscape layout: main photo on the left, info column on the right
- Info area: fixed camera zone and fixed lens zone
- Typography: explicit `.ttc` face indices to avoid accidentally loading a bold face
- Contact sheet: generated automatically after cards

See [PROMPT.en.md](/Users/vincent/Developer/code/python_code/PicFrame/PROMPT.en.md) for the design and implementation constraints that should guide future changes.
