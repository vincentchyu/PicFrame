"""
Scheme4 editorial 顶级画廊版画级渲染引擎 (Fine-art Editorial Diptych Renderer)

严格对齐 .agents/skills/photo-abstract-editorial 技能规范：
1. 上方忠实呈现摄影原片（保留原图比例与摄影气质）
2. 下方象牙色面板 (#F3F0E8) 绘制极简、克制、富有呼吸感的抽象视觉记忆母题
3. 严格控制留白（母题占面板宽度 32%-40%，高度 25%-30%，保留 70% 干净负空间）
4. 右下角点缀 4 色画廊色卡 (Palette Swatches)
5. 经典书籍衬线字体 (Baskerville / Georgia) 排版
"""
import colorsys
import json
import math
import os
import random
from dataclasses import dataclass
from pathlib import Path
from PIL import Image, ImageDraw, ImageFont

from ...fonts import font
from ...metadata import photo_year, fmt_editorial_meta_line, fmt_altitude, parse_gps_coord, format_dms
from .vlm import analyze_photo_with_vlm
from .generators import generate_motif_svg, apply_selective_color_filter
from .primitive_engine import generate_primitive_svg
from .svg_rasterizer import SVGRasterizer




SCHEME4_CONFIG = Path(__file__).resolve().parents[3] / "config" / "schemes" / "scheme4" / "config.yaml"


# ---------------------------------------------------------------------------
# 衬线字体查找辅助
# ---------------------------------------------------------------------------

def _load_editorial_serif_font(size: int, italic: bool = False, bold: bool = False) -> ImageFont.FreeTypeFont:
    """加载高品质书籍衬线字体（优先 Baskerville / Georgia / Times New Roman）"""
    candidates = []
    if italic:
        candidates += [
            "/System/Library/Fonts/Supplemental/Georgia Italic.ttf",
            "/System/Library/Fonts/Supplemental/Times New Roman Italic.ttf",
            "/System/Library/Fonts/Supplemental/Baskerville.ttc",
        ]
    elif bold:
        candidates += [
            "/System/Library/Fonts/Supplemental/Georgia Bold.ttf",
            "/System/Library/Fonts/Supplemental/Times New Roman Bold.ttf",
            "/System/Library/Fonts/Supplemental/Baskerville.ttc",
        ]
    else:
        candidates += [
            "/System/Library/Fonts/Supplemental/Baskerville.ttc",
            "/System/Library/Fonts/Supplemental/Georgia.ttf",
            "/System/Library/Fonts/Supplemental/Didot.ttc",
            "/System/Library/Fonts/Supplemental/Times New Roman.ttf",
        ]

    for path in candidates:
        if os.path.exists(path):
            try:
                return ImageFont.truetype(path, size)
            except Exception:
                continue

    return font(size, medium=bold)


def _load_editorial_meta_font(size: int) -> ImageFont.FreeTypeFont:
    """加载现代精工无衬线元数据字体（优先 Avenir Next / Helvetica Neue / SF Pro / Arial）"""
    candidates = [
        "/System/Library/Fonts/Avenir Next.ttc",
        "/System/Library/Fonts/HelveticaNeue.ttc",
        "/System/Library/Fonts/SFNS.ttf",
        "/System/Library/Fonts/Supplemental/Arial.ttf",
    ]
    for path in candidates:
        if os.path.exists(path):
            try:
                return ImageFont.truetype(path, size)
            except Exception:
                continue
    return font(size, medium=False)


# ---------------------------------------------------------------------------
# 配置加载
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class Scheme4Config:
    path: Path
    data: dict

    @classmethod
    def load(cls, path=SCHEME4_CONFIG):
        try:
            import yaml
        except ImportError as exc:
            raise RuntimeError("Scheme4 requires PyYAML; install dependencies from requirements.txt") from exc

        path = Path(path).resolve()
        if not path.exists():
            raise FileNotFoundError(f"Missing scheme4 config: {path}")
        with path.open("r", encoding="utf-8") as f:
            data = yaml.safe_load(f) or {}
        return cls(path, data)

    def layout(self, layout_name="editorial_diptych"):
        layouts = self.data.get("layouts", {})
        if layout_name in layouts:
            return layouts[layout_name]
        return layouts.get("editorial_diptych", {})


# ---------------------------------------------------------------------------
# 调色板与像素级辅助
# ---------------------------------------------------------------------------

def _extract_editorial_palette(img, sample_size=200):
    """从原照片提取四色美术馆调色板：主色、结构深色、中性淡色与点睛强调色。"""
    thumb = img.copy()
    thumb.thumbnail((sample_size, sample_size))
    thumb = thumb.convert("RGB")

    quantized = thumb.quantize(colors=16).convert("RGB")
    colors = quantized.getcolors(maxcolors=sample_size * sample_size)
    if not colors:
        return {
            "dominant": (90, 110, 80),
            "dark":     (40, 45, 40),
            "neutral":  (190, 195, 190),
            "accent":   (180, 110, 70),
        }

    colors.sort(key=lambda item: item[0], reverse=True)
    palette_info = []
    for count, (r, g, b) in colors:
        h, l, s = colorsys.rgb_to_hls(r / 255.0, g / 255.0, b / 255.0)
        palette_info.append({"rgb": (r, g, b), "count": count, "h": h, "l": l, "s": s})

    dom_rgb = palette_info[0]["rgb"]

    darks = [c for c in palette_info if c["l"] < 0.35]
    dark_rgb = darks[0]["rgb"] if darks else (40, 45, 42)

    lights = [c for c in palette_info if c["l"] > 0.60]
    neutral_rgb = lights[0]["rgb"] if lights else (195, 195, 190)

    # 灵魂点睛色 (Accent Pop)：寻找与主色/暗色距离最远且高饱和度的艺术色彩
    def _accent_score(c):
        rgb = c["rgb"]
        dist_dom = math.sqrt(sum((a - b)**2 for a, b in zip(rgb, dom_rgb)))
        dist_dark = math.sqrt(sum((a - b)**2 for a, b in zip(rgb, dark_rgb)))
        lum_penalty = 1.0 - abs(c["l"] - 0.52) * 1.2
        return c["s"] * 2.0 + (dist_dom + dist_dark) / 255.0 + max(0.0, lum_penalty)

    accents = sorted(palette_info, key=_accent_score, reverse=True)
    accent_rgb = accents[0]["rgb"] if accents and accents[0]["s"] > 0.15 else (180, 110, 75)

    def _soften(rgb, target_s=0.45):
        h, l, s = colorsys.rgb_to_hls(rgb[0] / 255.0, rgb[1] / 255.0, rgb[2] / 255.0)
        s = min(s, target_s)
        r, g, b = colorsys.hls_to_rgb(h, l, s)
        return (int(r * 255), int(g * 255), int(b * 255))

    return {
        "dominant": _soften(dom_rgb, target_s=0.50),
        "dark":     dark_rgb,
        "neutral":  neutral_rgb,
        "accent":   _soften(accent_rgb, target_s=0.75),
    }


