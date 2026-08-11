import functools
import json
import re
import subprocess
from pathlib import Path

from PIL import Image, ImageCms

from .config import SRGB_PROFILE
from .utils import unique_values


_EXIF_MEMORY_CACHE = {}


@functools.lru_cache(maxsize=256)
def _cached_run_exif(str_path):
    out = subprocess.check_output(["exiftool", "-json", str_path], text=True)
    return json.loads(out)[0]


def run_exif(path):
    resolved = Path(path).resolve()
    if resolved in _EXIF_MEMORY_CACHE:
        return _EXIF_MEMORY_CACHE[resolved]
    data = _cached_run_exif(str(resolved))
    _EXIF_MEMORY_CACHE[resolved] = data
    return data


def run_exif_batch(paths):
    if not paths:
        return {}
    resolved_paths = [Path(p).resolve() for p in paths]
    uncached_paths = [p for p in resolved_paths if p not in _EXIF_MEMORY_CACHE]
    if uncached_paths:
        str_paths = [str(p) for p in uncached_paths]
        try:
            out = subprocess.check_output(["exiftool", "-json", *str_paths], text=True)
            data = json.loads(out)
            for item in data:
                source_file = item.get("SourceFile")
                if source_file:
                    resolved_key = Path(source_file).resolve()
                    _EXIF_MEMORY_CACHE[resolved_key] = item
        except Exception:
            for p in uncached_paths:
                try:
                    run_exif(p)
                except Exception:
                    pass

    return {p: _EXIF_MEMORY_CACHE.get(p) or run_exif(p) for p in resolved_paths}



def fmt_model(exif):
    model = exif.get("CameraModelName") or exif.get("Model") or ""
    return model.replace("NIKON Z6_3", "Nikon Z6III").replace("NIKON", "Nikon")


def fmt_f_number(v):
    if v in (None, ""):
        return None
    try:
        return f"F{float(v):g}"
    except Exception:
        return f"F{v}"


def fmt_ev(v):
    if v in (None, "", 0, "0"):
        return None
    try:
        if isinstance(v, str) and "/" in v:
            a, b = v.split("/", 1)
            val = float(a) / float(b)
        else:
            val = float(v)
        return f"{val:+.1f}EV"
    except Exception:
        return f"{v}EV"


def fmt_focal(v):
    if not v:
        return None
    return str(v).replace(".0 mm", "mm").replace(" mm", "mm")


def split_lens_display_name(lens_name):
    lens_name = str(lens_name or "").strip()
    if not lens_name:
        return "", ""

    match = re.search(r"\b\d+(?:-\d+)?(?:\.\d+)?\s*mm\b", lens_name, re.IGNORECASE)
    if not match:
        return lens_name, ""

    lens_family = lens_name[:match.start()].strip()
    lens_params = lens_name[match.start():].strip()
    return lens_family, lens_params


def lens_asset_keys(lens_name):
    lens_name = str(lens_name or "").strip()
    keys = [lens_name] if lens_name else []

    # iPhone LensModel/LensID includes the module plus the active focal length
    # and aperture. The product PNG represents the fixed camera module, so map
    # all focal-length variants to the module-level key.
    match = re.match(
        r"^(iPhone\s+.+?\s+back\s+triple\s+camera)\s+\d+(?:\.\d+)?\s*mm\b.*$",
        lens_name,
        re.IGNORECASE,
    )
    if match:
        keys.append(match.group(1))

    return unique_values(keys)


def parse_gps_coord(value, ref=None):
    if value in (None, ""):
        return None
    if isinstance(value, (int, float)):
        coord = float(value)
    else:
        s = str(value).strip()
        try:
            coord = float(s)
        except ValueError:
            match = re.search(r"([\d.]+)\s*deg\s*([\d.]+)'\s*([\d.]+)\"?\s*([NSEW])?", s)
            if not match:
                return None
            deg, minute, second, inline_ref = match.groups()
            coord = float(deg) + float(minute) / 60 + float(second) / 3600
            ref = inline_ref or ref

    ref = str(ref or "").upper()
    if ref.startswith(("S", "W")):
        coord = -abs(coord)
    return coord


