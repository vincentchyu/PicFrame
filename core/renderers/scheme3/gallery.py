from dataclasses import dataclass
from pathlib import Path
from PIL import Image, ImageDraw, ImageFilter

from ...fonts import font
from ...metadata import (
    fmt_altitude,
    fmt_artist,
    fmt_copyright,
    fmt_date,
    fmt_ev,
    fmt_focal,
    fmt_gps,
    fmt_model,
    photo_year,
)
from .ascii_engine import (
    AsciiConfig,
    derive_terminal_theme,
    generate_ascii_art,
    get_mono_font,
)


SCHEME3_CONFIG = Path(__file__).resolve().parents[3] / "config" / "schemes" / "scheme3" / "config.yaml"


@dataclass(frozen=True)
class Scheme3Config:
    path: Path
    data: dict

    @classmethod
    def load(cls, path=SCHEME3_CONFIG):
        try:
            import yaml
        except ImportError as exc:
            raise RuntimeError("Scheme3 requires PyYAML; install dependencies from requirements.txt") from exc

        path = Path(path).resolve()
        if not path.exists():
            raise FileNotFoundError(f"Missing scheme3 config: {path}")
        with path.open("r", encoding="utf-8") as f:
            data = yaml.safe_load(f) or {}
        return cls(path, data)

    def artist(self):
        return self.data.get("base", {}).get("artist", "Vincent Chyu")

    def layout(self, layout_name="gallery_mat"):
        layouts = self.data.get("layouts", {})
        if layout_name in layouts:
            return layouts[layout_name]
        return layouts.get("gallery_mat", {})


def _format_exposure_line(exif, separator=" · "):
    parts = []

    # 1. 焦距
    focal = fmt_focal(exif.get("FocalLength"))
    if focal:
        parts.append(focal)

    # 2. 光圈
    f_num = exif.get("FNumber") or exif.get("Aperture")
    if f_num:
        try:
            val = float(f_num)
            parts.append(f"f/{val:g}")
        except Exception:
            parts.append(f"f/{f_num}")

    # 3. 快门速度
    exp_time = exif.get("ExposureTime") or exif.get("ShutterSpeed")
    if exp_time:
        s = str(exp_time).strip()
        if not s.endswith("s") and not s.endswith("S") and "/" in s:
            s = f"{s}s"
        parts.append(s)

    # 4. ISO
    iso = exif.get("ISO")
    if iso:
        parts.append(f"ISO {iso}")

    return separator.join(parts)


def _format_gear_line(context, separator=" · "):
    parts = []
    camera = str(context.camera_model or "").strip()
    lens = str(context.lens_model or "").strip()

    if camera:
        parts.append(camera)
    if lens:
        # 如果相机名称已包含在镜头名中，做适当去重，否则直接展示
        parts.append(lens)

    return separator.join(parts)


def _render_float_shadow(canvas, margin_x, margin_top, photo_w, photo_h, shadow_cfg):
    opacity = float(shadow_cfg.get("opacity", 0.08))
    if opacity <= 0:
        return

    blur_ratio = float(shadow_cfg.get("blur_ratio", 0.02))
    offset_y_ratio = float(shadow_cfg.get("offset_y_ratio", 0.006))

    blur_radius = max(6, int(photo_w * blur_ratio))
    offset_y = max(2, int(photo_h * offset_y_ratio))

    pad = blur_radius * 2
    shadow_w = photo_w + pad * 2
    shadow_h = photo_h + pad * 2

    shadow_layer = Image.new("RGBA", (shadow_w, shadow_h), (0, 0, 0, 0))
    draw = ImageDraw.Draw(shadow_layer)
    alpha = int(255 * opacity)
    draw.rectangle([pad, pad, pad + photo_w, pad + photo_h], fill=(0, 0, 0, alpha))

    blurred_shadow = shadow_layer.filter(ImageFilter.GaussianBlur(blur_radius))
    canvas.paste(
        blurred_shadow,
        (margin_x - pad, margin_top - pad + offset_y),
        blurred_shadow,
    )


