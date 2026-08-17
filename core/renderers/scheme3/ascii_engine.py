"""
画廊 ASCII 结构解构引擎 (Gallery ASCII Art Engine)

将照片转换为结构化 ASCII 字符矩阵，保留画面的构图骨架、
主体轮廓与明暗层次，支持核心主色着色渲染与高精度等宽字体光栅化。

用于方案3 (Scheme 3) 的 gallery_ascii_diptych 布局。
"""

from __future__ import annotations

import functools
from dataclasses import dataclass, field
from pathlib import Path
from typing import List, Optional, Tuple

import numpy as np
from PIL import Image, ImageDraw, ImageFont

# ── 字符集 ──────────────────────────────────────────────────────────
# Block 字符集（从亮→暗，象牙白背景时深色=实心）
BLOCK_CHARS = " ░▒▓█"
# 精细 ASCII 字符集（从亮→暗）
ASCII_CHARS = " .·:-=+*#%@"

# ── 等宽字体搜索路径（macOS 优先级） ─────────────────────────────────
_MONO_FONT_CANDIDATES = [
    ("/System/Library/Fonts/Menlo.ttc", 0),           # Menlo Regular
    ("/System/Library/Fonts/Monaco.dfont", 0),         # Monaco
    ("/System/Library/Fonts/Courier.dfont", 0),        # Courier
    ("/System/Library/Fonts/SFMono-Regular.otf", 0),   # SF Mono
]


# ── 配置数据类 ──────────────────────────────────────────────────────
@dataclass
class AsciiConfig:
    """ASCII 引擎配置参数"""
    columns: int = 100                        # 字符网格列数
    char_set: str = "block"                   # "block" 或 "ascii"
    edge_enhance: bool = True                 # Sobel 边缘增强开关
    edge_threshold: int = 30                  # 边缘阈值 (0-255)
    color_mode: str = "local_chromatic"       # dominant_mono / local_chromatic / palette_gradient
    font_size: int = 14                       # 等宽字体渲染点数
    bg_color: Tuple[int, int, int] = (243, 240, 232)  # 画布背景色（象牙白）
    invert: bool = False                      # 反转亮暗映射（用于暗底板）
    char_aspect_ratio: float = 0.55           # 字符高宽比校正系数
    n_palette_colors: int = 4                 # 提取的调色板核心色数量


# ── 等宽字体加载 ─────────────────────────────────────────────────────
@functools.lru_cache(maxsize=64)
def get_mono_font(size: int, bold: bool = False) -> ImageFont.FreeTypeFont:
    """查找系统等宽机械终端字体 (Menlo / SF Mono / Monaco / Courier)，返回 Pillow FreeTypeFont 对象。"""
    candidates = [
        ("/System/Library/Fonts/Menlo.ttc", 1 if bold else 0),
        ("/System/Library/Fonts/SFMono-Bold.otf" if bold else "/System/Library/Fonts/SFMono-Regular.otf", 0),
        ("/System/Library/Fonts/Monaco.dfont", 0),
        ("/System/Library/Fonts/Courier.dfont", 0),
    ]
    for path, index in candidates:
        if Path(path).exists():
            try:
                return ImageFont.truetype(path, size=size, index=index)
            except Exception:
                continue
    # 兜底回退
    return ImageFont.load_default()


def _find_mono_font(size: int) -> ImageFont.FreeTypeFont:
    """内部等宽字体获取快捷方式。"""
    return get_mono_font(size, bold=False)


@functools.lru_cache(maxsize=32)
def _char_metrics(font_size: int) -> Tuple[int, int]:
    """返回等宽字符的 (宽度, 高度) 像素值。"""
    mono = _find_mono_font(font_size)
    scratch = Image.new("RGB", (1, 1))
    draw = ImageDraw.Draw(scratch)
    # 用 Block 字符测量（比 M 更大更准确）
    bbox = draw.textbbox((0, 0), "█", font=mono)
    w = max(bbox[2] - bbox[0], 1)
    h = max(bbox[3] - bbox[1], 1)
    return w, h


