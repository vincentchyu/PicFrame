from pathlib import Path


PROJECT_DIR = Path(__file__).resolve().parent.parent
IMAGE_EXTENSIONS = {".png", ".jpg", ".jpeg", ".tif", ".tiff"}
LAYOUTS = {"portrait", "landscape"}

CANVAS_W = 1080
CANVAS_H = 1440
OUTER_PAD = 54
CARD_R = 40
PHOTO_X = 72
PHOTO_Y = 72
PHOTO_W = 936
PHOTO_H = 620
INFO_Y = 742

FONT_DIRS = [
    Path("/System/Library/Fonts"),
    Path("/System/Library/Fonts/Supplemental"),
    Path("/Library/Fonts"),
]
SRGB_PROFILE = Path("/System/Library/ColorSync/Profiles/sRGB Profile.icc")