def render_scheme3_gallery(context):
    cfg_obj = Scheme3Config.load()
    layout_name = getattr(context, "effective_layout", "") or getattr(context, "layout", "gallery_ascii_terminal")
    cfg = cfg_obj.layout(layout_name)

    # ── 方案3：智能黑客终端与原片主色 ASCII 解构 ──
    return _render_ascii_diptych(context, cfg_obj, cfg)

    # ── 原有 gallery_mat / gallery_flat / gallery_dark 渲染逻辑 ──
    # 打开源照片
    with Image.open(context.photo_path) as src_img:
        photo = src_img.convert("RGB")
    photo_w, photo_h = photo.size

    # 计算边距与画布尺寸
    margin_ratio = float(cfg.get("margin_ratio", 0.065))
    bottom_margin_ratio = float(cfg.get("bottom_margin_ratio", 0.125))

    # 以短边或长边为基准计算四周留白，保证视觉比例稳定
    base_dim = min(photo_w, photo_h)
    margin_x = max(24, int(photo_w * margin_ratio))
    margin_top = max(24, int(photo_h * margin_ratio))
    margin_bottom = max(48, int(photo_h * bottom_margin_ratio))

    canvas_w = photo_w + margin_x * 2
    canvas_h = photo_h + margin_top + margin_bottom

    bg_color = cfg.get("background_color", "#FAFAFA")
    canvas = Image.new("RGB", (canvas_w, canvas_h), bg_color)

    # 绘制悬浮微阴影
    shadow_cfg = cfg.get("shadow", {})
    if shadow_cfg.get("enable", False):
        _render_float_shadow(canvas, margin_x, margin_top, photo_w, photo_h, shadow_cfg)

    # 贴上主照片
    canvas.paste(photo, (margin_x, margin_top))

    # 准备文字排版
    draw = ImageDraw.Draw(canvas)
    typo_cfg = cfg.get("typography", {})
    layout_type = typo_cfg.get("layout_type", "split")
    separator = typo_cfg.get("separator", " · ")
    font_scale = float(typo_cfg.get("font_scale", 0.016))

    primary_font_size = max(14, int(canvas_w * font_scale))
    secondary_font_size = max(11, int(primary_font_size * 0.82))

    font_main = font(primary_font_size, medium=True)
    font_sub = font(secondary_font_size, medium=False)

    text_color_primary = cfg.get("text_color_primary", "#2C2C2C")
    text_color_secondary = cfg.get("text_color_secondary", "#7A7A7A")

    gear_text = _format_gear_line(context, separator=separator)
    exposure_text = _format_exposure_line(context.exif, separator=separator)
    artist_text = f"© {photo_year(context.exif)} {cfg_obj.artist()}"

    # 垂直排版基准位置
    text_baseline_y = margin_top + photo_h + int(margin_bottom * 0.35)
    line_gap = int(primary_font_size * 1.35)

    if layout_type == "center":
        # 居中极简排版
        all_parts = []
        if gear_text:
            all_parts.append(gear_text)
        if exposure_text:
            all_parts.append(exposure_text)
        full_line = separator.join(all_parts)

        if full_line:
            bbox = draw.textbbox((0, 0), full_line, font=font_main)
            text_w = bbox[2] - bbox[0]
            start_x = margin_x + (photo_w - text_w) // 2
            draw.text((start_x, text_baseline_y), full_line, fill=text_color_primary, font=font_main)

        # 副行（年份与作者，极淡小字）
        if artist_text:
            bbox_sub = draw.textbbox((0, 0), artist_text, font=font_sub)
            sub_w = bbox_sub[2] - bbox_sub[0]
            start_sub_x = margin_x + (photo_w - sub_w) // 2
            draw.text((start_sub_x, text_baseline_y + line_gap), artist_text, fill=text_color_secondary, font=font_sub)

    else:
        # Split 两段式排版（左侧器材/作者，右侧曝光参数）
        # 1. 左侧第一行：器材
        if gear_text:
            draw.text((margin_x, text_baseline_y), gear_text, fill=text_color_primary, font=font_main)

        # 2. 左侧第二行：作者与年份
        if artist_text:
            draw.text((margin_x, text_baseline_y + line_gap), artist_text, fill=text_color_secondary, font=font_sub)

        # 3. 右侧第一行：曝光参数
        if exposure_text:
            bbox_exp = draw.textbbox((0, 0), exposure_text, font=font_main)
            exp_w = bbox_exp[2] - bbox_exp[0]
            right_x = margin_x + photo_w - exp_w
            draw.text((right_x, text_baseline_y), exposure_text, fill=text_color_primary, font=font_main)

        # 4. 右侧第二行：拍摄日期 / 曝光补偿
        date_str = fmt_date(context.exif)
        ev_str = fmt_ev(context.exif.get("ExposureCompensation"))
        right_sub_parts = [p for p in [ev_str, date_str] if p]
        right_sub_text = separator.join(right_sub_parts)
        if right_sub_text:
            bbox_rsub = draw.textbbox((0, 0), right_sub_text, font=font_sub)
            rsub_w = bbox_rsub[2] - bbox_rsub[0]
            right_sub_x = margin_x + photo_w - rsub_w
            draw.text((right_sub_x, text_baseline_y + line_gap), right_sub_text, fill=text_color_secondary, font=font_sub)

    return canvas