# ── 核心主色提取 ─────────────────────────────────────────────────────
def extract_palette(
    image: Image.Image,
    n_colors: int = 4,
) -> List[Tuple[int, int, int]]:
    """
    从照片提取核心主色调色板。

    使用 Pillow MEDIANCUT 量化算法，按像素频率排序返回 RGB 元组列表。

    Args:
        image: 输入 RGB 图像。
        n_colors: 提取的颜色数量。

    Returns:
        按频率降序排列的 RGB 元组列表，长度为 n_colors。
    """
    small = image.copy()
    small.thumbnail((150, 150))
    small = small.convert("RGB")

    quantized = small.quantize(colors=n_colors, method=Image.Quantize.MEDIANCUT)
    palette_raw = quantized.getpalette()
    histogram = quantized.histogram()

    color_freq: list[tuple[tuple[int, int, int], int]] = []
    for i in range(n_colors):
        offset = i * 3
        if offset + 2 < len(palette_raw):
            rgb = (palette_raw[offset], palette_raw[offset + 1], palette_raw[offset + 2])
        else:
            rgb = (128, 128, 128)
        freq = histogram[i] if i < len(histogram) else 0
        color_freq.append((rgb, freq))

    color_freq.sort(key=lambda x: -x[1])
    return [c for c, _ in color_freq]


# ── Sobel 边缘检测 ──────────────────────────────────────────────────
def _sobel_edges(gray: np.ndarray) -> np.ndarray:
    """
    纯 NumPy Sobel 边缘检测。

    返回归一化到 [0, 255] 的梯度幅值矩阵。
    """
    g = gray.astype(np.float64)
    padded = np.pad(g, 1, mode="edge")
    h, w = gray.shape

    # Sobel 3×3 核 — 水平与垂直
    sx = np.array([[-1, 0, 1], [-2, 0, 2], [-1, 0, 1]], dtype=np.float64)
    sy = np.array([[-1, -2, -1], [0, 0, 0], [1, 2, 1]], dtype=np.float64)

    gx = np.zeros((h, w), dtype=np.float64)
    gy = np.zeros((h, w), dtype=np.float64)
    for di in range(3):
        for dj in range(3):
            gx += sx[di, dj] * padded[di : di + h, dj : dj + w]
            gy += sy[di, dj] * padded[di : di + h, dj : dj + w]

    mag = np.sqrt(gx * gx + gy * gy)
    peak = mag.max()
    if peak > 0:
        mag = (mag / peak * 255).astype(np.uint8)
    else:
        mag = mag.astype(np.uint8)
    return mag


# ── 字符矩阵构建 ────────────────────────────────────────────────────
def photo_to_ascii_matrix(
    image: Image.Image,
    config: AsciiConfig,
) -> Tuple[List[List[str]], List[List[Tuple[int, int, int]]]]:
    """
    将照片转换为 ASCII 字符矩阵 + 颜色矩阵。

    Args:
        image: 输入 RGB 图像。
        config: ASCII 引擎配置。

    Returns:
        (char_matrix, color_matrix):
        - char_matrix:  二维字符列表 [rows][cols]
        - color_matrix: 二维 RGB 元组列表 [rows][cols]，保留原图对应位置的真实颜色。
    """
    img_rgb = image.convert("RGB")
    img_gray = image.convert("L")

    orig_w, orig_h = img_rgb.size
    cols = config.columns
    rows = max(1, int(cols * (orig_h / orig_w) * config.char_aspect_ratio))

    # 下采样到网格分辨率
    grid_rgb = img_rgb.resize((cols, rows), Image.Resampling.LANCZOS)
    grid_gray = img_gray.resize((cols, rows), Image.Resampling.LANCZOS)

    gray_arr = np.array(grid_gray, dtype=np.uint8)
    rgb_arr = np.array(grid_rgb, dtype=np.uint8)

    # 可选 Sobel 边缘检测
    edge_arr: Optional[np.ndarray] = None
    if config.edge_enhance:
        edge_arr = _sobel_edges(gray_arr)

    # 选择字符集
    chars = BLOCK_CHARS if config.char_set == "block" else ASCII_CHARS
    n_chars = len(chars)

    char_matrix: list[list[str]] = []
    color_matrix: list[list[tuple[int, int, int]]] = []

    for r in range(rows):
        char_row: list[str] = []
        color_row: list[tuple[int, int, int]] = []
        for c in range(cols):
            brightness = int(gray_arr[r, c])

            # 边缘增强：强边缘位置偏向更实的字符
            if edge_arr is not None and edge_arr[r, c] > config.edge_threshold:
                edge_f = min(float(edge_arr[r, c]) / 255.0, 1.0)
                brightness = int(brightness * (1.0 - edge_f * 0.5))

            # 亮度 → 字符索引
            if config.invert:
                idx = int(brightness / 256 * n_chars)
            else:
                idx = int((255 - brightness) / 256 * n_chars)
            idx = min(idx, n_chars - 1)

            char_row.append(chars[idx])
            color_row.append(tuple(rgb_arr[r, c]))

        char_matrix.append(char_row)
        color_matrix.append(color_row)

    return char_matrix, color_matrix


