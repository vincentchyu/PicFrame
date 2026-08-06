from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True)
class OutputPolicy:
    """Encoding policy selected by the CLI or TUI."""

    compression: str = "none"
    jpeg_quality: int = 90

    def __post_init__(self):
        if self.compression not in {"none", "jpeg"}:
            raise ValueError("compression must be 'none' or 'jpeg'")
        if not 1 <= self.jpeg_quality <= 100:
            raise ValueError("jpeg_quality must be between 1 and 100")

    @property
    def format(self):
        return "png" if self.compression == "none" else "jpeg"

    @property
    def suffix(self):
        return ".png" if self.format == "png" else ".jpg"

    def save_card(self, image, path: Path, icc_profile=None):
        save_kwargs = {}
        if icc_profile:
            save_kwargs["icc_profile"] = icc_profile
        if self.format == "png":
            image.convert("RGB").save(path, format="PNG", **save_kwargs)
        else:
            save_kwargs.update({"quality": self.jpeg_quality, "optimize": True})
            image.convert("RGB").save(path, format="JPEG", **save_kwargs)

    def save_contact_sheet(self, image, path: Path, icc_profile=None):
        save_kwargs = {"quality": 95 if self.compression == "none" else self.jpeg_quality, "optimize": True}
        if icc_profile:
            save_kwargs["icc_profile"] = icc_profile
        image.convert("RGB").save(path, format="JPEG", **save_kwargs)