# ──────────────────────────────────────────────────────────────────────
# gallery_ascii_diptych 画廊 ASCII 双联装裱渲染
# ──────────────────────────────────────────────────────────────────────

def _draw_palette_swatches(draw, palette, x, y, swatch_size, gap, canvas_w, outline_color="#C0C0C0"):
    """在指定位置绘制核心主色色卡方块。"""
    total_w = len(palette) * swatch_size + (len(palette) - 1) * gap
    start_x = x + (canvas_w - x * 2 - total_w) // 2
    for i, color in enumerate(palette):
        sx = start_x + i * (swatch_size + gap)
        draw.rectangle([sx, y, sx + swatch_size, y + swatch_size], fill=color)
        draw.rectangle([sx, y, sx + swatch_size, y + swatch_size], outline=outline_color, width=1)


def _render_ascii_diptych(context, cfg_obj, cfg):
    """
    画廊 ASCII 双联与机械终端装裱渲染器。

    视觉原则：
        1. 当处于终端模式 (gallery_ascii_terminal) 时：
           - 照片主色明亮 -> 背景卡使用主色亮色，字色使用符合终端的黑客深墨绿 (#0A3D1B)，ASCII 深墨绿解构，亮处留白透底；
           - 照片主色暗色 -> 背景卡使用主色暗黑，字色使用符合终端的高亮黑客荧光绿 (#00FF66)，ASCII 荧光绿解构，暗处透黑底；
        2. 全量文字统一使用英文等宽/机械终端字体 (Menlo / SF Mono / Monaco / Courier)。
    """
    # ── 打开源照片 ──
    with Image.open(context.photo_path) as src_img:
        photo = src_img.convert("RGB")
    photo_w, photo_h = photo.size

    layout_name = getattr(context, "effective_layout", "") or getattr(context, "layout", "")
    is_terminal_layout = (layout_name == "gallery_ascii_terminal")

    # ── 终端模式自适应明暗调色推导 ──
    if is_terminal_layout:
        theme = derive_terminal_theme(photo)
        bg_rgb = theme["bg_rgb"]
        bg_is_dark = not theme["is_bright"]
        text_color_primary = cfg.get("text_color_primary") or theme["text_color_primary"]
        text_color_secondary = cfg.get("text_color_secondary") or theme["text_color_secondary"]
        auto_color_mode = theme["color_mode"]
        auto_invert = theme["invert"]
        shadow_enable = theme["shadow_enable"]
    else:
        # 普通 diptych 模式
        raw_bg = cfg.get("background_color", "auto")
        if raw_bg == "auto":
            bg_rgb = getattr(context, "bg", None) or (243, 240, 232)
        else:
            bg_rgb = _hex_to_rgb(raw_bg)
        bg_lum = 0.299 * bg_rgb[0] + 0.587 * bg_rgb[1] + 0.114 * bg_rgb[2]
        bg_is_dark = bg_lum < 128
        text_color_primary = cfg.get("text_color_primary", "#2C2C2C")
        text_color_secondary = cfg.get("text_color_secondary", "#7A7A7A")
        auto_color_mode = "dark_chromatic" if bg_is_dark else "local_chromatic"
        auto_invert = bg_is_dark
        shadow_cfg = cfg.get("shadow", {})
        shadow_enable = bool(shadow_cfg.get("enable", not bg_is_dark))

    # ── 解析排版与边距配置 ──
    margin_ratio = float(cfg.get("margin_ratio", 0.04))
    bottom_margin_ratio = float(cfg.get("bottom_margin_ratio", 0.08))
    ascii_cfg = cfg.get("ascii", {})
    panel_height_ratio = float(ascii_cfg.get("panel_height_ratio", 0.35))
    typo_cfg = cfg.get("typography", {})
    separator = typo_cfg.get("separator", " · ")
    font_scale = float(typo_cfg.get("font_scale", 0.013))

    margin_x = max(24, int(photo_w * margin_ratio))
    margin_top = max(24, int(photo_h * margin_ratio))
    margin_bottom = max(48, int(photo_h * bottom_margin_ratio))

    # ── 自动判定横构图与竖构图分流 ──
    is_portrait = photo_h > photo_w
    if is_portrait:
        return _render_ascii_diptych_portrait_square(
            context=context,
            cfg_obj=cfg_obj,
            cfg=cfg,
            photo=photo,
            photo_w=photo_w,
            photo_h=photo_h,
            bg_rgb=bg_rgb,
            bg_is_dark=bg_is_dark,
            text_color_primary=text_color_primary,
            text_color_secondary=text_color_secondary,
            auto_color_mode=auto_color_mode,
            auto_invert=auto_invert,
            shadow_enable=shadow_enable,
            separator=separator,
            font_scale=font_scale,
            margin_ratio=margin_ratio,
            ascii_cfg=ascii_cfg,
        )

    # ──────────────────────────────────────────────────────────────────
    # 横构图：1:1 正方形画布中的上下 HUD 结构 (Square 1:1 Landscape HUD)
    # ──────────────────────────────────────────────────────────────────
    # ── 动态推导 1:1 正方形画布尺寸 ──
    # 以照片宽度为主导，计算安全画廊外边距
    margin = max(24, int(photo_w * margin_ratio))
    canvas_size = photo_w + margin * 2

    # 原片在 1:1 正方形中居中偏上放置
    photo_x = margin
    photo_y = margin

    # HUD 控制台舱体尺寸（宽度与照片严格等宽）
    box_x = margin
    box_w = photo_w
    gap_photo_box = max(16, int(canvas_size * 0.02))
    box_y = photo_y + photo_h + gap_photo_box

    # HUD 舱体高度精确填充到底部安全边距（确保整张画布严格 1:1）
    box_h = canvas_size - margin - box_y

    # 舱体微反差底色与 HUD 边框色调
    if bg_is_dark:
        box_bg_rgb = (max(0, bg_rgb[0] + 5), max(0, bg_rgb[1] + 7), max(0, bg_rgb[2] + 5))
        hud_border = "#1B4D2B"
        hud_header_tag = "#00FF66"
        label_color = "#009944"
        val_color = "#39FF14"
        divider_color = "#12331C"
        swatch_border = "#00FF66"
    else:
        box_bg_rgb = (max(0, bg_rgb[0] - 6), max(0, bg_rgb[1] - 6), max(0, bg_rgb[2] - 8))
        hud_border = "#8EA896"
        hud_header_tag = "#0A3D1B"
        label_color = "#28683B"
        val_color = "#082B13"
        divider_color = "#BDC9BF"
        swatch_border = "#28683B"

    # ── 构建 ASCII 引擎配置 ──
    cfg_invert = ascii_cfg.get("invert")
    final_invert = auto_invert if cfg_invert is None else bool(cfg_invert)
    final_color_mode = str(ascii_cfg.get("color_mode") or auto_color_mode)

    ascii_config = AsciiConfig(
        columns=int(ascii_cfg.get("columns", 110)),
        char_set=str(ascii_cfg.get("char_set", "block")),
        edge_enhance=bool(ascii_cfg.get("edge_enhance", True)),
        edge_threshold=int(ascii_cfg.get("edge_threshold", 30)),
        color_mode=final_color_mode,
        font_size=int(ascii_cfg.get("font_size", 14)),
        bg_color=box_bg_rgb,
        invert=final_invert,
        n_palette_colors=int(ascii_cfg.get("n_palette_colors", 4)),
    )

    ascii_art, palette = generate_ascii_art(photo, ascii_config)
    ascii_art_w, ascii_art_h = ascii_art.size

    # ── 等宽机械字体字阶 ──
    primary_font_size = max(11, int(canvas_size * font_scale * 0.9))
    header_font_size = max(10, int(primary_font_size * 0.85))
    line_gap = int(primary_font_size * 1.4)
    swatch_size = max(12, int(primary_font_size * 1.05))
    swatch_gap = int(swatch_size * 0.5)

    pad_x = max(16, int(box_w * 0.03))
    pad_y = max(12, int(box_h * 0.04))

    header_h = line_gap
    divider_h = max(6, int(line_gap * 0.5))
    meta_rows = 4  # GEAR, EXIF, GEO, AUTH & TONE
    meta_section_h = meta_rows * line_gap

    # ── 抽象卡比例严格等于原图比例 ──
    aspect_ratio = photo_w / photo_h if photo_h > 0 else 1.0
    avail_inner_h = max(30, box_h - (pad_y * 2 + header_h * 2 + divider_h + meta_section_h + int(pad_y * 0.8)))
    avail_inner_w = box_w - pad_x * 2

    target_ascii_h = min(avail_inner_h, int(avail_inner_w / aspect_ratio))
    target_ascii_w = int(target_ascii_h * aspect_ratio)

    ascii_resized = ascii_art.resize((target_ascii_w, target_ascii_h), Image.Resampling.LANCZOS)

    # ── 创建 1:1 正方形大画布 ──
    canvas = Image.new("RGB", (canvas_size, canvas_size), bg_rgb)

    # ── 绘制照片悬浮微阴影 ──
    shadow_cfg = cfg.get("shadow", {})
    if shadow_enable and shadow_cfg.get("enable", True):
        _render_float_shadow(canvas, photo_x, photo_y, photo_w, photo_h, shadow_cfg)

    # ── 粘贴上方摄影原作（100% 原始比例与细节） ──
    canvas.paste(photo, (photo_x, photo_y))

    # ── 绘制下方 HUD 控制台舱体容器 ──
    draw = ImageDraw.Draw(canvas)
    draw.rectangle([box_x, box_y, box_x + box_w, box_y + box_h], fill=box_bg_rgb, outline=hud_border, width=1)

    font_mono_main = get_mono_font(primary_font_size, bold=True)
    font_mono_sub = get_mono_font(primary_font_size, bold=False)
    font_mono_header = get_mono_font(header_font_size, bold=True)

    cur_y = box_y + pad_y

    # Section 1 Header: [01 / ASCII MATRIX DECODE] ────── [STATUS: OK]
    tag_left = "[01 / ASCII MATRIX DECODE]"
    tag_right = "[STATUS: 24-BIT · OK]"
    draw.text((box_x + pad_x, cur_y), tag_left, fill=hud_header_tag, font=font_mono_header)

    bbox_tr = draw.textbbox((0, 0), tag_right, font=font_mono_header)
    tr_w = bbox_tr[2] - bbox_tr[0]
    draw.text((box_x + box_w - pad_x - tr_w, cur_y), tag_right, fill=label_color, font=font_mono_header)

    cur_y += header_h + int(pad_y * 0.3)

    # 粘贴 ASCII 结构画（居中于舱体视口内，比例严格等于原图）
    ascii_paste_x = box_x + (box_w - target_ascii_w) // 2
    canvas.paste(ascii_resized, (ascii_paste_x, cur_y))
    cur_y += target_ascii_h + int(pad_y * 0.6)

    # Section 分割线
    draw.line([box_x + pad_x, cur_y, box_x + box_w - pad_x, cur_y], fill=divider_color, width=1)
    cur_y += divider_h

    # Section 2 Header: [02 / TELEMETRY DATA]
    draw.text((box_x + pad_x, cur_y), "[02 / TELEMETRY DATA]", fill=hud_header_tag, font=font_mono_header)
    cur_y += header_h + int(pad_y * 0.3)

    # Key-Value 遥测数据网格
    gear_val = _format_gear_line(context, separator=" · ")
    exif_val = _format_exposure_line(context.exif, separator=" · ")
    gps_val = fmt_gps(context.exif) or "N/A"
    artist_val = fmt_artist(context.exif, cfg_obj.artist())

    def _draw_kv(d, label, value, y_pos, val_f=font_mono_main):
        lbl_text = f"{label:<7} :: "
        d.text((box_x + pad_x, y_pos), lbl_text, fill=label_color, font=font_mono_header)
        bbox_lbl = d.textbbox((0, 0), lbl_text, font=font_mono_header)
        lbl_w = bbox_lbl[2] - bbox_lbl[0]
        d.text((box_x + pad_x + lbl_w, y_pos), value, fill=val_color, font=val_f)

    if gear_val:
        _draw_kv(draw, "GEAR", gear_val, cur_y)
        cur_y += line_gap

    if exif_val:
        _draw_kv(draw, "EXIF", exif_val, cur_y)
        cur_y += line_gap

    if gps_val and gps_val != "N/A":
        _draw_kv(draw, "GEO", gps_val, cur_y, val_f=font_mono_sub)
        cur_y += line_gap

    # 第四行：AUTH 署名 + TONE 色卡
    lbl_auth = "AUTH    :: "
    draw.text((box_x + pad_x, cur_y), lbl_auth, fill=label_color, font=font_mono_header)
    bbox_la = draw.textbbox((0, 0), lbl_auth, font=font_mono_header)
    la_w = bbox_la[2] - bbox_la[0]
    draw.text((box_x + pad_x + la_w, cur_y), artist_val, fill=val_color, font=font_mono_sub)

    # 右侧嵌入色卡
    if palette:
        total_swatches_w = len(palette) * swatch_size + (len(palette) - 1) * swatch_gap
        swatch_start_x = box_x + box_w - pad_x - total_swatches_w
        lbl_tone = "TONE :: "
        bbox_lt = draw.textbbox((0, 0), lbl_tone, font=font_mono_header)
        lt_w = bbox_lt[2] - bbox_lt[0]
        draw.text((swatch_start_x - lt_w - 6, cur_y), lbl_tone, fill=label_color, font=font_mono_header)

        for i, color in enumerate(palette):
            sx = swatch_start_x + i * (swatch_size + swatch_gap)
            draw.rectangle([sx, cur_y + 1, sx + swatch_size, cur_y + 1 + swatch_size], fill=color)
            draw.rectangle([sx, cur_y + 1, sx + swatch_size, cur_y + 1 + swatch_size], outline=swatch_border, width=1)

    return canvas


