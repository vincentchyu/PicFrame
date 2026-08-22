# Photography Info Card Generation Prompt

This document defines the design and implementation constraints for `generate_photo_cards.py`. Chinese version: [PROMPT.md](PROMPT.md).

The project is inspired by the Guizang social card workflow: the output should read as a polished, publishable social-media image, not a raw EXIF dump. `template.png` is a layout reference, not a pixel-perfect template.

## Goal

For every image in a chosen source folder, generate one finished photography information card in that folder's `PicFrame/` output folder.

The card should:

- Show the photo prominently.
- Preserve the photo's original aspect ratio.
- Display camera, exposure, lens, GPS, altitude, and copyright metadata cleanly.
- Use the photo itself to derive a soft background color.
- Feel quiet, precise, and product-card-like.
- Avoid text overlap, overflow, and decorative noise.
- Keep gear text as supporting information, never the primary visual.

## Platform

- Target platform: Xiaohongshu / Rednote
- Default output ratio: `3:4`
- Default output size: `1080 x 1440`
- When the source image is portrait (`width < height`) and `landscape` is selected, output ratio is `4:3` and output size is `1440 x 1080`
- Default output format: uncompressed PNG cards plus a JPEG contact sheet. With compression selected, cards are JPEG.

## Source Folder Contract

Default source folder:

```text
<source>/
├── DSC_0001.jpg
├── DSC_0002.png
└── PicFrame/
```

The script should create `PicFrame/` automatically if it does not exist.

The default executable behavior is:

- Running `python3 generate_photo_cards.py` opens a terminal UI for choosing the source folder.
- Running `python3 generate_photo_cards.py --source <source>` processes that source folder without the TUI.
- Running `python3 generate_photo_cards.py --source <source> --layout landscape` applies the landscape presentation only to source images whose width is less than their height.
- Running `python3 generate_photo_cards.py --legacy-task <task>` keeps the old compatibility behavior: read `<task>/src/` and write `<task>/result/`.

Supported source extensions:

- `.jpg`
- `.jpeg`
- `.png`
- `.tif`
- `.tiff`

## Presentation Scheme Contract

Presentation schemes and layouts are separate concepts:

- `scheme1` is the current photography information-card visual system.
- `portrait` and `landscape` are layouts within `scheme1`, not independent presentation schemes.
- Scheme registration is maintained in `config/presentation_schemes.json`, including the renderer import path, scheme config, resource roots, and optional dependencies.
- Each batch selects one presentation scheme and one layout supported by that scheme; a batch does not mix schemes.
- A new scheme should add a config entry and an independent renderer instead of accumulating more branches in `portrait` / `landscape`.
- Scheme configuration expresses only the ID, name, supported layouts, default layout, and renderer ID; coordinates, typography, and drawing details remain in the Python renderer.
- The renderer ID is resolved through the renderer registry and must select the implementation used for the batch.
- Every renderer receives the same `RendererContext` contract; scheme-specific assets, configs, dependencies, and overlays stay inside that renderer package.
- `scheme2` uses the `watermark_right_logo` watermark-band layout; its configuration is maintained in `config/schemes/scheme2/config.yaml`, with fonts and brand logos under `assets/scheme2/`. It preserves the source aspect ratio and appends a bottom watermark band containing exposure params, lens model, brand logo, date, and copyright.
- `scheme3` is the hacker terminal & ASCII structural art diptych scheme; its configuration is maintained in `config/schemes/scheme3/config.yaml`. It generates unified 1:1 square canvas cards with the original photograph strictly preserving its native aspect ratio as the visual hero. It supports `gallery_ascii_terminal` (intelligent light/dark adaptive terminal matting with hacker phosphor/dark green telemetry HUD and pure monospace mechanical font) and `gallery_ascii_diptych` (source photo dominant-color background + local chromatic ASCII structural art diptych). The ASCII engine (`ascii_engine.py`) uses Block character sets (`█▓▒░`), Sobel edge enhancement, and adaptive theme derivation.
- `scheme4` is the abstract editorial diptych scheme; its configuration is maintained in `config/schemes/scheme4/config.yaml`. Inspired by `photo-abstract-editorial`, it breaks away from conventional EXIF frames by pairing the faithful photograph with a lower ivory panel (`#F3F0E8`), extracted 4-color palette & geometric visual memory motif, and poetic serif title. It supports `editorial_diptych` (200-mesh geometric texture), `editorial_guidance` (architectural fine-line & focal crosshair art), `editorial_asymmetric`, and `editorial_minimal`. Stage 1~4 JSON schemas strictly embed self-contained `canvas` metadata (`aspect_ratio`, `width`, `height`), and all geometric aesthetic filters perform rigorous isotropic aspect ratio compensation to eliminate elliptical distortions and ensure lossless spatial reconstruction.
- Scheme2, Scheme3, and Scheme4 preserve the source ratio and render layout independently without duplicating Scheme1's top/bottom capsules.
- **Mandatory TUI Wireframe Preview Constraint**: When designing or introducing any new presentation scheme or layout, the AI/developer **MUST** synchronously implement ASCII wireframe layout previews and descriptions in `core/tui.py` (`SCHEME_PREVIEWS`, `LAYOUT_PREVIEWS`, and `choose_layout` descriptions). Empty preview panels in the TUI terminal are strictly unacceptable.
- **Mandatory Portrait Orientation Left-Right Structural Layout Constraint**: Across ALL present and future presentation schemes (Scheme 3, Scheme 4, and any newly added schemes/layouts) that pair photographs with companion artwork/panels (such as ASCII structural art, abstract visual panels, editorial textures, or metadata sidebars), **Portrait photographs (`photo_h > photo_w`) MUST unconditionally adopt a Left-Right side-by-side structural layout (Left: faithful portrait photo; Right: companion art/ASCII panel + metadata typography + swatches)** rather than top-bottom vertical stacking, preventing excessively elongated cards and preserving balanced gallery diptych proportions. Landscape photographs (`photo_w >= photo_h`) continue using the Top-Bottom vertical structure.
- **1:1 Square Canvas & Faithful Ratio Balancing Principle**: In diptych / terminal HUD presentation layouts, the canvas outputs as a unified 1:1 square aspect ratio. The original photograph is preserved 100% faithfully in its original aspect ratio as the primary visual hero; the companion abstract/ASCII artwork maintains the exact same aspect ratio as the original photograph, with the modular telemetry HUD dynamically adapting to fill the remainder of the 1:1 square canvas.

## Assets

Camera and lens product PNGs are looked up in this order:

1. The task folder's `assets/gear/`
2. The task folder
3. The selected scheme's built-in asset folder, such as `assets/scheme1/gear/`
4. The script folder

Current built-in assets:

```text
assets/scheme1/gear/default-camera.png
assets/scheme1/gear/default-lens.png
assets/scheme1/gear/Z6III.png
assets/scheme1/gear/NIKKOR Z 24-120mm f4 S.png
assets/scheme1/gear/NIKKOR Z 35mm f1.8 S.png
```

Camera and lens mappings for scheme1 are maintained in `config/schemes/scheme1/gear_assets.json`. Current config:

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

If the camera or lens cannot be matched:

- Print a warning.
- Use a default camera PNG.
- Use a default lens PNG.
- Do not fail the whole batch.
- Add future model support in `config/schemes/scheme1/gear_assets.json` and place PNGs in `assets/scheme1/gear/`, not as hard-coded Python mappings.
- iPhone `LensModel` / `LensID` values may look like `iPhone 14 Pro back triple camera 6.86mm f/1.78`; asset matching should also try the module-level key `iPhone 14 Pro back triple camera`, while the displayed lens text keeps the full focal length and aperture.

## Layout

The layout is deterministic and should not resize itself based on text length.

Canvas:

```text
default: 1080 x 1440
portrait source + landscape layout: 1440 x 1080
```

Main photo:

- Default layout uses a fixed top photo frame.
- Only when the source image is portrait and `landscape` is selected, use a fixed left photo frame with the info column on the right.
- Preserve source aspect ratio.
- Use contain-fit.
- Do not stretch.
- Do not crop just to fill the frame.
- Default layout rounds the top photo corners.
- Portrait-source landscape presentation rounds all four photo corners.

Outer card:

- Rounded card on a light page background.
- Soft shadow.
- Card background is generated from the photo.

Info area:

- Starts below the main photo.
- Split into two fixed zones: camera zone and lens zone.
- Camera and lens product images have fixed positions.
- Camera text and lens text have fixed starting positions.
- Exposure parameters must never push the lens zone downward.
- Gear typography should stay restrained and should not become a title.

## Camera Zone

Right side content:

```text
Camera model
Exposure parameters
```

Camera model examples:

```text
Nikon Z6III
iPhone 13 Pro
```

Exposure parameters may include:

- Format, when useful and not redundant
- Aperture
- Shutter speed
- ISO
- Focal length
- Exposure compensation
- White balance

Rules:

- Hide missing fields.
- If there are many fields, compact them into fewer rows.
- Use ` | ` to combine short parameters on one line.
- The camera model may be slightly stronger than the parameters, but it remains supporting information.

Example:

```text
F5.6 | 1/30
ISO 6400 | 34mm
Auto
```

## Lens Zone

Right side content:

```text
Lens family
Lens parameters
```

Lens field priority:

1. `LensModel`
2. `LensID`
3. `Lens`

Hard constraints for lens text parsing:

- Do not hard-code the lens family as `Nikon`.
- Do not strip `NIKKOR Z` bluntly.
- In the complete lens string, find the focal-length number before `mm`.
- Everything before that focal-length number is the lens family and belongs on the family line.
- Everything from that focal-length number to the end is the lens parameters and belongs on the parameter line.
- If the parameters contain an independent `S`, render that `S` in a heavier weight because it identifies Nikon S-Line high-quality lenses.

Examples:

```text
LensID: iPhone 13 Pro back triple camera 9mm f/2.8
Lens family: iPhone 13 Pro back triple camera
Lens parameters: 9mm f/2.8

LensID: NIKKOR Z 24-120mm f/4 S
Lens family: NIKKOR Z
Lens parameters: 24-120mm f/4 S
```

Layout rules:

- Keep lens text aligned with the lens product image zone.
- Wrap long lens names.
- Limit lens text to a controlled number of lines.
- Do not allow lens text to overflow outside the right text column.
- Lens family text should be smaller than the camera model to avoid stealing attention from the photo.

## GPS Capsule

If EXIF GPS data exists, show it in a small capsule at the top center of the canvas.

Format:

```text
23°09'N 113°16'E
23°09'N 113°16'E · 1018m
```

Rules:

- Convert EXIF GPS values to degree/minute notation.
- Use `N/S/E/W`.
- Do not show raw decimal numbers.
- If `GPSAltitude` or `Altitude` exists, append altitude in `m`.
- Altitude is shown as whole meters, for example `1018m`.
- Support below-sea-level altitude as a negative value.
- Do not place GPS text on top of the photo.
- Use a light capsule background derived from the card background.
- Keep it visually related to the bottom copyright capsule while staying subtle.
- If GPS is missing, omit this capsule entirely.

## Copyright Capsule

Show a bottom-center capsule:

```text
© <year> Vincent Chyu PHOTOGRAPHY - All rights reserved
```

Rules:

- `<year>` is read from EXIF capture date when possible.
- Preferred fields:
  - `DateTimeOriginal`
  - `CreateDate`
  - `SubSecDateTimeOriginal`
  - `ModifyDate`
