import functools
from PIL import ImageFont

from .config import FONT_DIRS


def find_font(names):
    for base in FONT_DIRS:
        for name in names:
            p = base / name
            if p.exists():
                return str(p)
    return None


Avenir_NEXT = find_font(["Avenir Next.ttc"])
HELVETICA_NEUE = find_font(["HelveticaNeue.ttc"])
SFNS = find_font(["SFNS.ttf"])
ARIAL = find_font(["Arial.ttf"])
ARIAL_BOLD = find_font(["Arial Bold.ttf"])

# PIL loads the first face in a .ttc by default. Some macOS collections start
# with a bold face, so keep the face index explicit for stable typography.
FONT_REG = (Avenir_NEXT, 7) if Avenir_NEXT else ((HELVETICA_NEUE, 0) if HELVETICA_NEUE else ((SFNS, 0) if SFNS else (ARIAL or "DejaVuSans.ttf", 0)))
FONT_MED = (Avenir_NEXT, 5) if Avenir_NEXT else ((HELVETICA_NEUE, 10) if HELVETICA_NEUE else ((SFNS, 0) if SFNS else (ARIAL_BOLD or FONT_REG[0], 0)))


@functools.lru_cache(maxsize=128)
def font(size, medium=False):
    path, index = FONT_MED if medium else FONT_REG
    return ImageFont.truetype(path, size=size, index=index)


