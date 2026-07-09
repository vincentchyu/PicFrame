from pathlib import Path

from .assets import load_gear_assets
from .config import IMAGE_EXTENSIONS, LAYOUTS
from .rendering import make_card, make_contact_sheet


def list_photos(source_dir):
    return sorted(p for p in source_dir.iterdir() if p.is_file() and p.suffix.lower() in IMAGE_EXTENSIONS)


def normalize_layout(layout):
    layout = str(layout or "portrait").strip().lower()
    if layout not in LAYOUTS:
        raise ValueError(f"Unsupported layout: {layout}")
    return layout


def generate_batch(source_dir, result_dir, asset_dir, progress_callback=None, layout="portrait"):
    layout = normalize_layout(layout)
    source_dir = source_dir.resolve()
    result_dir = result_dir.resolve()
    asset_dir = asset_dir.resolve()

    if not source_dir.exists():
        raise FileNotFoundError(f"Missing source folder: {source_dir}")
    if not source_dir.is_dir():
        raise NotADirectoryError(f"Source path is not a folder: {source_dir}")

    photos = list_photos(source_dir)
    if not photos:
        raise ValueError(f"No photos found in {source_dir}")

    result_dir.mkdir(parents=True, exist_ok=True)
    gear_assets = load_gear_assets(asset_dir)

    outputs = []
    total = len(photos)
    for index, photo in enumerate(photos, start=1):
        if progress_callback:
            progress_callback("processing", index, total, photo, result_dir)
        outputs.append(make_card(photo, result_dir, gear_assets, layout))
        if progress_callback:
            progress_callback("generated", index, total, photo, result_dir)

    if progress_callback:
        progress_callback("contact_sheet", total, total, None, result_dir)
    contact_sheet = make_contact_sheet(outputs, result_dir)
    if progress_callback:
        progress_callback("done", total, total, contact_sheet, result_dir)

    return {
        "source_dir": source_dir,
        "result_dir": result_dir,
        "layout": layout,
        "outputs": outputs,
        "contact_sheet": contact_sheet,
    }


def generate_from_source(source_dir, output_dir=None, progress_callback=None, layout="portrait"):
    source_dir = Path(source_dir).resolve()
    result_dir = Path(output_dir).resolve() if output_dir else source_dir / "PicFrame34"
    return generate_batch(source_dir, result_dir, source_dir, progress_callback, layout)


def generate(task_dir, progress_callback=None, layout="portrait"):
    task_dir = task_dir.resolve()
    src_dir = task_dir / "src"
    result_dir = task_dir / "result"
    if not src_dir.exists():
        raise SystemExit(f"Missing src folder: {src_dir}")

    try:
        result = generate_batch(src_dir, result_dir, task_dir, progress_callback, layout)
    except ValueError as exc:
        raise SystemExit(str(exc)) from exc

    print(f"Generated {len(result['outputs'])} cards in {result['result_dir']}")
    for out in result["outputs"]:
        print(out)
    if result["contact_sheet"]:
        print(result["contact_sheet"])
    return result