# ── 颜色模式处理 ─────────────────────────────────────────────────────
def apply_color_mode(
    char_matrix: List[List[str]],
    color_matrix: List[List[Tuple[int, int, int]]],
    palette: List[Tuple[int, int, int]],
    mode: str = "local_chromatic",
) -> List[List[Tuple[int, int, int]]]:
    """
    根据颜色模式对颜色矩阵进行二次处理。

    Modes:
        - ``dominant_mono``:    全部字符使用核心主色（单色版画风）。
        - ``local_chromatic``:  保留每个位置的原始真实颜色（默认推荐）。
        - ``palette_gradient``: 基于亮度在调色板颜色之间插值映射。
    """
    if not palette:
        return color_matrix

    if mode == "dominant_mono":
        dominant = palette[0]
        return [[dominant for _ in row] for row in color_matrix]

    if mode == "local_chromatic":
        return color_matrix

    if mode == "dark_chromatic":
        # 暗色颜色系：保留原图自然色相与色彩关系，但压低亮度并融入深邃冷暗质感，高光处保留微光
        result = []
        for crow in color_matrix:
            new_row = []
            for r, g, b in crow:
                lum = 0.299 * r + 0.587 * g + 0.114 * b
                # 动态暗调曲线：高光适度保留，中暗部压深，形成深邃暗调
                factor = 0.45 + (lum / 255.0) * 0.35
                nr = max(10, min(230, int(r * factor)))
                ng = max(18, min(245, int(g * factor * 1.08)))  # 微量提携绿色通道以呼应终端绿
                nb = max(10, min(230, int(b * factor)))
                new_row.append((nr, ng, nb))
            result.append(new_row)
        return result

    if mode == "matrix_green":
        # 纯正黑客终端磷光绿渐变：深墨绿 (0, 38, 15) -> 荧光黑客翠绿 (0, 255, 102)
        c_dark = (0, 38, 15)
        c_bright = (0, 255, 102)
        result = []
        for crow in color_matrix:
            new_row = []
            for r, g, b in crow:
                lum = (0.299 * r + 0.587 * g + 0.114 * b) / 255.0
                nr = int(c_dark[0] * (1 - lum) + c_bright[0] * lum)
                ng = int(c_dark[1] * (1 - lum) + c_bright[1] * lum)
                nb = int(c_dark[2] * (1 - lum) + c_bright[2] * lum)
                new_row.append((nr, ng, nb))
            result.append(new_row)
        return result

    if mode == "dark_matrix_green":
        # 亮色卡纸上的黑客深墨绿系：从深墨绿 (10, 52, 24) 到 中灰绿 (45, 110, 65)
        c_dark = (10, 52, 24)
        c_light = (45, 110, 65)
        result = []
        for crow in color_matrix:
            new_row = []
            for r, g, b in crow:
                lum = (0.299 * r + 0.587 * g + 0.114 * b) / 255.0
                nr = int(c_dark[0] * (1 - lum) + c_light[0] * lum)
                ng = int(c_dark[1] * (1 - lum) + c_light[1] * lum)
                nb = int(c_dark[2] * (1 - lum) + c_light[2] * lum)
                new_row.append((nr, ng, nb))
            result.append(new_row)
        return result

    if mode == "palette_gradient":
        # 按亮度将调色板排序（暗→亮）
        sorted_pal = sorted(palette, key=lambda c: 0.299 * c[0] + 0.587 * c[1] + 0.114 * c[2])
        n_pal = len(sorted_pal)

        result: list[list[tuple[int, int, int]]] = []
        for r_idx, (crow, chrow) in enumerate(zip(color_matrix, char_matrix)):
            new_row: list[tuple[int, int, int]] = []
            for c_idx, color in enumerate(crow):
                lum = 0.299 * color[0] + 0.587 * color[1] + 0.114 * color[2]
                # 映射到调色板索引
                t = lum / 255.0  # 0=暗, 1=亮
                fi = t * (n_pal - 1)
                lo = max(0, min(int(fi), n_pal - 2))
                hi = lo + 1
                frac = fi - lo
                r = int(sorted_pal[lo][0] * (1 - frac) + sorted_pal[hi][0] * frac)
                g = int(sorted_pal[lo][1] * (1 - frac) + sorted_pal[hi][1] * frac)
                b = int(sorted_pal[lo][2] * (1 - frac) + sorted_pal[hi][2] * frac)
                new_row.append((r, g, b))
            result.append(new_row)
        return result

    # 未知模式，原样返回
    return color_matrix