def format_dms(coord, positive_ref, negative_ref):
    ref = positive_ref if coord >= 0 else negative_ref
    coord = abs(coord)
    deg = int(coord)
    minutes_float = (coord - deg) * 60
    minutes = int(round(minutes_float))
    if minutes == 60:
        deg += 1
        minutes = 0
    return f"{deg}\N{DEGREE SIGN}{minutes:02d}'{ref}"


def fmt_altitude(exif):
    value = exif.get("GPSAltitude") or exif.get("Altitude")
    if value in (None, ""):
        return None

    if isinstance(value, (int, float)):
        meters = float(value)
    else:
        text = str(value).strip()
        if "/" in text and re.fullmatch(r"\s*-?\d+(?:\.\d+)?\s*/\s*\d+(?:\.\d+)?\s*", text):
            numerator, denominator = text.split("/", 1)
            meters = float(numerator) / float(denominator)
        else:
            match = re.search(r"-?\d+(?:\.\d+)?", text)
            if not match:
                return None
            meters = float(match.group(0))
            if "below" in text.lower():
                meters = -abs(meters)

    ref = str(exif.get("GPSAltitudeRef") or "").lower()
    if ref in {"1", "below sea level"} or "below" in ref:
        meters = -abs(meters)

    return f"{round(meters):g}m"


def fmt_gps(exif):
    lat = parse_gps_coord(exif.get("GPSLatitude"), exif.get("GPSLatitudeRef"))
    lon = parse_gps_coord(exif.get("GPSLongitude"), exif.get("GPSLongitudeRef"))
    if lat is None or lon is None:
        return None
    text = f"{format_dms(lat, 'N', 'S')} {format_dms(lon, 'E', 'W')}"
    altitude = fmt_altitude(exif)
    if altitude:
        text = f"{text} · {altitude}"
    return text


def photo_year(exif):
    for key in ("DateTimeOriginal", "CreateDate", "SubSecDateTimeOriginal", "ModifyDate"):
        value = str(exif.get(key) or "")
        match = re.search(r"(19|20)\d{2}", value)
        if match:
            return match.group(0)
    return "2026"


def fmt_copyright(exif, artist="Vincent Chyu"):
    """格式化统一的版权声明文本。"""
    year = photo_year(exif)
    artist_name = str(artist or "Vincent Chyu").strip()
    return f"© {year} {artist_name} PHOTOGRAPHY - All rights reserved"


def fmt_focal_integer(exif):
    """从 EXIF 中提取整数焦距，回退返回 '--'。"""
    value = str(exif.get("FocalLength") or "--")
    match = re.search(r"(\d+)\.", value)
    return match.group(1) if match else (value if str(value).isdigit() else "--")


def fmt_date(exif):
    """从 EXIF 中提取拍摄日期，返回 'YYYY-MM-DD' 格式字符串。

    优先读取 DateTimeOriginal，找不到时回退到当天。
    兼容 exiftool 输出的 '2024:07:15 10:30:00' 格式。
    """
    from datetime import datetime

    for key in ("DateTimeOriginal", "CreateDate", "SubSecDateTimeOriginal", "ModifyDate"):
        value = str(exif.get(key) or "").strip()
        if not value:
            continue
        # exiftool 格式: '2024:07:15 10:30:00'
        if len(value) >= 10 and value[4] == ":" and value[7] == ":":
            return f"{value[:4]}-{value[5:7]}-{value[8:10]}"
        # 其他格式: '2024-07-15 ...'
        date_part = value.split(" ", 1)[0]
        if len(date_part) >= 8:
            return date_part
    return datetime.now().strftime("%Y-%m-%d")


def srgb_icc_profile():
    if SRGB_PROFILE.exists():
        return SRGB_PROFILE.read_bytes()
    return ImageCms.ImageCmsProfile(ImageCms.createProfile("sRGB")).tobytes()


def source_icc_profile(path, exif=None):
    with Image.open(path) as img:
        icc = img.info.get("icc_profile")
        if icc:
            return icc

        pil_exif = img.getexif()
        color_space = pil_exif.get(0xA001) if pil_exif else None
        if color_space == 1:
            return srgb_icc_profile()

    if exif:
        profile = str(exif.get("ProfileDescription") or exif.get("ColorSpace") or "").lower()
        if "srgb" in profile:
            return srgb_icc_profile()
    return None

