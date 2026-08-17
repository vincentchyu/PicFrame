from dataclasses import dataclass

from .metadata import (
    fmt_ev,
    fmt_f_number,
    fmt_focal,
    fmt_model,
    run_exif,
)


@dataclass(frozen=True)
class RendererContext:
    """Common input contract shared by every presentation renderer."""

    photo_path: object
    source_dir: object
    presentation: object
    layout: str
    exif: dict
    bg: tuple
    camera_png: object = None
    lens_png: object = None
    camera_model: str = ""
    lens_model: str = ""
    line_items: tuple = ()
    effective_layout: str = ""
    compression: str = "none"
    debug: bool = False
    debug_dir: object = None


def build_context(photo_path, source_dir, presentation, layout, compression="none", exif=None, debug=False, debug_dir=None):
    """Build only the shared metadata context; scheme modules supply assets."""
    from .rendering import dominant_bg

    if exif is None:
        exif = run_exif(photo_path)
    camera_model = fmt_model(exif)

    lens_model = (exif.get("LensModel") or exif.get("LensID") or exif.get("Lens") or "").strip()

    line_items = [
        exif.get("Format") if exif.get("Format") and str(exif.get("Format")).lower() != "image/jpeg" else None,
        fmt_f_number(exif.get("FNumber") or exif.get("Aperture")),
        exif.get("ExposureTime") or exif.get("ShutterSpeed"),
        f"ISO {exif.get('ISO')}" if exif.get("ISO") else None,
        fmt_focal(exif.get("FocalLength")),
        fmt_ev(exif.get("ExposureCompensation")),
        exif.get("WhiteBalance"),
    ]
    return RendererContext(
        photo_path=photo_path,
        source_dir=source_dir,
        presentation=presentation,
        layout=layout,
        exif=exif,
        bg=dominant_bg(photo_path),
        camera_model=camera_model,
        lens_model=lens_model,
        line_items=tuple(item for item in line_items if item),
        effective_layout=layout,
        compression=compression,
        debug=debug,
        debug_dir=debug_dir,
    )