# ── 光栅化渲染 ───────────────────────────────────────────────────────
def rasterize_ascii(
    char_matrix: List[List[str]],
    color_matrix: List[List[Tuple[int, int, int]]],
    config: AsciiConfig,
) -> Image.Image:
    """
    将 ASCII 字符矩阵 + 颜色矩阵光栅化为高精度 Pillow Image。

    使用等宽字体逐字符绘制，空格跳过以保留背景色。

    Returns:
        光栅化后的 RGB Image。
    """
    if not char_matrix or not char_matrix[0]:
        return Image.new("RGB", (100, 100), config.bg_color)

    rows = len(char_matrix)
    cols = len(char_matrix[0])

    mono_font = _find_mono_font(config.font_size)
    char_w, char_h = _char_metrics(config.font_size)

    canvas_w = cols * char_w
    canvas_h = rows * char_h
    canvas = Image.new("RGB", (canvas_w, canvas_h), config.bg_color)
    draw = ImageDraw.Draw(canvas)

    for r in range(rows):
        y = r * char_h
        for c in range(cols):
            ch = char_matrix[r][c]
            if ch == " ":
                continue
            color = color_matrix[r][c] if r < len(color_matrix) and c < len(color_matrix[r]) else (80, 80, 80)
            x = c * char_w
            draw.text((x, y), ch, fill=color, font=mono_font)

    return canvas


# ── 一站式 API ───────────────────────────────────────────────────────
def generate_ascii_art(
    image: Image.Image,
    config: Optional[AsciiConfig] = None,
) -> Tuple[Image.Image, List[Tuple[int, int, int]]]:
    """
    一站式照片 → ASCII 结构艺术画。

    Args:
        image:  输入照片 (Pillow Image)。
        config: ASCII 引擎配置；为 None 时使用默认配置。

    Returns:
        (ascii_image, palette):
        - ascii_image: 光栅化后的 ASCII 结构画 (RGB Image)。
        - palette: 从照片提取的核心主色调色板 (RGB 元组列表)。
    """
    if config is None:
        config = AsciiConfig()

    # 1. 提取核心主色调色板
    palette = extract_palette(image, n_colors=config.n_palette_colors)

    # 2. 生成 ASCII 字符矩阵与原始颜色矩阵
    char_matrix, color_matrix = photo_to_ascii_matrix(image, config)

    # 3. 应用颜色模式
    color_matrix = apply_color_mode(char_matrix, color_matrix, palette, config.color_mode)

    # 4. 光栅化为高精度图片
    ascii_image = rasterize_ascii(char_matrix, color_matrix, config)

    return ascii_image, palette


