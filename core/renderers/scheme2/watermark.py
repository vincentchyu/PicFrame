from dataclasses import dataclass
from pathlib import Path

from PIL import Image, ImageOps

from ...metadata import fmt_copyright, fmt_date, fmt_focal_integer, fmt_gps
from ...rendering import arrange_images_side, concatenate_images, create_text_image, pad_image, resize_by_width
from ...utils import match_brand_asset


SCHEME2_CONFIG = Path(__file__).resolve().parents[3] / "config" / "schemes" / "scheme2" / "config.yaml"
TRANSPARENT = (0, 0, 0, 0)
LINE_COLOR = "#CBCBC9"


@dataclass(frozen=True)
class Scheme2Config:
    path: Path
    data: dict

    @classmethod
    def load(cls, path=SCHEME2_CONFIG):
        try:
            import yaml
        except ImportError as exc:
            raise RuntimeError("Scheme2 requires PyYAML; install dependencies from requirements.txt") from exc

        path = Path(path).resolve()
        if not path.exists():
            raise FileNotFoundError(f"Missing scheme2 config: {path}")
        with path.open("r", encoding="utf-8") as f:
            data = yaml.safe_load(f) or {}
        return cls(path, data)

    def _base(self):
        return self.data["base"]

    def _layout(self):
        return self.data["layout"]

    def _resolve(self, raw):
        path = Path(raw)
        return path if path.is_absolute() else (self.path.parent / path).resolve()

    def font(self, bold=False, size=None):
        base = self._base()
        if size is None:
            size = 100 if bold else {1: 150, 2: 250, 3: 300}.get(base.get("font_size"), 240)
        key = "bold_font" if bold else "font"
        from PIL import ImageFont
        return ImageFont.truetype(self._resolve(base[key]), size=size)

    def font_set(self, size):
        base = self._base()
        from PIL import ImageFont
        return ImageFont.truetype(self._resolve(base["font"]), size=size)

    def artist(self):
        return self._base().get("artist", "")

    def background(self):
        return self._layout().get("background_color", "#ffffff")

    def font_padding_level(self):
        base = self._base()
        bold = base.get("bold_font_size", 1)
        regular = base.get("font_size", 1)
        return (bold if 1 <= bold <= 3 else 1) + (regular if 1 <= regular <= 3 else 1)

    def element(self, location):
        return self._layout()["elements"][location]

    def logo_for_make(self, make):
        logos = self.data.get("logo", {})
        makes = logos.get("makes") or {}
        default_path = logos.get("default", {}).get("path")
        return match_brand_asset(make, makes, default_path=default_path, resolve_fn=self._resolve)


def _text_image(content, regular_font, bold_font, is_bold=False, fill="black"):
    target_font = bold_font if is_bold else regular_font
    return create_text_image(content, target_font, fill=fill, transparent_color=TRANSPARENT)


def _scheme2_param(exif):
    focal_length = fmt_focal_integer(exif)
    f_number = str(exif.get("FNumber") or "--")
    exposure_time = str(exif.get("ExposureTime") or "--")
    iso = str(exif.get("ISO") or "--")
    return "  ".join([focal_length + "mm", "f/" + f_number, exposure_time + "s", "ISO" + iso])


def _scheme2_right_me(exif):
    return "{} , {} ".format(exif.get("ExposureProgram", ""), exif.get("MeteringMode", ""))


def _scheme2_attribute(config, location, context):
    name = config.element(location).get("name", "")
    exif = context.exif
    values = {
        "Param": _scheme2_param(exif),
        "LensMake_LensModel": " ".join(value for value in (exif.get("LensMake", ""), context.lens_model) if value),
        "GeoInfo": fmt_gps(exif) or "/",
        "Custom": config.element(location).get("value", ""),
    }
    return values.get(name, "")


def render_scheme2(context):
    config = Scheme2Config.load(context.presentation.resolve_path(context.presentation.config))
    source = ImageOps.exif_transpose(Image.open(context.photo_path)).convert("RGBA")
    image_ratio = source.width / source.height
    font_padding_level = config.font_padding_level()
    ratio = (.04 if image_ratio >= 1 else .09) + 0.02 * font_padding_level
    padding_ratio = (.52 if image_ratio >= 1 else .7) - 0.04 * font_padding_level
    normal_font = config.font()
    bold_font = config.font(bold=True)

    left_top = _text_image(_scheme2_attribute(config, "left_top", context), normal_font, bold_font, fill="#424242")
    left_bottom_text = "{} , {}".format(_scheme2_attribute(config, "left_bottom", context), _scheme2_right_me(context.exif))
    left_bottom = _text_image(left_bottom_text, normal_font, bold_font, is_bold=True, fill="#212121")
    left = concatenate_images([left_top, Image.new("RGBA", (10, 100), TRANSPARENT), left_bottom])
    left = concatenate_images([left, Image.new("RGBA", (10, 100), TRANSPARENT)], align="left")

    right_top_text = "{}  {} ".format(_scheme2_attribute(config, "right_top", context), fmt_date(context.exif))
    right_top = _text_image(right_top_text, normal_font, bold_font, fill="#424242")
    copyright_text = "© {} {} PHOTOGRAPHY - All rights reserved".format(
        fmt_date(context.exif)[:4],
        _scheme2_attribute(config, "right_bottom", context),
    )
    right_bottom = _text_image(copyright_text, normal_font, bold_font, is_bold=True, fill="#212121")
    right = concatenate_images([right_top, Image.new("RGBA", (10, 100), TRANSPARENT), right_bottom])
    right = concatenate_images([right, Image.new("RGBA", (10, 100), TRANSPARENT)], align="left")

    max_height = max(left.height, right.height)
    left = pad_image(left, int(max_height * padding_ratio), "tb")
    right = pad_image(right, int(max_height * padding_ratio), "t")
    right = pad_image(right, left.height - right.height, "b")

    watermark = Image.new("RGBA", (int(1000 / ratio), 1000), color=TRANSPARENT)
    arrange_images_side(watermark, [left], is_start=True)

    logo = Image.open(config.logo_for_make(context.exif.get("Make"))).convert("RGBA")
    logo = pad_image(logo, int(padding_ratio * logo.height))
    line = pad_image(Image.new("RGBA", (20, 1000), color=LINE_COLOR), int(padding_ratio * 1000 * 0.8))
    arrange_images_side(watermark, [logo, line, right], side="right")

    watermark = resize_by_width(watermark, source.width)
    bg = ImageOps.expand(source, border=(0, 0, 0, watermark.height), fill=config.background())
    fg = ImageOps.expand(watermark, border=(0, source.height, 0, 0), fill=TRANSPARENT)
    output = Image.alpha_composite(bg, fg)

    if config.data.get("global", {}).get("white_margin", {}).get("enable", False):
        width = int(config.data["global"]["white_margin"].get("width", 0) * min(output.width, output.height) / 100)
        output = pad_image(output, width, "tlr", color=config.background())
    return ImageOps.exif_transpose(output)
