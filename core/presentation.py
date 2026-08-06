import json
from dataclasses import dataclass, field
from pathlib import Path

from .config import PROJECT_DIR


PRESENTATION_CONFIG = PROJECT_DIR / "config" / "presentation_schemes.json"


@dataclass(frozen=True)
class PresentationScheme:
    scheme_id: str
    name: str
    renderer: str
    layouts: tuple[str, ...]
    default_layout: str
    output_dir: str
    config: str | None = None
    resources: dict = field(default_factory=dict)
    dependencies: tuple[str, ...] = ()

    def resolve_path(self, raw_path):
        if not raw_path:
            return None
        path = Path(raw_path)
        return path if path.is_absolute() else (PROJECT_DIR / path).resolve()


def load_presentation_schemes(config_path=PRESENTATION_CONFIG):
    config_path = Path(config_path)
    if not config_path.exists():
        raise FileNotFoundError(f"Missing presentation scheme config: {config_path}")

    with config_path.open("r", encoding="utf-8") as f:
        raw = json.load(f)

    entries = raw.get("schemes")
    if not isinstance(entries, dict) or not entries:
        raise ValueError(f"Presentation config must contain a non-empty schemes object: {config_path}")

    schemes = {}
    for scheme_id, entry in entries.items():
        if not isinstance(scheme_id, str) or not scheme_id.strip():
            raise ValueError("Presentation scheme IDs must be non-empty strings")
        if not isinstance(entry, dict):
            raise ValueError(f"Presentation scheme {scheme_id!r} must be an object")

        name = str(entry.get("name") or scheme_id).strip()
        renderer = str(entry.get("renderer") or "").strip()
        layouts = entry.get("layouts")
        default_layout = str(entry.get("default_layout") or "").strip().lower()
        output_dir = str(entry.get("output_dir") or scheme_id).strip().lower()
        config = entry.get("config")
        resources = entry.get("resources") or {}
        dependencies = entry.get("dependencies") or []
        if not renderer:
            raise ValueError(f"Presentation scheme {scheme_id!r} is missing renderer")
        if not isinstance(resources, dict):
            raise ValueError(f"Presentation scheme {scheme_id!r} resources must be an object")
        if not isinstance(dependencies, list) or any(not str(item).strip() for item in dependencies):
            raise ValueError(f"Presentation scheme {scheme_id!r} dependencies must be a list of strings")
        if not isinstance(layouts, list) or not layouts:
            raise ValueError(f"Presentation scheme {scheme_id!r} must define layouts")
        normalized_layouts = tuple(str(layout).strip().lower() for layout in layouts)
        if any(not layout for layout in normalized_layouts):
            raise ValueError(f"Presentation scheme {scheme_id!r} contains an empty layout")
        if len(set(normalized_layouts)) != len(normalized_layouts):
            raise ValueError(f"Presentation scheme {scheme_id!r} contains duplicate layouts")
        if default_layout not in normalized_layouts:
            raise ValueError(
                f"Presentation scheme {scheme_id!r} default_layout must be one of {normalized_layouts}"
            )

        schemes[scheme_id.strip().lower()] = PresentationScheme(
            scheme_id=scheme_id.strip().lower(),
            name=name,
            renderer=renderer,
            layouts=normalized_layouts,
            default_layout=default_layout,
            output_dir=output_dir,
            config=str(config).strip() if config else None,
            resources={str(key): str(value) for key, value in resources.items()},
            dependencies=tuple(str(item).strip() for item in dependencies),
        )
    return schemes


def get_presentation_scheme(scheme="scheme1", config_path=PRESENTATION_CONFIG):
    scheme_id = str(scheme or "scheme1").strip().lower()
    schemes = load_presentation_schemes(config_path)
    try:
        return schemes[scheme_id]
    except KeyError as exc:
        choices = ", ".join(sorted(schemes))
        raise ValueError(f"Unsupported presentation scheme: {scheme_id}. Available schemes: {choices}") from exc


def normalize_presentation(scheme="scheme1", layout=None, config_path=PRESENTATION_CONFIG):
    selected = get_presentation_scheme(scheme, config_path)
    normalized_layout = str(layout or selected.default_layout).strip().lower()
    if normalized_layout not in selected.layouts:
        choices = ", ".join(selected.layouts)
        raise ValueError(
            f"Layout {normalized_layout!r} is not supported by {selected.scheme_id}; available layouts: {choices}"
        )
    return selected, normalized_layout