# ── 自适应终端明暗主题推导 ──────────────────────────────────────────────
def derive_terminal_theme(
    image: Image.Image,
    base_bg: Optional[Tuple[int, int, int]] = None,
) -> dict:
    """
    根据照片本身的真实像素明暗与主色，推导机械终端黑客主题配色方案。

    规则：
        1. 当照片主色为【明亮】时（日景、雪景、雾中山景等）：
           - 背景卡：使用原片主色亮色（温润高明度卡纸，明度 ~94%）；
           - 字色：符合终端对应的黑客深墨绿 (#0A3D1B / #28683B)；
           - ASCII 抽象解构卡：dark_matrix_green（深墨绿阶调），invert=False（天空亮处为空格透亮底，暗处树木等显示深墨绿字符）；
           - 悬浮微阴影：开启。
        2. 当照片主色为【暗色】时（夜景、暗调街景、弱光摄影等）：
           - 背景卡：使用原片主色暗色（深邃黑绿/暗黑底板 #0A0D0A，明度 ~5.5%）；
           - 字色：符合终端对应的荧光高亮黑客绿 (#00FF66 / #009944)；
           - ASCII 抽象解构卡：matrix_green（黑客荧光绿阶调），invert=True（暗处为空格透出暗底，亮处高楼灯光/山峰白雪显示荧光发光字符）；
           - 悬浮微阴影：关闭。

    Returns:
        dict 包含:
            - is_bright (bool)
            - bg_rgb (tuple)
            - text_color_primary (str)
            - text_color_secondary (str)
            - color_mode (str)
            - invert (bool)
            - shadow_enable (bool)
    """
    import colorsys

    # 直接从原始照片真实采样计算亮度分布（严禁使用被强制提亮到 0.95 的背景色）
    thumb = image.copy()
    thumb.thumbnail((120, 120))
    gray_arr = np.array(thumb.convert("L"), dtype=np.float64)
    mean_lum = float(gray_arr.mean())
    median_lum = float(np.median(gray_arr))

    # 综合考量均值与中位数：加权判定整体画面真实明暗
    effective_lum = mean_lum * 0.6 + median_lum * 0.4
    is_bright = effective_lum >= 108.0

    # 提取原照片主色
    palette = extract_palette(image, n_colors=4)
    dominant_rgb = palette[0] if palette else (128, 128, 128)
    dh, dl, ds = colorsys.rgb_to_hls(
        dominant_rgb[0] / 255.0, dominant_rgb[1] / 255.0, dominant_rgb[2] / 255.0
    )

    if is_bright:
        # 亮色主题：根据原片主色调配温润亮卡纸
        new_l = 0.935
        new_s = min(ds, 0.12)
        br, bg, bb = colorsys.hls_to_rgb(dh, new_l, new_s)
        bg_rgb = (int(br * 255), int(bg * 255), int(bb * 255))

        return {
            "is_bright": True,
            "bg_rgb": bg_rgb,
            "text_color_primary": "#0A3D1B",    # 终端深墨绿
            "text_color_secondary": "#28683B",  # 终端深灰绿
            "color_mode": "dark_matrix_green",  # 亮底深墨绿阶调
            "invert": False,                    # 亮处为空格透底
            "shadow_enable": True,
        }
    else:
        # 暗色主题：根据原片主色调配深邃暗黑曜石绿/暗黑底板
        new_l = 0.05
        new_s = min(ds, 0.20)
        br, bg, bb = colorsys.hls_to_rgb(dh, new_l, new_s)
        bg_rgb = (int(br * 255), int(bg * 255), int(bb * 255))

        return {
            "is_bright": False,
            "bg_rgb": bg_rgb,
            "text_color_primary": "#00FF66",    # 纯正荧光黑客高亮绿
            "text_color_secondary": "#009944",  # 终端中暗绿
            "color_mode": "matrix_green",       # 暗底荧光绿阶调
            "invert": True,                     # 暗处为空格透黑底
            "shadow_enable": False,
        }