def _smooth_curve_points(control_points, num_output=64):
    """Catmull-Rom 样条平滑算法"""
    if len(control_points) < 2:
        return control_points
    pts = [control_points[0]] + list(control_points) + [control_points[-1]]
    output = []
    n = len(pts) - 3
    for i in range(n):
        p0, p1, p2, p3 = pts[i], pts[i + 1], pts[i + 2], pts[i + 3]
        steps = max(2, num_output // n)
        for t_step in range(steps):
            t = t_step / float(steps)
            t2, t3 = t * t, t * t * t
            y_val = 0.5 * (
                (2 * p1[1]) +
                (-p0[1] + p2[1]) * t +
                (2 * p0[1] - 5 * p1[1] + 4 * p2[1] - p3[1]) * t2 +
                (-p0[1] + 3 * p1[1] - 3 * p2[1] + p3[1]) * t3
            )
            x_val = p1[0] + (p2[0] - p1[0]) * t
            output.append((x_val, y_val))
    output.append(control_points[-1])
    return output


# ---------------------------------------------------------------------------
# 画廊级有机图元绘制引擎
# ---------------------------------------------------------------------------

def _normalize_motifs(raw_motifs) -> list[dict]:
    """将无论是字符串列表还是字典列表统一转换为标准字典列表"""
    normalized = []
    if not isinstance(raw_motifs, list):
        return normalized
    for item in raw_motifs:
        if isinstance(item, str):
            normalized.append({"type": item.strip().lower()})
        elif isinstance(item, dict):
            # 兼容 key 为 "name" 或 "type"
            m_type = item.get("type") or item.get("name") or "unknown"
            item_copy = dict(item)
            item_copy["type"] = str(m_type).strip().lower()
            normalized.append(item_copy)
    return normalized


def _draw_editorial_motif_gallery(canvas, cx, cy, max_w, max_h, palette, motifs_raw=None, scene_type="landscape", svg_code=None, debug_dir=None, blur_radius=0.0):
    """
    画廊丝网版画级通用抽象矢量图元渲染引擎 (Universal Abstract Vector Renderer)
    优先解析定制极简 SVG 代码并高精度光栅化；同时具备底层几何图元容错渲染能力。
    """
    # 1. 优先采用大模型定制生成的纯粹矢量 SVG 进行高精光栅化
    if svg_code and "<svg" in svg_code:
        try:
            import time
            t_rast_start = time.time()
            # 对于万级三角面片 (Triangle Mesh)，1x 采样即具备视网膜级锐度且仅需 0.05s；对于极简线条采用 2x 抗锯齿
            is_dense_mesh = svg_code.count("<path") > 200 or "Image triangulator" in svg_code
            ss = 1 if is_dense_mesh else 2
            
            rasterizer = SVGRasterizer(max_w, max_h, palette, super_sample=ss, blur_radius=blur_radius)
            svg_img = rasterizer.rasterize(svg_code)
            rast_cost = time.time() - t_rast_start
            
            print(f"│   ├─ 矢量光栅化: 渲染母题图层 ({max_w}×{max_h}px) | 耗时: {rast_cost:.2f}s")

            # Debug 记录独立光栅化图层 (05_01_svg_rasterized_layer.png)
            if debug_dir:
                try:
                    p = Path(debug_dir)
                    p.mkdir(parents=True, exist_ok=True)
                    svg_img.save(p / "05_01_svg_rasterized_layer.png", format="PNG")
                except Exception as dbg_e:
                    print(f"│   ⚠️ [Debug Dump] 保存光栅化图层失败: {dbg_e}")

            # 在象牙色面板中心无缝合成
            paste_x = cx - max_w // 2
            paste_y = cy - max_h // 2
            canvas.alpha_composite(svg_img, (paste_x, paste_y))

            # 2. 画廊级微缩画框极细装裱线 (Gallery Inset Framing Border)
            bbox = svg_img.getbbox()
            if bbox:
                dark_c = palette.get("dark", (40, 45, 40))
                border_draw = ImageDraw.Draw(canvas)
                fx0, fy0, fx1, fy1 = bbox
                frame_box = [paste_x + fx0, paste_y + fy0, paste_x + fx1 - 1, paste_y + fy1 - 1]
                border_color = (dark_c[0], dark_c[1], dark_c[2], 65)
                border_draw.rectangle(frame_box, outline=border_color, width=1)
            return
        except Exception as exc:
            print(f"│   ⚠️ [SVG Renderer] SVG 光栅化异常 ({exc})，回退到基础几何解释器")

    dom     = palette.get("dominant", (90, 110, 80))

    dark    = palette.get("dark",     (40, 45, 40))
    neutral = palette.get("neutral",  (190, 195, 190))
    accent  = palette.get("accent",   (180, 110, 70))

    color_map = {
        "dominant": dom,
        "dark":     dark,
        "neutral":  neutral,
        "accent":   accent,
    }

    def _get_color(key, default_c):
        if isinstance(key, (tuple, list)) and len(key) >= 3:
            return tuple(key[:3])
        return color_map.get(str(key).lower().strip(), default_c)

    x0 = cx - max_w // 2
    y0 = cy - max_h // 2
    x1 = cx + max_w // 2
    y1 = cy + max_h // 2

    overlay = Image.new("RGBA", canvas.size, (0, 0, 0, 0))
    o = ImageDraw.Draw(overlay)

    motifs = _normalize_motifs(motifs_raw)
    if not motifs:
        # 默认备用图元
        motifs = [
            {"type": "atmospheric_band", "y": 0.22, "height": 0.38, "fill": "neutral"},
            {"type": "contour_surface", "curve_points": [0.42, 0.45, 0.38, 0.44, 0.40, 0.46, 0.39, 0.43], "fill": "dominant", "stroke": "dark"},
            {"type": "rhythm_marks", "points": [{"x": 0.58, "y": 0.55}, {"x": 0.68, "y": 0.53}], "shape": "dash", "fill": "accent"},
        ]

    # 按图层优先级顺序渲染：
    # Layer 1: 大气背景场 (atmospheric_band / sky_block)
    for m in motifs:
        mtype = m.get("type", "")
        if mtype in ("atmospheric_band", "sky_block", "color_band"):
            band_y = float(m.get("y", 0.22))
            band_h = float(m.get("height", 0.38))
            fill_c = _get_color(m.get("fill"), neutral)

            sw = int(max_w * 0.88)
            sh = int(max_h * band_h)
            sx = cx - sw // 2
            sy = y0 + int(max_h * max(0.02, band_y - band_h * 0.4))
            o.rounded_rectangle(
                [sx, sy, sx + sw, sy + sh],
                radius=max(6, int(sw * 0.08)),
                fill=(fill_c[0], fill_c[1], fill_c[2], 135),
            )

    # Layer 2: 核心实体骨架 (contour_surface / slope_plane / structural_columns / arch_volume)
    for m in motifs:
        mtype = m.get("type", "")
        if mtype in ("contour_surface", "contour_curve"):
            fill_c = _get_color(m.get("fill"), dom)
            stroke_c = _get_color(m.get("stroke"), dark)
            bot_y = y0 + int(max_h * 0.82)

            curve_pts = [0.38, 0.46, 0.36, 0.44, 0.39, 0.45, 0.38, 0.42]
            raw_cpts = m.get("curve_points")
            if isinstance(raw_cpts, list) and len(raw_cpts) >= 4:
                curve_pts = [float(p) for p in raw_cpts]

            step_x = max_w / float(len(curve_pts) - 1)
            base_y = y0 + int(max_h * 0.22)
            amp    = max_h * 0.46
            raw_pts = [(x0 + idx * step_x, base_y + ny * amp) for idx, ny in enumerate(curve_pts)]
            smooth = _smooth_curve_points(raw_pts, 64)
            poly   = [(x0, bot_y)] + smooth + [(x1, bot_y)]
            o.polygon(poly, fill=(fill_c[0], fill_c[1], fill_c[2], 215))
            for i in range(len(smooth) - 1):
                o.line([smooth[i], smooth[i + 1]], fill=(stroke_c[0], stroke_c[1], stroke_c[2], 225), width=max(1, int(max_w * 0.005)))

        elif mtype in ("slope_plane", "diagonal_plane"):
            fill_c = _get_color(m.get("fill"), dom)
            stroke_c = _get_color(m.get("stroke"), dark)
            bot_y = y0 + int(max_h * 0.82)
            sy = y0 + int(max_h * float(m.get("start_y", 0.72)))
            ey = y0 + int(max_h * float(m.get("end_y", 0.42)))
            poly = [(x0, sy), (x1, ey), (x1, bot_y), (x0, bot_y)]
            o.polygon(poly, fill=(fill_c[0], fill_c[1], fill_c[2], 215))
            o.line([poly[0], poly[1]], fill=(stroke_c[0], stroke_c[1], stroke_c[2], 235), width=max(1, int(max_w * 0.005)))

        elif mtype in ("structural_columns", "pillar_mass"):
            fill_c = _get_color(m.get("fill"), dark)
            pillars = m.get("pillars") or [
                {"x": 0.42, "y": 0.46, "w": 0.09, "h": 0.42},
                {"x": 0.58, "y": 0.42, "w": 0.11, "h": 0.50},
            ]
            for pl in pillars:
                px = x0 + int(max_w * float(pl.get("x", 0.5)))
                py = y0 + int(max_h * float(pl.get("y", 0.5)))
                pw = max(4, int(max_w * float(pl.get("w", 0.1))))
                ph = max(8, int(max_h * float(pl.get("h", 0.35))))
                o.rounded_rectangle(
                    [px - pw // 2, py - ph // 2, px + pw // 2, py + ph // 2],
                    radius=max(1, int(pw * 0.15)),
                    fill=(fill_c[0], fill_c[1], fill_c[2], 215),
                )

        elif mtype in ("arch_volume", "arch", "arch_layers"):
            fill_c = _get_color(m.get("fill"), dom)
            stroke_c = _get_color(m.get("stroke"), dark)
            aw = int(max_w * float(m.get("radius_w", 0.48)))
            ah = int(max_h * float(m.get("radius_h", 0.38)))
            ax = x0 + int(max_w * float(m.get("cx", 0.5)))
            ay = y0 + int(max_h * float(m.get("cy", 0.62)))
            box = [ax - aw // 2, ay - ah, ax + aw // 2, ay + ah]
            o.pieslice(box, start=180, end=360, fill=(fill_c[0], fill_c[1], fill_c[2], 225))
            o.arc(box, start=180, end=360, fill=(stroke_c[0], stroke_c[1], stroke_c[2], 210), width=max(1, int(max_w * 0.005)))
            hr = max(4, int(min(aw, ah) * 0.26))
            hy = ay - int(ah * 0.30)
            o.ellipse([ax - hr, hy - hr, ax + hr, hy + hr], fill=(stroke_c[0], stroke_c[1], stroke_c[2], 245))

    # Layer 3: 轴线与地平引导线 (axis_line)
    for m in motifs:
        mtype = m.get("type", "")
        if mtype == "axis_line":
            stroke_c = _get_color(m.get("stroke"), dark)
            lx0 = x0 + int(max_w * float(m.get("x0", 0.10)))
            ly0 = y0 + int(max_h * float(m.get("y0", 0.68)))
            lx1 = x0 + int(max_w * float(m.get("x1", 0.90)))
            ly1 = y0 + int(max_h * float(m.get("y1", 0.68)))
            o.line([lx0, ly0, lx1, ly1], fill=(stroke_c[0], stroke_c[1], stroke_c[2], 200), width=max(1, int(max_w * 0.004)))

    # Layer 4: 焦点主体符号与散点律动 (focal_marker / rhythm_marks / circle)
    for m in motifs:
        mtype = m.get("type", "")
        if mtype == "focal_marker":
            fx = float(m.get("x", 0.5))
            fy = float(m.get("y", 0.5))
            scale = float(m.get("scale", 1.0))
            shape = str(m.get("shape", "vertical_notch")).lower()
            fill_c = _get_color(m.get("fill"), accent)

            mx = x0 + int(max_w * fx)
            my = y0 + int(max_h * fy)

            if shape == "vertical_notch":
                nw = max(3, int(max_w * 0.012 * scale))
                nh = max(8, int(max_h * 0.045 * scale))
                o.rounded_rectangle([mx - nw//2, my - nh, mx + nw//2, my], radius=1, fill=(dark[0], dark[1], dark[2], 245))
                cr = max(2, int(nw * 0.9))
                o.ellipse([mx - cr, my - nh - cr*2, mx + cr, my - nh], fill=(fill_c[0], fill_c[1], fill_c[2], 250))
            elif shape == "crosshair":
                ch_s = max(4, int(max_w * 0.02 * scale))
                o.line([mx - ch_s, my, mx + ch_s, my], fill=(fill_c[0], fill_c[1], fill_c[2], 240), width=1)
                o.line([mx, my - ch_s, mx, my + ch_s], fill=(fill_c[0], fill_c[1], fill_c[2], 240), width=1)
            else:
                dr = max(3, int(max_w * 0.018 * scale))
                o.ellipse([mx - dr, my - dr, mx + dr, my + dr], fill=(fill_c[0], fill_c[1], fill_c[2], 245))

        elif mtype in ("rhythm_marks", "crowd"):
            fill_c = _get_color(m.get("fill"), accent)
            pts = m.get("points") or [
                {"x": 0.38, "y": 0.65},
                {"x": 0.52, "y": 0.62},
                {"x": 0.64, "y": 0.66},
                {"x": 0.74, "y": 0.63},
            ]
            for p in pts:
                if not isinstance(p, dict):
                    continue
                px = x0 + int(max_w * float(p.get("x", 0.5)))
                py = y0 + int(max_h * float(p.get("y", 0.5)))
                sc = float(p.get("scale", 1.0))
                rx = max(3, int(max_w * 0.015 * sc))
                ry = max(3, int(max_h * 0.022 * sc))
                o.ellipse([px - rx, py - ry, px + rx, py + ry], fill=(dark[0], dark[1], dark[2], 245))
                o.ellipse([px + rx + 1, py - ry, px + rx + 3, py - ry + 2], fill=(fill_c[0], fill_c[1], fill_c[2], 240))

        elif mtype == "circle":
            fill_c = _get_color(m.get("fill"), accent)
            cx_ = x0 + int(max_w * float(m.get("x", 0.72)))
            cy_ = y0 + int(max_h * float(m.get("y", 0.32)))
            cr = max(4, int(max_w * float(m.get("radius", 0.065))))
            o.ellipse([cx_ - cr, cy_ - cr, cx_ + cr, cy_ + cr], fill=(fill_c[0], fill_c[1], fill_c[2], 235))
            o.ellipse([cx_ - cr, cy_ - cr, cx_ + cr, cy_ + cr], outline=(dark[0], dark[1], dark[2], 140), width=1)

    canvas.alpha_composite(overlay)




# ---------------------------------------------------------------------------
# 4 色画廊色卡绘制 (Palette Swatches)
# ---------------------------------------------------------------------------

# ---------------------------------------------------------------------------
# 4 色画廊色卡绘制 (Palette Swatches)
# ---------------------------------------------------------------------------

def _draw_palette_swatches(draw, start_x, start_y, palette, swatch_size=20, spacing=6):
    """
    在面板上绘制 4 个纯净高雅的色卡小方块（Dominant, Dark, Neutral, Accent）
    """
    colors = [
        palette.get("dominant", (90, 110, 80)),
        palette.get("dark",     (40, 45, 40)),
        palette.get("neutral",  (190, 195, 190)),
        palette.get("accent",   (180, 110, 70)),
    ]
    cur_x = start_x
    for c in colors:
        draw.rounded_rectangle(
            [cur_x, start_y, cur_x + swatch_size, start_y + swatch_size],
            radius=max(2, int(swatch_size * 0.15)),
            fill=c,
        )
        cur_x += swatch_size + spacing


# ---------------------------------------------------------------------------
# 精工细线草图与焦点解构渲染引擎 (Architectural Line & Contour Art)
# ---------------------------------------------------------------------------

def _norm_coord(v, ref=1000.0) -> float:
    """自适应将 0~1 浮点坐标或 0~1000/像素级坐标归一化到 0.0~1.0 范围"""
    try:
        fv = float(v)
        if fv > 1.0:
            return min(1.0, max(0.0, fv / ref))
        return min(1.0, max(0.0, fv))
    except Exception:
        return 0.5


def _norm_point(pt, ref=1000.0) -> tuple[float, float]:
    """将坐标点归一化为 (0.0~1.0, 0.0~1.0)"""
    if isinstance(pt, (list, tuple)) and len(pt) >= 2:
        return (_norm_coord(pt[0], ref), _norm_coord(pt[1], ref))
    return (0.5, 0.5)


def _norm_bbox(bbox, ref=1000.0) -> tuple[float, float, float, float]:
    """将包围盒归一化为 (x0, y0, x1, y1)"""
    if isinstance(bbox, (list, tuple)) and len(bbox) >= 4:
        b0 = _norm_coord(bbox[0], ref)
        b1 = _norm_coord(bbox[1], ref)
        b2 = _norm_coord(bbox[2], ref)
        b3 = _norm_coord(bbox[3], ref)
        return (min(b0, b2), min(b1, b3), max(b0, b2), max(b1, b3))
    return (0.2, 0.2, 0.8, 0.8)


def extract_photo_cv_facts(photo_pil: Image.Image) -> dict:
    """从原始照片中提取真实的几何构图事实 (真实地平线、显著主体重心、真实主体轮廓与关键点)"""
    import numpy as np
    from PIL import ImageFilter

    w_target = 360
    orig_w, orig_h = photo_pil.size
    h_target = max(240, int(orig_h * (w_target / orig_w)))
    thumb = photo_pil.resize((w_target, h_target), Image.Resampling.BILINEAR)
    gray = thumb.convert("L")

    blurred = gray.filter(ImageFilter.GaussianBlur(radius=2.5))
    arr = np.array(blurred, dtype=np.float32)

    gy, gx = np.gradient(arr)
    grad_mag = np.hypot(gx, gy)

    # 1. 真实地平线/水天分界线检测
    row_means = grad_mag.mean(axis=1)
    y_min, y_max = int(h_target * 0.20), int(h_target * 0.85)
    horizon_idx = y_min + int(np.argmax(row_means[y_min:y_max]))
    horizon_y = round(float(horizon_idx) / h_target, 3)

    # 2. 真实焦点质心 (显著边缘能量质心)
    threshold = float(grad_mag.mean() + grad_mag.std() * 0.65)
    salient_mask = grad_mag > threshold
    if salient_mask.sum() > 0:
        y_idxs, x_idxs = np.where(salient_mask)
        weights = grad_mag[salient_mask]
        focal_x = round(float(np.sum(x_idxs * weights) / np.sum(weights)) / w_target, 3)
        focal_y = round(float(np.sum(y_idxs * weights) / np.sum(weights)) / h_target, 3)
    else:
        focal_x, focal_y = 0.5, 0.45

    # 3. 沿 X 轴扫描提取真实主轮廓流线 (Primary & Secondary Keypoints)
    num_bins = 8
    bin_w = w_target // num_bins
    primary_pts = []
    secondary_pts = []

    last_y = focal_y
    for b in range(num_bins):
        norm_x = round((b + 0.5) / num_bins, 3)
        col = grad_mag[:, int(b * bin_w) : int((b + 1) * bin_w)]
        energy = col.mean(axis=1)

        if energy.max() > threshold * 0.35:
            y_indices = np.arange(len(energy))
            dist_weights = np.exp(-((y_indices / h_target - last_y) ** 2) / 0.18)
            scored = energy * dist_weights
            best_y = float(np.argmax(scored)) / h_target
            best_y = max(0.12, min(0.88, best_y))
            primary_pts.append((norm_x, round(best_y, 3)))
            last_y = best_y

            opp_mask = np.abs(y_indices / h_target - best_y) > 0.14
            if opp_mask.sum() > 0 and energy[opp_mask].max() > threshold * 0.28:
                opp_y = float(y_indices[opp_mask][np.argmax(energy[opp_mask])]) / h_target
                secondary_pts.append((norm_x, round(max(0.12, min(0.88, opp_y)), 3)))
        else:
            primary_pts.append((norm_x, round(last_y, 3)))

    primary_pts.append((focal_x, focal_y))
    primary_pts.sort(key=lambda p: p[0])

    if len(secondary_pts) < 3:
        secondary_pts = [
            (0.12, round(min(0.88, focal_y + 0.18), 3)),
            (focal_x, focal_y),
            (0.88, round(min(0.88, focal_y + 0.22), 3)),
        ]
    secondary_pts.sort(key=lambda p: p[0])

    # 4. 推断主体与场景类型
    aspect = orig_h / orig_w
    if aspect > 1.2 and focal_y < 0.6:
        subject_type = "human"
        geometry_style = "monolithic_block"
        scene_type = "portrait"
    elif horizon_y > 0.65:
        subject_type = "tree"
        geometry_style = "fractal_spires"
        scene_type = "nature"
    else:
        subject_type = "mountain"
        geometry_style = "sharp_planes"
        scene_type = "landscape"

    return {
        "composition_axis": {
            "horizon_y": horizon_y,
            "slope_angle_deg": -5.0 if horizon_y > 0.5 else 5.0,
            "ground_slope": "detected_energy_ridge",
        },
        "scene_type": scene_type,
        "saliency_foci": [
            {
                "label": "PRIMARY HERO",
                "subject_type": subject_type,
                "center": [focal_x, focal_y],
                "bbox": [
                    max(0.05, focal_x - 0.25),
                    max(0.05, focal_y - 0.25),
                    min(0.95, focal_x + 0.25),
                    min(0.95, focal_y + 0.25),
                ],
                "keypoints": primary_pts,
                "geometry_style": geometry_style,
                "weight": 22.0,
                "primary_pts": primary_pts,
                "secondary_pts": secondary_pts,
            }
        ],
    }


def _draw_dashed_spline(draw, pts, fill, width=1, dash_len=8, gap_len=6):
    """沿平滑曲线点集绘制优雅虚线"""
    total_dist = 0.0
    for i in range(len(pts) - 1):
        x1, y1 = pts[i]
        x2, y2 = pts[i + 1]
        seg_len = math.hypot(x2 - x1, y2 - y1)
        if seg_len == 0:
            continue
        num_steps = max(1, int(seg_len))
        for s in range(num_steps):
            cur_pos = total_dist + (s / num_steps) * seg_len
            cycle = cur_pos % (dash_len + gap_len)
            if cycle < dash_len:
                px1 = x1 + (x2 - x1) * (s / num_steps)
                py1 = y1 + (y2 - y1) * (s / num_steps)
                px2 = x1 + (x2 - x1) * ((s + 1) / num_steps)
                py2 = y1 + (y2 - y1) * ((s + 1) / num_steps)
                draw.line([(px1, py1), (px2, py2)], fill=fill, width=width)
        total_dist += seg_len


def _generate_subject_skeletal_curves(focus: dict, x0: int, y0: int, max_w: int, max_h: int) -> tuple[list[list[tuple[float, float]]], list[list[tuple[float, float]]]]:
    """
    根据主体的 keypoints, bbox, geometry_style 与 subject_type 生成真实的精工骨架流线
    返回 (primary_splines, secondary_splines)
    """
    st = str(focus.get("subject_type", "general")).lower()
    style = str(focus.get("geometry_style", "")).lower()
    raw_kpts = focus.get("keypoints", [])
    raw_center = focus.get("center", [0.5, 0.5])
    raw_bbox = focus.get("bbox", [0.2, 0.2, 0.8, 0.8])

    cx, cy = _norm_point(raw_center)
    bx0, by0, bx1, by1 = _norm_bbox(raw_bbox)

    norm_kpts = [_norm_point(kp) for kp in raw_kpts if isinstance(kp, (list, tuple)) and len(kp) >= 2]

    prim_splines = []
    sec_splines = []

    # 像素坐标辅助
    def to_px(nx, ny):
        return (x0 + int(max_w * max(0.02, min(0.98, nx))), y0 + int(max_h * max(0.02, min(0.98, ny))))

    # 1. 树木 / 枯枝 / 尖塔结构 (fractal_spires / tree)
    if "tree" in st or "spire" in style or "branch" in st:
        if norm_kpts:
            sorted_by_y = sorted(norm_kpts, key=lambda p: p[1], reverse=True)
            root = sorted_by_y[0]
            trunk_pts = [to_px(root[0], root[1])]
            for pt in sorted_by_y[1:]:
                trunk_pts.append(to_px(pt[0], pt[1]))
            if len(trunk_pts) >= 2:
                prim_splines.append(_smooth_curve_points(trunk_pts, 48))
            # 枝桠次级分叉
            for pt in norm_kpts:
                if pt != root:
                    offset_x = 0.08 if pt[0] >= cx else -0.08
                    branch_pts = [to_px(pt[0], pt[1]), to_px(pt[0] + offset_x, max(by0, pt[1] - 0.06))]
                    sec_splines.append(branch_pts)
        else:
            base_pt = to_px(cx, by1)
            mid_pt = to_px(cx, (by0 + by1) * 0.55)
            top_pt = to_px(cx, by0)
            prim_splines.append(_smooth_curve_points([base_pt, mid_pt, top_pt], 36))
            sec_splines.append([mid_pt, to_px(max(0.05, cx - 0.12), by0 + 0.08)])
            sec_splines.append([mid_pt, to_px(min(0.95, cx + 0.12), by0 + 0.05)])

    # 2. 人物 / 身体手势 / 动物姿态 (human / figure / gesture / animal)
    elif any(k in st for k in ("human", "person", "figure", "gesture", "animal")) or "block" in style:
        if len(norm_kpts) >= 2:
            pts_px = [to_px(nx, ny) for nx, ny in norm_kpts]
            prim_splines.append(_smooth_curve_points(pts_px, 48))
            # 人物/手势轮廓扩展
            if len(pts_px) >= 2:
                p_start, p_end = pts_px[0], pts_px[-1]
                dx_p = (p_end[0] - p_start[0]) * 0.2
                dy_p = (p_end[1] - p_start[1]) * 0.2
                sec_splines.append([p_start, (p_start[0] - dy_p, p_start[1] + dx_p), p_end])
        else:
            # 姿态力线与轮廓弧
            p_top = to_px(cx, by0)
            p_center = to_px(cx, cy)
            p_bottom = to_px(cx, by1)
            prim_splines.append(_smooth_curve_points([p_top, p_center, p_bottom], 36))
            p_left = to_px(bx0, cy)
            p_right = to_px(bx1, cy)
            sec_splines.append([p_left, p_center, p_right])

    # 3. 山峰 / 岩石山脊 / 锐利切面 (mountain / alpine / sharp_planes)
    elif "mountain" in st or "ridge" in st or "sharp" in style:
        if norm_kpts:
            sorted_x = sorted(norm_kpts, key=lambda p: p[0])
            pts_px = [to_px(nx, ny) for nx, ny in sorted_x]
            if pts_px[0][0] > x0 + int(max_w * 0.05):
                pts_px.insert(0, (x0, pts_px[0][1]))
            if pts_px[-1][0] < x0 + int(max_w * 0.95):
                pts_px.append((x0 + max_w, pts_px[-1][1]))
            prim_splines.append(_smooth_curve_points(pts_px, 64))
            # 山脊阴影折线
            peak_pt = min(pts_px, key=lambda p: p[1])
            sec_splines.append([peak_pt, to_px(cx + 0.12, by1)])
        else:
            p0 = to_px(0.02, min(0.85, cy + 0.20))
            p_peak = to_px(cx, max(0.12, cy - 0.18))
            p1 = to_px(0.98, min(0.85, cy + 0.25))
            prim_splines.append(_smooth_curve_points([p0, p_peak, p1], 48))
            sec_splines.append([p_peak, to_px(cx + 0.15, min(0.90, cy + 0.35))])

    # 4. 建筑 / 几何体块 (architecture / facade / bridge)
    elif "arch" in st or "building" in st:
        p_tl = to_px(bx0, by0)
        p_tr = to_px(bx1, by0)
        p_br = to_px(bx1, by1)
        p_bl = to_px(bx0, by1)
        prim_splines.append([p_bl, p_tl, p_tr, p_br])
        if norm_kpts:
            sec_pts = [to_px(nx, ny) for nx, ny in norm_kpts]
            sec_splines.append(sec_pts)
        else:
            sec_splines.append([p_tl, to_px(cx, by0 - 0.06), p_tr])

    # 5. 曲线波浪 / 道路 / 水面 (curved_sweeps / water / path)
    else:
        if norm_kpts:
            sorted_x = sorted(norm_kpts, key=lambda p: p[0])
            pts_px = [to_px(nx, ny) for nx, ny in sorted_x]
            if pts_px[0][0] > x0 + int(max_w * 0.05):
                pts_px.insert(0, (x0, pts_px[0][1]))
            if pts_px[-1][0] < x0 + int(max_w * 0.95):
                pts_px.append((x0 + max_w, pts_px[-1][1]))
            prim_splines.append(_smooth_curve_points(pts_px, 56))
        else:
            p0 = to_px(0.02, min(0.88, cy + 0.15))
            p_mid = to_px(cx, cy)
            p1 = to_px(0.98, min(0.88, cy - 0.10))
            prim_splines.append(_smooth_curve_points([p0, p_mid, p1], 48))

    return prim_splines, sec_splines


def _draw_architectural_line_art(canvas, cx, cy, max_w, max_h, palette, scene_type="landscape", vlm_result=None, photo_img=None):
    """
    画廊精工手稿风（通用主体与焦点解构引擎 · 顶级画廊手稿美学）：
    基于移动端高 PPI 视网膜屏幕精心调校样式（不费劲、能引导、不喧宾夺主）：
    1. 精工标尺装裱框（85 墨度半透细线 + 四角微缩十字刻度与边框比例点）
    2. 空间基准地平轴线 (Composition Axis & Horizon Line 带端点标尺)
    3. 核心主体主轮廓实线 (Hero Skeletal Splines · 3~4px 扎实深炭实线，挺拔不发虚)
    4. 次级主体与立体辅助虚线 (Secondary Dashed Splines · 宽间距通透呼吸虚线)
    5. 真实立体光影排线 (Dynamic Architectural Hatching · 4~5 条极轻半透平行钢笔排线，间距通透不粘连)
    6. 浅彩实心底 + 穿透式十字准星微标 (Soft Pastel Tint & Dual Precision Crosshairs · 4.5mm 矿物印泥浅彩，一眼锚定)
    7. 左下角画廊场景与透视标注 (Dynamic Scene & Axis Tag)
    """
    overlay = Image.new("RGBA", canvas.size, (0, 0, 0, 0))
    o = ImageDraw.Draw(overlay)

    x0 = cx - max_w // 2
    y0 = cy - max_h // 2
    x1 = cx + max_w // 2
    y1 = cy + max_h // 2

    dark    = palette.get("dark",     (50, 48, 45))
    accent  = palette.get("accent",   (185, 215, 238))
    neutral = palette.get("neutral",  (160, 160, 160))
    dom     = palette.get("dominant", (90, 110, 80))

    # 精准调校的四级墨色退行体系 (Visual Hierarchy Ink Values)
    line_dark   = (dark[0], dark[1], dark[2], 235)  # 85% 深炭墨 (主轮廓/准星，扎实挺拔)
    line_subtle = (dark[0], dark[1], dark[2], 130)  # 50% 中性辅助墨 (虚线/次级骨架)
    line_ghost  = (dark[0], dark[1], dark[2], 70)   # 28% 幽灵排线墨 (光影排线/地平轴线，轻盈不抢戏)

    w_main = max(3, int(max_w * 0.0046))  # 移动端约 1.2~1.5pt 扎实物理线宽
    w_sub  = max(1, int(max_w * 0.0022))  # 精工细线
    dash_len = max(8, int(max_w * 0.022))  # 拉开虚线长度
    gap_len  = max(6, int(max_w * 0.016))  # 留出足够通透间隙

    # 1. 精工标尺装裱框 (85 墨度半透框线 + 四角微缩十字刻度与边框比例点)
    pad = int(max_w * 0.05)
    fx0, fy0, fx1, fy1 = x0 - pad, y0 - pad, x1 + pad, y1 + pad
    o.rectangle([fx0, fy0, fx1, fy1], outline=(dark[0], dark[1], dark[2], 85), width=1)

    tick = int(pad * 0.7)
    for cx_c, cy_c, dx, dy in [(fx0, fy0, 1, 1), (fx1, fy0, -1, 1), (fx0, fy1, 1, -1), (fx1, fy1, -1, -1)]:
        o.line([(cx_c, cy_c - dy * tick), (cx_c, cy_c + dy * tick)], fill=line_subtle, width=1)
        o.line([(cx_c - dx * tick, cy_c), (cx_c + dx * tick, cy_c)], fill=line_subtle, width=1)

    # 边框 25%, 50%, 75% 微小标尺点
    for r_t in (0.25, 0.50, 0.75):
        tx = fx0 + int((fx1 - fx0) * r_t)
        ty = fy0 + int((fy1 - fy0) * r_t)
        o.line([(tx, fy0 - 2), (tx, fy0 + 2)], fill=line_ghost, width=1)
        o.line([(tx, fy1 - 2), (tx, fy1 + 2)], fill=line_ghost, width=1)
        o.line([(fx0 - 2, ty), (fx0 + 2, ty)], fill=line_ghost, width=1)
        o.line([(fx1 - 2, ty), (fx1 + 2, ty)], fill=line_ghost, width=1)

    # 提取当前照片真实的空间解构事实
    spatial = {}
    fact_engine = "VLM"
    if vlm_result and isinstance(vlm_result, dict):
        spatial = vlm_result.get("spatial_facts") or {}
        if not spatial and "saliency_foci" in vlm_result:
            spatial = vlm_result
        if not scene_type or scene_type == "landscape":
            scene_type = vlm_result.get("scene_type", scene_type)

    if not spatial and photo_img:
        spatial = extract_photo_cv_facts(photo_img)
        fact_engine = "Local CV"

    axis_info = spatial.get("composition_axis", {})
    horizon_norm = _norm_coord(axis_info.get("horizon_y", 0.55))
    slope_angle = float(axis_info.get("slope_angle_deg", 0.0))
    foci = spatial.get("saliency_foci", [])

    # 2. 空间基准地平轴线 (Composition Axis & Horizon Guide Line 带端点标尺)
    if 0.15 <= horizon_norm <= 0.85:
        hy_mid = y0 + int(max_h * horizon_norm)
        slope_dy = math.tan(math.radians(max(-30.0, min(30.0, slope_angle)))) * (max_w * 0.5)
        hx0, hy0 = x0, int(hy_mid + slope_dy)
        hx1, hy1 = x1, int(hy_mid - slope_dy)
        _draw_dashed_spline(o, [(hx0, hy0), (hx1, hy1)], line_ghost, width=1, dash_len=dash_len, gap_len=gap_len)
        # 地平线两端微型端点垂直刻度
        o.line([(hx0, hy0 - 3), (hx0, hy0 + 3)], fill=line_ghost, width=1)
        o.line([(hx1, hy1 - 3), (hx1, hy1 + 3)], fill=line_ghost, width=1)

    # 3. 提取主次主体信息
    primary_focus = foci[0] if (foci and isinstance(foci, list) and len(foci) > 0 and isinstance(foci[0], dict)) else {}
    secondary_focus = foci[1] if (foci and isinstance(foci, list) and len(foci) > 1 and isinstance(foci[1], dict)) else None

    # 主焦点计算
    f0_c = primary_focus.get("center", [0.5, 0.45])
    focal_rel_x, focal_rel_y = _norm_point(f0_c)
    raw_lbl = str(primary_focus.get("label", "FEATURE")).strip().upper()
    clean_lbl = raw_lbl.replace("FOCUS", "").replace("//", "").replace("01", "").strip()
    subject_label = f"{clean_lbl} FOCUS // 01" if clean_lbl else "HERO FOCUS // 01"
    subject_type = str(primary_focus.get("subject_type", "general")).lower()

    focal_x = x0 + int(max_w * focal_rel_x)
    focal_y = y0 + int(max_h * focal_rel_y)

    print(f"│   ├─ 空间解构引擎: [{fact_engine}] | 真实主体: {subject_type} ({scene_type})")
    print(f"│   └─ 视觉引导焦点: 锁定真实主体 [{subject_label}] 坐标 (X: {focal_rel_x:.3f}, Y: {focal_rel_y:.3f})")

    # 4. 生成与绘制主主体骨架实线与辅助虚线
    prim_splines, sec_splines = _generate_subject_skeletal_curves(primary_focus, x0, y0, max_w, max_h)

    # 绘制主轮廓实线 (扎实挺拔深炭墨)
    for spl in prim_splines:
        if len(spl) >= 2:
            for i in range(len(spl) - 1):
                o.line([spl[i], spl[i + 1]], fill=line_dark, width=w_main)

    # 绘制主主体内部辅助虚线 (通透节奏)
    for spl in sec_splines:
        if len(spl) >= 2:
            _draw_dashed_spline(o, spl, line_subtle, width=w_sub, dash_len=dash_len, gap_len=gap_len)

    # 5. 生成与绘制次级主体（若存在）
    if secondary_focus:
        sec_p_splines, _ = _generate_subject_skeletal_curves(secondary_focus, x0, y0, max_w, max_h)
        for spl in sec_p_splines:
            if len(spl) >= 2:
                _draw_dashed_spline(o, spl, line_subtle, width=w_sub, dash_len=dash_len, gap_len=gap_len)

    # 6. 真实立体光影排线 (Dynamic Architectural Hatching · 极轻半透平行钢笔排线)
    # 依据真实坡度倾角与主体重心，生成 5 条间距拉开、长短渐变的精工排线
    hatch_count = 5
    hatch_spacing = max(6, int(max_w * 0.026))  # 适度拉开间距，手机端绝不粘连
    hatch_rad = math.radians(slope_angle - 40.0 if abs(slope_angle) > 1 else -35.0)
    cos_h, sin_h = math.cos(hatch_rad), math.sin(hatch_rad)
    h_len_base = max_w * 0.09

    # 排线中心位于主体阴影侧
    h_cx = focal_x + int(max_w * 0.05)
    h_cy = focal_y + int(max_h * 0.06)

    for idx in range(hatch_count):
        offset = (idx - hatch_count // 2) * hatch_spacing
        len_factor = 1.0 - abs(idx - hatch_count / 2.0) / (hatch_count * 0.75)
        cur_len = h_len_base * max(0.45, len_factor)

        px_mid = h_cx - int(offset * sin_h)
        py_mid = h_cy + int(offset * cos_h)

        p_start = (px_mid - int(cur_len * 0.5 * cos_h), py_mid - int(cur_len * 0.5 * sin_h))
        p_end   = (px_mid + int(cur_len * 0.5 * cos_h), py_mid + int(cur_len * 0.5 * sin_h))

        # 限制在面板框内，使用极轻半透实线
        if x0 <= p_start[0] <= x1 and y0 <= p_start[1] <= y1 and x0 <= p_end[0] <= x1 and y0 <= p_end[1] <= y1:
            o.line([p_start, p_end], fill=line_ghost, width=1)

    # 7. 焦点准星与双重圆环（浅彩实心底 + 极细深色外圆环 + 穿透式十字准星微标）
    # 主焦点 // 01 (放大至约 4.5mm 矿物印章尺寸，一眼锚定)
    cr = max(14, int(max_w * 0.052))
    ch_s = int(cr * 1.5)  # 准星穿透圆环
    o.line([(focal_x - ch_s, focal_y), (focal_x + ch_s, focal_y)], fill=line_dark, width=1)
    o.line([(focal_x, focal_y - ch_s), (focal_x, focal_y + ch_s)], fill=line_dark, width=1)

    tint_color = (accent[0], accent[1], accent[2], 220)
    o.ellipse([focal_x - cr, focal_y - cr, focal_x + cr, focal_y + cr], fill=tint_color)
    o.ellipse([focal_x - cr, focal_y - cr, focal_x + cr, focal_y + cr], outline=line_dark, width=1)

    # 焦点微标标签（提升字阶与阅读舒适度）
    f_focus_tag = _load_editorial_meta_font(max(11, int(max_w * 0.028)))
    o.text((focal_x + cr + 8, focal_y - int(cr * 0.45)), subject_label, fill=line_dark, font=f_focus_tag)

    # 次级焦点 // 02 (若存在)
    if secondary_focus:
        f1_c = secondary_focus.get("center", [0.5, 0.5])
        f1_rel_x, f1_rel_y = _norm_point(f1_c)
        f1_x = x0 + int(max_w * f1_rel_x)
        f1_y = y0 + int(max_h * f1_rel_y)
        cr2 = int(cr * 0.72)
        ch_s2 = int(cr2 * 1.5)
        o.line([(f1_x - ch_s2, f1_y), (f1_x + ch_s2, f1_y)], fill=line_subtle, width=1)
        o.line([(f1_x, f1_y - ch_s2), (f1_x, f1_y + ch_s2)], fill=line_subtle, width=1)
        tint_sub = (neutral[0], neutral[1], neutral[2], 200)
        o.ellipse([f1_x - cr2, f1_y - cr2, f1_x + cr2, f1_y + cr2], fill=tint_sub)
        o.ellipse([f1_x - cr2, f1_y - cr2, f1_x + cr2, f1_y + cr2], outline=line_subtle, width=1)
        f_tiny2 = _load_editorial_meta_font(max(9, int(max_w * 0.022)))
        o.text((f1_x + cr2 + 6, f1_y - int(cr2 * 0.45)), "FOCUS // 02", fill=line_subtle, font=f_tiny2)

    # 8. 动态场景与透视标签 (优雅 60% 炭灰)
    st_lower = (scene_type or "").lower() + " " + subject_type
    if any(k in st_lower for k in ("portrait", "person", "human", "figure", "gesture")):
        corner_tag = "FIGURE GESTURE // CONTOUR"
    elif any(k in st_lower for k in ("tree", "botanical", "plant", "branch", "forest")):
        corner_tag = "BOTANICAL SILHOUETTE // AXIS"
    elif any(k in st_lower for k in ("seascape", "lake", "water", "sea", "ocean")):
        corner_tag = "COASTAL HORIZON // AXIS"
    elif any(k in st_lower for k in ("architecture", "building", "urban", "city")):
        corner_tag = "ARCHITECTURAL PERSPECTIVE // AXIS"
    elif any(k in st_lower for k in ("mountain", "alpine", "ridge", "snow")):
        corner_tag = "ALPINE RIDGE // ELEVATION"
    else:
        corner_tag = "SPATIAL CONTOUR // AXIS"

    f_corner = _load_editorial_meta_font(max(10, int(max_w * 0.025)))
    o.text((fx0 + 8, fy1 - int(pad * 0.75)), corner_tag, fill=(dark[0], dark[1], dark[2], 130), font=f_corner)

    canvas.alpha_composite(overlay)


# ---------------------------------------------------------------------------
# 主渲染入口
# ---------------------------------------------------------------------------

def render_scheme4_editorial(context):
    cfg_obj = Scheme4Config.load()
    layout_name = getattr(context, "effective_layout", "") or getattr(context, "layout", "editorial_diptych")
    cfg = cfg_obj.layout(layout_name)

    # 打开原始照片
    with Image.open(context.photo_path) as src_img:
        photo = src_img.convert("RGB")
    photo_w, photo_h = photo.size
    is_portrait = photo_w < photo_h

    # 提取调色板与真实物理地理上下文 (GPS / 海拔 / EXIF)
    debug_dir  = getattr(context, "debug_dir", None)
    palette    = _extract_editorial_palette(photo)
    vlm_cfg    = dict(cfg_obj.data.get("vlm", {}))
    vlm_cfg["motif_engine"] = cfg_obj.data.get("motif_engine", "hybrid")
    vlm_cfg["generator_type"] = cfg_obj.data.get("generator_type", "triangle")
    vlm_cfg["triangle"] = cfg_obj.data.get("triangle", {})
    vlm_cfg["primitive"] = cfg_obj.data.get("primitive", {})
    vlm_cfg["layout_style"] = cfg.get("style", "primitive_mesh")

    # 提取 EXIF 经纬度与海拔物理事实
    exif_data = getattr(context, "exif", {}) or {}
    lat = parse_gps_coord(exif_data.get("GPSLatitude"), exif_data.get("GPSLatitudeRef"))
    lon = parse_gps_coord(exif_data.get("GPSLongitude"), exif_data.get("GPSLongitudeRef"))
    alt_str = fmt_altitude(exif_data)

    geo_context = {}
    if lat is not None and lon is not None:
        geo_context["gps_coordinates"] = f"{format_dms(lat, 'N', 'S')} {format_dms(lon, 'E', 'W')}"
        geo_context["decimal_coords"] = f"{lat:.4f}°N, {lon:.4f}°E"
    if alt_str:
        geo_context["elevation"] = alt_str

    layout_style  = cfg.get("style", "primitive_mesh")
    portrait_mode = cfg.get("portrait_mode", "vertical")
    panel_color   = cfg.get("panel_color", "#F3F0E8")

    # 控制台方案概览日志
    print("\n" + "┌── [Scheme4 编辑艺术双联] " + "─" * 46)
    orient_str = "Portrait (竖图)" if is_portrait else "Landscape (横图)"
    print(f"│ 📸 输入照片: {Path(context.photo_path).name} ({photo_w}×{photo_h}, {orient_str})")
    print(f"│ 📐 选用布局: {layout_name} (风格: {layout_style})")

    vlm_result = analyze_photo_with_vlm(
        context.photo_path,
        vlm_cfg,
        debug_dir=debug_dir,
        geo_context=geo_context,
        step_callback=context.step_callback,
    )

    vlm_svg = None
    if vlm_result:
        fact_source = f"VLM 视觉多模态大模型 ({vlm_result.get('source', 'vlm')})"
        if "palette" in vlm_result:
            palette = vlm_result["palette"]
        title_text    = vlm_result.get("title", "SILENT DIALOGUE")
        subtitle_text = vlm_result.get("subtitle", "")
        vlm_motifs    = vlm_result.get("motifs", [])
        vlm_svg       = vlm_result.get("svg")
        scene_type    = vlm_result.get("scene_type", "landscape")
        vlm_layout    = vlm_result.get("title_layout", "center")
    else:
        fact_source = "本地计算机视觉 (CV 真实边缘与空间解构)"
        title_text    = "SILENT DIALOGUE"
        subtitle_text = "Visual Memory & Spatial Rhythm"
        vlm_motifs    = []
        scene_type    = "landscape"
        vlm_layout    = "center"
        if layout_style == "primitive_mesh":
            try:
                gen_type = str(vlm_cfg.get("generator_type", "triangle")).strip().lower()
                gen_cfg = vlm_cfg.get("triangle" if gen_type in ("triangle", "delaunay") else "primitive", {})
                if gen_type in ("triangle", "delaunay"):
                    pts = gen_cfg.get("points") or gen_cfg.get("pts", 2500)
                    print(f"│ 🧩 抽象图元分支: [Triangle Delaunay 高精三角面片剖分 ({pts} 采样点)]")
                else:
                    num_s = gen_cfg.get("num_shapes", 220)
                    print(f"│ 🧩 抽象图元分支: [Primitive {num_s} 晶格几何退火拟合]")
                vlm_svg = generate_motif_svg(
                    image_input=photo,
                    generator_type=gen_type,
                    generator_config=gen_cfg,
                    palette=palette,
                )
            except Exception as p_err:
                print(f"│ ⚠️ [Motif Generator Fallback] 离线拟合异常: {p_err}")

    # 调色板 HEX 打印
    def _c2hex(c): return f"#{c[0]:02X}{c[1]:02X}{c[2]:02X}"
    pal_summary = f"Dominant {_c2hex(palette['dominant'])} | Dark {_c2hex(palette['dark'])} | Neutral {_c2hex(palette['neutral'])} | Accent {_c2hex(palette['accent'])}"
    print(f"│ 🎨 画廊调色板: {pal_summary}")
    print(f"│ 📝 标题策展: \"{title_text}\" | 副标: \"{subtitle_text}\" (来源: {fact_source})")

    # 画布与排版空间自适应计算
    if is_portrait and portrait_mode == "horizontal":
        branch_desc = "4:3 横版左右双联 (Left-Right Diptych)"
        total_h = photo_h
        total_w = int(photo_h * 4 / 3)
        panel_w = total_w - photo_w
        panel_h = total_h
        panel_left = photo_w
        panel_top = 0

        canvas = Image.new("RGBA", (total_w, total_h), panel_color)
        canvas.paste(photo, (0, 0))

        motif_scale = float(cfg.get("motif_scale", 0.48))
        base_area = (panel_w * motif_scale) * (panel_h * 0.30)
        asp = max(0.4, min(2.5, photo_w / float(photo_h)))
        target_w = math.sqrt(base_area * asp)
        target_h = math.sqrt(base_area / asp)
        motif_max_w = int(max(panel_w * 0.25, min(panel_w * 0.55, target_w)))
        motif_max_h = int(max(panel_h * 0.20, min(panel_h * 0.42, target_h)))
        motif_center_x = panel_left + panel_w // 2
        motif_center_y = int(panel_h * 0.36)

        font_scale     = float(cfg.get("font_scale",     0.040))
        sub_font_scale = float(cfg.get("sub_font_scale", 0.022))
        meta_ratio     = float(cfg.get("meta_ratio",     0.55))
        title_font_size = max(18, int(panel_w * font_scale))
        sub_font_size   = max(12, int(panel_w * sub_font_scale))
        meta_font_size  = max(10, int(title_font_size * meta_ratio))

        title_y = int(panel_h * 0.74)
        meta_y  = title_y - int(title_font_size * 0.88)
        sub_y   = title_y + int(title_font_size * 1.35)

    elif is_portrait and portrait_mode == "vertical":
        branch_desc = "3:4 / 4:5 竖版上下双联 (Top-Bottom Diptych - 移动端沉浸全屏)"
        photo_ratio = float(cfg.get("photo_ratio_portrait", 0.68))
        total_h = int(photo_h / photo_ratio)
        total_w = photo_w
        panel_h = total_h - photo_h
        panel_w = photo_w
        panel_left = 0
        panel_top = photo_h

        canvas = Image.new("RGBA", (panel_w, total_h), panel_color)
        canvas.paste(photo, (0, 0))

        motif_scale = float(cfg.get("motif_scale", 0.46))
        base_area = (panel_w * motif_scale) * (panel_h * 0.35)
        asp = max(0.4, min(2.5, photo_w / float(photo_h)))
        target_w = math.sqrt(base_area * asp)
        target_h = math.sqrt(base_area / asp)
        motif_max_w = int(max(panel_w * 0.22, min(panel_w * 0.50, target_w)))
        motif_max_h = int(max(panel_h * 0.18, min(panel_h * 0.40, target_h)))
        motif_center_x = panel_w // 2
        motif_center_y = photo_h + int(panel_h * 0.32)

        font_scale     = float(cfg.get("font_scale",     0.040))
        sub_font_scale = float(cfg.get("sub_font_scale", 0.022))
        meta_ratio     = float(cfg.get("meta_ratio",     0.55))
        title_font_size = max(18, int(panel_w * font_scale))
        sub_font_size   = max(12, int(panel_w * sub_font_scale))
        meta_font_size  = max(10, int(title_font_size * meta_ratio))

        title_y = panel_top + int(panel_h * 0.70)
        meta_y  = title_y - int(title_font_size * 0.88)
        sub_y   = title_y + int(title_font_size * 1.35)

    else:
        branch_desc = "经典上下双联 (Top-Bottom Diptych)"
        photo_ratio = float(cfg.get("photo_ratio_landscape", 0.48))
        total_h = int(photo_h / photo_ratio)
        total_w = photo_w
        panel_h = total_h - photo_h
        panel_w = photo_w
        panel_left = 0
        panel_top = photo_h

        canvas = Image.new("RGBA", (panel_w, total_h), panel_color)
        canvas.paste(photo, (0, 0))

        motif_scale = float(cfg.get("motif_scale", 0.42))
        base_area = (panel_w * motif_scale) * (panel_h * 0.34)
        asp = max(0.4, min(2.5, photo_w / float(photo_h)))
        target_w = math.sqrt(base_area * asp)
        target_h = math.sqrt(base_area / asp)
        motif_max_w = int(max(panel_w * 0.22, min(panel_w * 0.48, target_w)))
        motif_max_h = int(max(panel_h * 0.18, min(panel_h * 0.40, target_h)))
        motif_center_x = panel_w // 2
        motif_center_y = photo_h + int(panel_h * 0.33)

        font_scale     = float(cfg.get("font_scale",     0.040))
        sub_font_scale = float(cfg.get("sub_font_scale", 0.022))
        meta_ratio     = float(cfg.get("meta_ratio",     0.55))
        title_font_size = max(18, int(panel_w * font_scale))
        sub_font_size   = max(12, int(panel_w * sub_font_scale))
        meta_font_size  = max(10, int(title_font_size * meta_ratio))

        title_y = panel_top + int(panel_h * 0.72)
        meta_y  = title_y - int(title_font_size * 0.88)
        sub_y   = title_y + int(title_font_size * 1.35)

    print(f"│ 🖼️ 排版分支: {branch_desc} (画布总尺寸: {total_w}×{total_h})")
    print(f"│ 🔤 移动端字阶: 主标题 {title_font_size}px | 副标题 {sub_font_size}px | 元数据 {meta_font_size}px (80% 深炭墨)")

    # 绘制抽象图形：精工细线草图 vs 几何晶格拟合
    if layout_style in ("architectural_line", "minimal_line"):
        print("│ 🏛️ 渲染引擎分支: [精工细线草图与焦点解构 (Architectural Line)]")
        _draw_architectural_line_art(
            canvas,
            motif_center_x,
            motif_center_y,
            motif_max_w,
            motif_max_h,
            palette,
            scene_type=scene_type,
            vlm_result=vlm_result,
            photo_img=photo,
        )
    else:
        print("│ 🧩 渲染引擎分支: [画廊有机/几何晶格光栅化 (Primitive Mesh / SVG)]")
        gen_type_cur = str(vlm_cfg.get("generator_type", "triangle")).strip().lower()
        if gen_type_cur in ("triangle", "delaunay"):
            blur_r = 0.0  # Triangle Delaunay 面片保持超清硬边几何晶格
        else:
            blur_r = float(vlm_cfg.get("primitive", {}).get("blur_radius", 0.0))

        _draw_editorial_motif_gallery(
            canvas,
            motif_center_x,
            motif_center_y,
            motif_max_w,
            motif_max_h,
            palette,
            motifs_raw=vlm_motifs,
            scene_type=scene_type,
            svg_code=vlm_svg,
            debug_dir=debug_dir,
            blur_radius=blur_r,
        )
    print("└" + "─" * 68)

    # ── 移动端高辨识度大字阶排版 ────────────────────────────────
    draw = ImageDraw.Draw(canvas)

    font_title = _load_editorial_serif_font(title_font_size, bold=True)
    font_sub   = _load_editorial_serif_font(sub_font_size, italic=True)
    font_meta  = _load_editorial_serif_font(meta_font_size, bold=False)

    # 墨色：80% 深炭墨色（消除小屏幕发虚），70% 副标题墨色
    dark_c = palette["dark"]
    title_color = dark_c
    sub_color   = (
        int(dark_c[0] * 0.7 + 70 * 0.3),
        int(dark_c[1] * 0.7 + 70 * 0.3),
        int(dark_c[2] * 0.7 + 70 * 0.3),
    )
    meta_color  = (
        int(dark_c[0] * 0.8 + 110 * 0.2),
        int(dark_c[1] * 0.8 + 110 * 0.2),
        int(dark_c[2] * 0.8 + 110 * 0.2),
    )

    meta_line = fmt_editorial_meta_line(getattr(context, "exif", {}))

    swatch_scale   = float(cfg.get("swatch_scale", 0.026))
    swatch_size    = max(14, int(panel_w * swatch_scale))
    swatch_spacing = max(4, int(swatch_size * 0.32))

    title_layout = cfg.get("title_layout", vlm_layout)
    if title_layout == "left":
        # 左下对齐排版
        start_x = panel_left + int(panel_w * 0.08)
        if meta_line:
            draw.text((start_x, meta_y), meta_line, fill=meta_color, font=font_meta)
        draw.text((start_x, title_y), title_text, fill=title_color, font=font_title)
        if subtitle_text:
            draw.text((start_x, sub_y), subtitle_text, fill=sub_color, font=font_sub)

        # 右下角色卡
        swatches_w = swatch_size * 4 + swatch_spacing * 3
        swatches_x = panel_left + panel_w - int(panel_w * 0.08) - swatches_w
        swatches_y = title_y + int(title_font_size * 0.2)
        _draw_palette_swatches(draw, swatches_x, swatches_y, palette, swatch_size, swatch_spacing)
    else:
        # 居中经典排版
        if meta_line:
            bbox_m = draw.textbbox((0, 0), meta_line, font=font_meta)
            meta_w = bbox_m[2] - bbox_m[0]
            draw.text((panel_left + (panel_w - meta_w) // 2, meta_y), meta_line, fill=meta_color, font=font_meta)

        bbox_t  = draw.textbbox((0, 0), title_text, font=font_title)
        title_w = bbox_t[2] - bbox_t[0]
        draw.text((panel_left + (panel_w - title_w) // 2, title_y), title_text, fill=title_color, font=font_title)

        if subtitle_text:
            bbox_s = draw.textbbox((0, 0), subtitle_text, font=font_sub)
            sub_w  = bbox_s[2] - bbox_s[0]
            draw.text((panel_left + (panel_w - sub_w) // 2, sub_y), subtitle_text, fill=sub_color, font=font_sub)

        # 色卡置于右下角
        swatches_w = swatch_size * 4 + swatch_spacing * 3
        swatches_x = panel_left + panel_w - int(panel_w * 0.08) - swatches_w
        swatches_y = panel_top + int(panel_h * 0.88)
        _draw_palette_swatches(draw, swatches_x, swatches_y, palette, swatch_size, swatch_spacing)

    # -------------------------------------------------------------------
    # Stage 5: 全流程 5 阶段进度 100% 完成与耗时汇总报表
    # -------------------------------------------------------------------
    print(f"\n[Stage 5/5] [100%] 🖼️  画廊双联卡片排版渲染完成 ({canvas.width}×{canvas.height}px)")
    if vlm_result and isinstance(vlm_result, dict) and "timings" in vlm_result:
        t_info = vlm_result["timings"]
        s1_t = t_info.get("stage1_s1", 0.0)
        s2_t = t_info.get("stage2_s2", 0.0)
        s3_t = t_info.get("stage3_s3", 0.0)
        s4_t = t_info.get("stage4_s4", 0.0)
        total_pipeline_t = t_info.get("vlm_total", 0.0)
        print("┌── [Scheme4 全流程 5 阶段耗时统计] " + "─" * 38)
        print(f"│ 🔍 [Stage 1/5: 20%] 空间解构与主体骨架 : {s1_t:6.2f}s")
        print(f"│ ✍️  [Stage 2/5: 40%] 文学立意与标题副标 : {s2_t:6.2f}s")
        print(f"│ 🎨 [Stage 3/5: 60%] 核心主焦点造型特征 : {s3_t:6.2f}s")
        print(f"│ 🧩 [Stage 4/5: 80%] 几何晶格与抽色工序 : {s4_t:6.2f}s")
        print(f"│ 🖼️  [Stage 5/5:100%] 画布合成与双联排版 :   完成")
        print(f"│ ⏱️  [总计流水线耗时]                    : {total_pipeline_t:6.2f}s")
        print("└" + "─" * 68)

    return canvas.convert("RGB")