- If no year is found, use a conservative fallback.
- Use a light capsule background derived from the card background.
- Keep the capsule visually related to the GPS capsule.
- Do not let the capsule touch the canvas edge or get clipped.

## EXIF

Read EXIF with:

```bash
exiftool -json <image>
```

Camera fields:

- `CameraModelName`
- `Model`
- `Make`

Lens fields:

- `LensModel`
- `LensID`
- `Lens`

Exposure fields:

- `Format`
- `FNumber`
- `Aperture`
- `ExposureTime`
- `ShutterSpeed`
- `ISO`
- `FocalLength`
- `ExposureCompensation`
- `WhiteBalance`

GPS fields:

- `GPSLatitude`
- `GPSLongitude`
- `GPSLatitudeRef`
- `GPSLongitudeRef`
- `GPSPosition`
- `GPSAltitude`
- `GPSAltitudeRef`
- `Altitude`

Date fields:

- `DateTimeOriginal`
- `CreateDate`
- `SubSecDateTimeOriginal`
- `ModifyDate`

## Background Color

Generate the card background from the source photo.

Algorithm:

1. Open the source photo as RGB.
2. Downsample for speed.
3. Ignore the outer 5% edges.
4. Cluster sampled pixels into a small number of color groups.
5. Pick the dominant group.
6. Convert to HLS.
7. Raise lightness into a soft UI range.
8. Reduce saturation.
9. Use the result as the card background.

The background should feel related to the photo but should not be a raw dominant color.

## Color Management

Preserve source color behavior.

Rules:

- If the source image has an embedded ICC profile, save the output with that ICC profile.
- If the source image is tagged as sRGB but does not embed an ICC profile, save with the system sRGB profile when available.
- On macOS, prefer:

```text
/System/Library/ColorSync/Profiles/sRGB Profile.icc
```

Expected sRGB output profile description:

```text
sRGB IEC61966-2.1
```

The contact sheet should inherit the first generated card's ICC profile.

## Typography

Use explicit font face indices. Do not rely on the first face in a `.ttc` file.

Preferred macOS font:

```text
Avenir Next.ttc
```

Face indices:

```text
Regular -> index 7
Medium  -> index 5
```

Fallbacks:

- Helvetica Neue
- SFNS
- Arial
- DejaVu Sans

Reason:

Some `.ttc` collections load a bold face by default. Explicit indices keep the typography stable.

Style:

- Camera and lens family text may use Medium, but their sizes should stay restrained.
- Parameters use Regular.
- An independent `S` in lens parameters may use Medium for emphasis.
- Avoid monospaced English for this card.
- Keep text calm and readable.
- Gear information must serve the photo, not compete with it.

## Text Safety

Non-negotiable:

- No text overlap.
- No text should enter another fixed zone.
- No text should touch the edge.
- Long lens names must wrap or truncate.
- Exposure fields should compact before they push the lens zone.
- The bottom copyright capsule must not collide with the card shadow or canvas edge.

## Contact Sheet

After generating all cards, also create:

```text
PicFrame/contact-sheet.jpg
```

Rules:

- Use small thumbnails.
- Include file labels.
- Keep it lightweight enough for quick review.
- Preserve an ICC profile when available.

## Adapted Guizang Social Card Principles

Only the relevant principles are adopted:

- Expression comes first; the card should communicate clearly in one glance.
- Use real photo evidence, not decorative filler.
- Avoid random ornaments, stickers, blobs, or meaningless shapes.
- Do not use nested cards.
- Do not let text overflow or collide.
- For 3:4 cards, fill the canvas with useful visual information.
- Show rendered outputs quickly, then iterate visually.

This project does not copy the Guizang skill templates. It uses the social-card design discipline as a reference while keeping the implementation as a Python image-generation utility.

## Code Structure

`generate_photo_cards.py` is only the executable entry point. Do not keep adding rendering, EXIF, or TUI logic to it. The implementation lives in the `core/` package:

- `core/cli.py`: command-line arguments, default TUI launch, and error exits.
- `core/tui.py`: standard-library `curses` folder picker, layout picker, progress screens, and readable errors.
- `core/presentation.py`: presentation-scheme configuration and scheme/layout validation.
- `core/renderer.py`: renderer abstraction, dynamic loading, and selected-scheme config/resources/dependencies validation.
- `core/renderers/scheme1/`: scheme1 package containing renderer (`renderer.py`), original-resolution 3:4/4:3 card drawing (`cards.py`), and gear PNG lookup (`assets.py`).
- `core/renderers/scheme2/`: scheme2 package containing renderer (`renderer.py`) and original-resolution watermark-band rendering (`watermark.py`).
- `core/renderers/scheme3/`: scheme3 package containing renderer (`renderer.py`), fine-art gallery matting/shadow rendering (`gallery.py`), and ASCII structural art engine (`ascii_engine.py`) with Block character sets, Sobel edge enhancement, dominant-color extraction, and monospace rasterization.
- `core/renderers/scheme4/`: scheme4 package containing renderer (`renderer.py`), VLM progressive pipeline (`pipeline.py`), and abstract editorial rendering (`editorial.py`). For complete architecture flowcharts, shared context schema, and interaction guidelines, see `docs/scheme4_architecture_and_workflow.md`.
- `core/batch.py`: source scanning, output folder selection, batch generation, and legacy task compatibility.
- `core/renderer.py`: presentation renderer abstraction.
- `core/output.py`: PNG/JPEG output policy and encoding.
- `core/rendering.py`: shared Pillow image primitives, renderer invocation, unified card output compression (`apply_card_compression`), and contact sheets.
- `core/metadata.py`: EXIF, GPS, altitude, lens text parsing, and ICC profiles.
- `core/fonts.py`: font lookup, `.ttc` face indices, and `font()`.
- `core/config.py`: project paths, canvas sizes, extensions, and layout constants.
- `core/utils.py`: small stateless helpers.

Modification rules:

- CLI/TUI changes should not touch the rendering core unless required.
- Scheme-specific layout or image-generation changes should usually stay in the matching `core/renderers/` module.
- New schemes or layouts must provide corresponding ASCII wireframe previews in `core/tui.py`.
- EXIF, GPS, ICC, and lens parsing changes should usually stay in `metadata.py`.
- Asset lookup or model mapping changes should usually stay in the matching renderer resource module and the selected scheme config under `config/schemes/`.
- Keep `generate_photo_cards.py` as a thin entry point instead of letting it grow back into a thousand-line script.

## Verification Checklist

Before considering a change complete:

- Run the script on a real folder.
- In the TUI terminal interface, cycle through each scheme and layout to confirm the right-hand ASCII wireframe preview and description render fully without any blank panels.
- Open at least one landscape photo result.
- Open at least one portrait photo result if available.
- Confirm output size is `1080 x 1440` (Scheme1) or lossless adaptive dimensions (Scheme2/3).
- Confirm the main photo ratio is preserved.
- Confirm camera and lens zones stay fixed.
- Confirm long exposure parameters compact with ` | `.
- Confirm long lens text wraps safely.
- Confirm LensID examples split correctly into family and parameters.
- Confirm `PicFrame/<scheme>/<layout>/<format>/contact-sheet.jpg` and `manifest.json` exist for default source-folder runs.
- Confirm `result/contact-sheet.jpg` exists for explicit `--legacy-task` compatibility runs.

## AI Architecture & Execution Protocol

1. **Pre-Modification Proposal Review**: Before implementing any major architecture or prompt redesigns, the AI Agent MUST first present a clear implementation plan for user review and approval.
2. **Verification & Execution Boundary**: After code modifications, the AI Agent is strictly limited to verifying code integrity via automated unit tests (`unittest`). The AI Agent MUST NOT autonomously launch heavy, multi-photo VLM inference scripts (`generate_photo_cards.py`). Real batch generation is completely user-controlled and user-executed.

