import json
from pathlib import Path

from .config import GEAR_ASSET_DIR, GEAR_CONFIG, PROJECT_DIR


def asset_path(task_dir, name, config_key=None):
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
        GEAR_CONFIG.parent / raw,
        GEAR_ASSET_DIR / raw,
        PROJECT_DIR / raw,
    ])
    for p in candidates:
        if p.exists():
            return p.resolve()
    if config_key:
        raise FileNotFoundError(
            f"Missing asset for config/gear_assets.json {config_key}: {name}. "
            f"Put it in assets/gear/, {task_dir / 'assets' / 'gear'}, or {task_dir}"
        )
    raise FileNotFoundError(
        f"Missing asset: {name}. Put it in assets/gear/, {task_dir / 'assets' / 'gear'}, or {task_dir}"
    )


def load_gear_assets(task_dir):
    if not GEAR_CONFIG.exists():
        raise FileNotFoundError(f"Missing gear asset config: {GEAR_CONFIG}")

    with GEAR_CONFIG.open("r", encoding="utf-8") as f:
        config = json.load(f)

    defaults = config.get("defaults") or {}
    if not defaults.get("camera"):
        raise ValueError("gear_assets.json is missing defaults.camera")
    if not defaults.get("lens"):
        raise ValueError("gear_assets.json is missing defaults.lens")

    camera_assets = {
        key: asset_path(task_dir, value, f"cameras.{key}")
        for key, value in (config.get("cameras") or {}).items()
    }
    lens_assets = {
        key: asset_path(task_dir, value, f"lenses.{key}")
        for key, value in (config.get("lenses") or {}).items()
    }
    return {
        "default_camera": asset_path(task_dir, defaults["camera"], "defaults.camera"),
        "default_lens": asset_path(task_dir, defaults["lens"], "defaults.lens"),
        "cameras": camera_assets,
        "lenses": lens_assets,
    }

