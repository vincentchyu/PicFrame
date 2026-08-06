import functools
import json
from dataclasses import replace
from pathlib import Path

from ...config import PROJECT_DIR
from ...metadata import lens_asset_keys
from ...utils import unique_values


def asset_path(task_dir, name, config_key=None, config_dir=None, asset_dir=None):
    raw = Path(name)
    if raw.is_absolute() and raw.exists():
        return raw

    candidates = []
    if not raw.parts[:-1]:
        candidates.extend([
            task_dir / "assets" / "gear" / raw,
            task_dir / raw,
        ])
    candidates.extend([
        (Path(config_dir) if config_dir else PROJECT_DIR) / raw,
        Path(asset_dir) / raw if asset_dir else None,
        PROJECT_DIR / raw,
    ])
    for path in (candidate for candidate in candidates if candidate is not None):
        if path.exists():
            return path.resolve()
    if config_key:
        raise FileNotFoundError(
            f"Missing asset for scheme1 gear config {config_key}: {name}. "
            f"Put it in assets/scheme1/gear/, {task_dir / 'assets' / 'gear'}, or {task_dir}"
        )
    raise FileNotFoundError(
        f"Missing asset: {name}. Put it in assets/scheme1/gear/, {task_dir / 'assets' / 'gear'}, or {task_dir}"
    )


@functools.lru_cache(maxsize=32)
def load_gear_assets(task_dir, config_path, asset_dir=None):
    config_path = Path(config_path).resolve()
    if not config_path.exists():
        raise FileNotFoundError(f"Missing scheme1 gear asset config: {config_path}")

    with config_path.open("r", encoding="utf-8") as f:
        config = json.load(f)

    defaults = config.get("defaults") or {}
    if not defaults.get("camera"):
        raise ValueError("scheme1 gear_assets.json is missing defaults.camera")
    if not defaults.get("lens"):
        raise ValueError("scheme1 gear_assets.json is missing defaults.lens")

    camera_assets = {
        key: asset_path(task_dir, value, f"cameras.{key}", config_dir=config_path.parent, asset_dir=asset_dir)
        for key, value in (config.get("cameras") or {}).items()
    }
    lens_assets = {
        key: asset_path(task_dir, value, f"lenses.{key}", config_dir=config_path.parent, asset_dir=asset_dir)
        for key, value in (config.get("lenses") or {}).items()
    }
    return {
        "default_camera": asset_path(
            task_dir,
            defaults["camera"],
            "defaults.camera",
            config_dir=config_path.parent,
            asset_dir=asset_dir,
        ),
        "default_lens": asset_path(
            task_dir,
            defaults["lens"],
            "defaults.lens",
            config_dir=config_path.parent,
            asset_dir=asset_dir,
        ),
        "cameras": camera_assets,
        "lenses": lens_assets,
    }


def attach_gear_assets(context, gear_assets):
    camera_keys = unique_values([context.exif.get("CameraModelName"), context.exif.get("Model"), context.camera_model])
    camera_png = next((gear_assets["cameras"].get(key) for key in camera_keys if key in gear_assets["cameras"]), None)
    if not camera_png:
        print(
            f"Warning: no camera PNG match for {context.photo_path.name}: "
            f"{context.camera_model or 'unknown camera'}; using default"
        )
        camera_png = gear_assets["default_camera"]

    lens_keys = lens_asset_keys(context.lens_model)
    lens_png = next((gear_assets["lenses"].get(key) for key in lens_keys if key in gear_assets["lenses"]), None)
    if not lens_png:
        print(f"Warning: no lens PNG match for {context.photo_path.name}: {context.lens_model}; using default")
        lens_png = gear_assets["default_lens"]

    return replace(context, camera_png=camera_png, lens_png=lens_png)