def _render_ascii_diptych_portrait_square(
    context,
    cfg_obj,
    cfg,
    photo,
    photo_w,
    photo_h,
    bg_rgb,
    bg_is_dark,
    text_color_primary,
    text_color_secondary,
    auto_color_mode,
    auto_invert,
    shadow_enable,
    separator,
    font_scale,
    margin_ratio,
    ascii_cfg,
):
    """
    竖构图 (photo_h > photo_w) 专用 1:1 正方形画布左右 HUD 结构。

    左侧：忠实摄影原作主画幅（主导视觉，严格保留原始竖图比例）
    右侧：1:1 自适应等高 HUD 控制台仪表舱：
          - 顶部：[01 / MATRIX DECODE] 状态栏
          - 中部：ASCII 结构画视口（比例严格等于原图，居中呈现）
          - 底部：[02 / TELEMETRY] 沉底结构化遥测数据网格（自适应拆行/换行，绝不溢出）
    """
    # ── 动态推导 1:1 正方形画布尺寸 ──
    margin = max(24, int(photo_h * margin_ratio))
    canvas_size = photo_h + margin * 2

    # 原片在 1:1 正方形中左侧放置
    photo_x = margin
    photo_y = margin

    # 右侧 HUD 控制台尺寸（与左侧照片严格 1:1 等高对齐）
    gap_x = max(16, int(canvas_size * 0.02))
    box_x = photo_x + photo_w + gap_x
    box_y = margin
    box_h = photo_h

    # 宽度精确填充到右侧安全边距（确保整张画布严格 1:1）
    box_w = canvas_size - margin - box_x

    # 舱体微反差底色与 HUD 边框色调
    if bg_is_dark:
        box_bg_rgb = (max(0, bg_rgb[0] + 5), max(0, bg_rgb[1] + 7), max(0, bg_rgb[2] + 5))
        hud_border = "#1B4D2B"
        hud_header_tag = "#00FF66"
        label_color = "#009944"
        val_color = "#39FF14"
        divider_color = "#12331C"
        swatch_border = "#00FF66"
    else:
        box_bg_rgb = (max(0, bg_rgb[0] - 6), max(0, bg_rgb[1] - 6), max(0, bg_rgb[2] - 8))
        hud_border = "#8EA896"
        hud_header_tag = "#0A3D1B"
        label_color = "#28683B"
        val_color = "#082B13"
        divider_color = "#BDC9BF"
        swatch_border = "#28683B"

    # 创建 1:1 正方形画布
    canvas = Image.new("RGB", (canvas_size, canvas_size), bg_rgb)

    # ── 绘制左侧照片悬浮微阴影 ──
    shadow_cfg = cfg.get("shadow", {})
    if shadow_enable and shadow_cfg.get("enable", True):
        _render_float_shadow(canvas, photo_x, photo_y, photo_w, photo_h, shadow_cfg)

    # ── 粘贴左侧摄影原作（100% 原始比例） ──
    canvas.paste(photo, (photo_x, photo_y))

    # ── 绘制右侧 HUD 舱体容器 ──
    draw = ImageDraw.Draw(canvas)
    draw.rectangle([box_x, box_y, box_x + box_w, box_y + box_h], fill=box_bg_rgb, outline=hud_border, width=1)

    # ── 提取遥测参数并做竖版结构化拆解 ──
    cam_val = getattr(context, "camera_model", "") or (fmt_model(context.exif) if isinstance(getattr(context, "exif", None), dict) else "")
    lens_val = getattr(context, "lens_model", "")

    exif = getattr(context, "exif", {}) if isinstance(getattr(context, "exif", None), dict) else {}
    focal = fmt_focal(exif.get("FocalLength"))
    fnum = exif.get("FNumber")
    fnum_str = f"f/{fnum}" if fnum else ""
    exp_time = str(exif.get("ExposureTime") or "")
    if exp_time and not exp_time.endswith("s"):
        exp_time = f"{exp_time}s"
    iso = exif.get("ISO")
    iso_str = f"ISO {iso}" if iso else ""
    ev_val = fmt_ev(exif.get("ExposureCompensation"))

    focal_opt = " · ".join([t for t in [focal, fnum_str] if t])
    shutter_opt = " · ".join([t for t in [exp_time, iso_str, ev_val] if t])
    gps_val = fmt_gps(exif) or ""
    artist_val = fmt_artist(exif, cfg_obj.artist())

    pad_x = max(14, int(box_w * 0.045))
    pad_y = max(14, int(box_h * 0.025))
    max_text_w = box_w - pad_x * 2

    # 构造竖版结构化行列表
    kv_items = []
    if cam_val:
        kv_items.append(("MODEL", cam_val, True))
    if lens_val:
        kv_items.append(("LENS", lens_val, True))
    if focal_opt:
        kv_items.append(("FOCAL", focal_opt, True))
    if shutter_opt:
        kv_items.append(("SHUTTER", shutter_opt, True))
    if gps_val:
        kv_items.append(("GEO", gps_val, False))
    if artist_val:
        kv_items.append(("AUTH", artist_val, False))

    # ── 智能自适应计算字阶（Auto-Fit） ──
    primary_font_size = max(10, int(box_w * 0.038))
    while primary_font_size > 8:
        f_test = get_mono_font(primary_font_size, bold=True)
        f_hdr = get_mono_font(int(primary_font_size * 0.85), bold=True)
        overflow = False
        for label, val, is_bold in kv_items:
            lbl_text = f"{label:<7} :: "
            bbox_l = draw.textbbox((0, 0), lbl_text, font=f_hdr)
            bbox_v = draw.textbbox((0, 0), val, font=f_test)
            line_w = (bbox_l[2] - bbox_l[0]) + (bbox_v[2] - bbox_v[0])
            if line_w > max_text_w:
                overflow = True
                break
        if not overflow:
            break
        primary_font_size -= 1

    header_font_size = max(8, int(primary_font_size * 0.85))
    line_gap = int(primary_font_size * 1.45)
    swatch_size = max(10, int(primary_font_size * 1.05))
    swatch_gap = int(swatch_size * 0.5)

    font_mono_main = get_mono_font(primary_font_size, bold=True)
    font_mono_sub = get_mono_font(primary_font_size, bold=False)
    font_mono_header = get_mono_font(header_font_size, bold=True)

    header_h = line_gap
    divider_h = max(6, int(line_gap * 0.5))

    # ── 计算底部遥测区所需总高度并将其牢牢固定在底部（Bottom-Anchored） ──
    num_meta_lines = len(kv_items) + 1  # 额外 +1 为色卡行
    telemetry_content_h = header_h + int(pad_y * 0.3) + num_meta_lines * line_gap
    telemetry_start_y = box_y + box_h - pad_y - telemetry_content_h
    divider_y = telemetry_start_y - divider_h - int(pad_y * 0.3)

    # ── 构建右侧 ASCII 引擎 ──
    cfg_invert = ascii_cfg.get("invert")
    final_invert = auto_invert if cfg_invert is None else bool(cfg_invert)
    final_color_mode = str(ascii_cfg.get("color_mode") or auto_color_mode)

    ascii_config = AsciiConfig(
        columns=int(ascii_cfg.get("columns", 70)),
        char_set=str(ascii_cfg.get("char_set", "block")),
        edge_enhance=bool(ascii_cfg.get("edge_enhance", True)),
        edge_threshold=int(ascii_cfg.get("edge_threshold", 30)),
        color_mode=final_color_mode,
        font_size=int(ascii_cfg.get("font_size", 14)),
        bg_color=box_bg_rgb,
        invert=final_invert,
        n_palette_colors=int(ascii_cfg.get("n_palette_colors", 4)),
    )

    ascii_art, palette = generate_ascii_art(photo, ascii_config)
    ascii_art_w, ascii_art_h = ascii_art.size

    # ── 抽象卡比例严格等于原图比例 (photo_w / photo_h)，在上半部视口内居中 ──
    ascii_avail_top = box_y + pad_y + header_h + int(pad_y * 0.3)
    ascii_avail_bottom = divider_y - int(pad_y * 0.4)
    avail_ascii_h = max(30, ascii_avail_bottom - ascii_avail_top)
    avail_ascii_w = box_w - pad_x * 2

    aspect_ratio = photo_w / photo_h if photo_h > 0 else 1.0
    target_ascii_h = min(avail_ascii_h, int(avail_ascii_w / aspect_ratio))
    target_ascii_w = int(target_ascii_h * aspect_ratio)

    ascii_resized = ascii_art.resize((target_ascii_w, target_ascii_h), Image.Resampling.LANCZOS)

    # ── 1. 顶部 Header: [01 / MATRIX DECODE] ────── [STATUS: OK] ──
    top_y = box_y + pad_y
    draw.text((box_x + pad_x, top_y), "[01 / MATRIX DECODE]", fill=hud_header_tag, font=font_mono_header)
    bbox_tr = draw.textbbox((0, 0), "[STATUS: OK]", font=font_mono_header)
    draw.text((box_x + box_w - pad_x - (bbox_tr[2] - bbox_tr[0]), top_y), "[STATUS: OK]", fill=label_color, font=font_mono_header)

    # ── 2. 中部：粘贴 ASCII 结构画（在上半视口居中） ──
    ascii_paste_x = box_x + (box_w - target_ascii_w) // 2
    ascii_paste_y = ascii_avail_top + (avail_ascii_h - target_ascii_h) // 2
    canvas.paste(ascii_resized, (ascii_paste_x, ascii_paste_y))

    # ── 3. 分割线 ──
    draw.line([box_x + pad_x, divider_y, box_x + box_w - pad_x, divider_y], fill=divider_color, width=1)

    # ── 4. 底部：沉底 [02 / TELEMETRY] 遥测数据网格 ──
    cur_y = telemetry_start_y
    draw.text((box_x + pad_x, cur_y), "[02 / TELEMETRY]", fill=hud_header_tag, font=font_mono_header)
    cur_y += header_h + int(pad_y * 0.3)

    def _draw_kv_portrait(d, label, value, y_pos, is_bold=True):
        lbl_text = f"{label:<7} :: "
        d.text((box_x + pad_x, y_pos), lbl_text, fill=label_color, font=font_mono_header)
        bbox_lbl = d.textbbox((0, 0), lbl_text, font=font_mono_header)
        lbl_w = bbox_lbl[2] - bbox_lbl[0]
        val_font = font_mono_main if is_bold else font_mono_sub
        d.text((box_x + pad_x + lbl_w, y_pos), value, fill=val_color, font=val_font)

    for label, val, is_bold in kv_items:
        _draw_kv_portrait(draw, label, val, cur_y, is_bold=is_bold)
        cur_y += line_gap

    # 色卡行
    if palette:
        lbl_tone = "TONE    :: "
        draw.text((box_x + pad_x, cur_y), lbl_tone, fill=label_color, font=font_mono_header)
        bbox_lt = draw.textbbox((0, 0), lbl_tone, font=font_mono_header)
        lt_w = bbox_lt[2] - bbox_lt[0]
        swatch_x = box_x + pad_x + lt_w

        for i, color in enumerate(palette):
            sx = swatch_x + i * (swatch_size + swatch_gap)
            draw.rectangle([sx, cur_y + 1, sx + swatch_size, cur_y + 1 + swatch_size], fill=color)
            draw.rectangle([sx, cur_y + 1, sx + swatch_size, cur_y + 1 + swatch_size], outline=swatch_border, width=1)

    return canvas


def _hex_to_rgb(hex_color: str) -> tuple:
    """将 #RRGGBB 十六进制颜色转换为 RGB 元组。"""
    hex_color = hex_color.lstrip("#")
    if len(hex_color) != 6:
        return (243, 240, 232)
    return (int(hex_color[0:2], 16), int(hex_color[2:4], 16), int(hex_color[4:6], 16))





