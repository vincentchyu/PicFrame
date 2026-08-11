import concurrent.futures
import json
import os
from datetime import datetime, timezone
from pathlib import Path

from .config import IMAGE_EXTENSIONS
from .metadata import run_exif_batch
from .output import OutputPolicy
from .presentation import normalize_presentation
from .renderer import validate_presentation_requirements
from .rendering import get_renderer, make_card, make_contact_sheet


def list_photos(source_dir):
    return sorted(p for p in source_dir.iterdir() if p.is_file() and p.suffix.lower() in IMAGE_EXTENSIONS)


def normalize_layout(layout, scheme="scheme1"):
    _, layout = normalize_presentation(scheme, layout)
    return layout


def _write_manifest(path, presentation, renderer, layout, output_policy, source_dir, result_dir, outputs, contact_sheet):
    manifest = {
        "scheme": presentation.scheme_id,
        "renderer": presentation.renderer,
        "renderer_id": renderer.renderer_id,
        "config": presentation.config,
        "resources": presentation.resources,
        "dependencies": list(presentation.dependencies),
        "layout": layout,
        "compression": output_policy.compression,
        "format": output_policy.format,
        "source_directory": str(source_dir),
        "output_directory": str(result_dir),
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "outputs": [str(path) for path in outputs],
        "contact_sheet": str(contact_sheet) if contact_sheet else None,
    }
    path.write_text(json.dumps(manifest, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return path


def generate_batch(
    source_dir,
    result_dir,
    asset_dir,
    progress_callback=None,
    layout=None,
    scheme="scheme1",
    compression="none",
    legacy=False,
):
    presentation, layout = normalize_presentation(scheme, layout)
    validate_presentation_requirements(presentation)
    renderer = get_renderer(presentation)
    output_policy = OutputPolicy(compression)
    source_dir = Path(source_dir).resolve()
    result_dir = Path(result_dir).resolve()
    asset_dir = Path(asset_dir).resolve()

    if not source_dir.exists():
        raise FileNotFoundError(f"Missing source folder: {source_dir}")
    if not source_dir.is_dir():
        raise NotADirectoryError(f"Source path is not a folder: {source_dir}")

    photos = list_photos(source_dir)
    if not photos:
        raise ValueError(f"No photos found in {source_dir}")

    result_dir.mkdir(parents=True, exist_ok=True)
    total = len(photos)

    # 1. 一次性批量提取所有照片 EXIF，降至 1 次 exiftool 进程
    exif_map = run_exif_batch(photos)

    outputs = []
    if total > 1:
        # 2. 多线程并发生成卡片
        max_workers = min(8, (os.cpu_count() or 1) + 4)
        with concurrent.futures.ThreadPoolExecutor(max_workers=max_workers) as executor:
            future_to_item = {
                executor.submit(
                    make_card,
                    photo,
                    result_dir,
                    renderer,
                    presentation,
                    layout,
                    output_policy,
                    asset_dir,
                    exif_map.get(photo.resolve()),
                ): (idx, photo)
                for idx, photo in enumerate(photos, start=1)
            }
            indexed_outputs = []
            for future in concurrent.futures.as_completed(future_to_item):
                idx, photo = future_to_item[future]
                out_path = future.result()
                indexed_outputs.append((idx, out_path))
                if progress_callback:
                    progress_callback("generated", len(indexed_outputs), total, photo, result_dir)
        indexed_outputs.sort(key=lambda item: item[0])
        outputs = [out for _, out in indexed_outputs]
    else:
        photo = photos[0]
        if progress_callback:
            progress_callback("processing", 1, 1, photo, result_dir)
        outputs.append(
            make_card(
                photo,
                result_dir,
                renderer,
                presentation,
                layout,
                output_policy,
                asset_dir,
                exif_map.get(photo.resolve()),
            )
        )
        if progress_callback:
            progress_callback("generated", 1, 1, photo, result_dir)


    if progress_callback:
        progress_callback("contact_sheet", total, total, None, result_dir)
    contact_sheet = make_contact_sheet(outputs, result_dir, output_policy)
    manifest = _write_manifest(
        result_dir / "manifest.json",
        presentation,
        renderer,
        layout,
        output_policy,
        source_dir,
        result_dir,
        outputs,
        contact_sheet,
    )
    if progress_callback:
        progress_callback("done", total, total, contact_sheet, result_dir)

    return {
        "source_dir": source_dir,
        "result_dir": result_dir,
        "scheme": presentation.scheme_id,
        "renderer": presentation.renderer,
        "renderer_id": renderer.renderer_id,
        "layout": layout,
        "compression": output_policy.compression,
        "format": output_policy.format,
        "outputs": outputs,
        "contact_sheet": contact_sheet,
        "manifest": manifest,
    }


def generate_from_source(source_dir, output_dir=None, progress_callback=None, layout=None, scheme="scheme1", compression="none"):
    source_dir = Path(source_dir).resolve()
    presentation, normalized_layout = normalize_presentation(scheme, layout)
    output_root = Path(output_dir).resolve() if output_dir else source_dir / "PicFrame"
    result_dir = output_root / presentation.output_dir / normalized_layout / OutputPolicy(compression).format
    return generate_batch(
        source_dir,
        result_dir,
        source_dir,
        progress_callback,
        normalized_layout,
        scheme,
        compression,
    )


def generate(task_dir, progress_callback=None, layout=None, scheme="scheme1", compression="none"):
    """Legacy src/result compatibility path; it intentionally skips new nesting."""
    task_dir = Path(task_dir).resolve()
    src_dir = task_dir / "src"
    result_dir = task_dir / "result"
    if not src_dir.exists():
        raise SystemExit(f"Missing src folder: {src_dir}")

    try:
        result = generate_batch(src_dir, result_dir, task_dir, progress_callback, layout, scheme, compression, legacy=True)
    except ValueError as exc:
        raise SystemExit(str(exc)) from exc

    print(f"Generated {len(result['outputs'])} cards in {result['result_dir']}")
    for out in result["outputs"]:
        print(out)
    if result["contact_sheet"]:
        print(result["contact_sheet"])
    return result
