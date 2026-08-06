from PIL import Image, ImageDraw

from ...config import CARD_R, CANVAS_H, CANVAS_W, INFO_Y, OUTER_PAD, PHOTO_H, PHOTO_W, PHOTO_X, PHOTO_Y
from ...drawing import (
    draw_centered_rich_lens_params,
    draw_centered_wrapped_text,
    draw_rich_lens_params,
    draw_wrapped_text,
)
from ...fonts import font
from ...metadata import split_lens_display_name
from ...rendering import blend_rgb, calculate_card_scale, contain_fit, new_card_canvas, paste_contained


def draw_top_gps(canvas, text, bg, scale=1.0):
    if not text:
        return
    canvas_w, _ = canvas.size
    f = font(round(19 * scale), False)
    overlay = Image.new("RGBA", canvas.size, (0, 0, 0, 0))
    draw = ImageDraw.Draw(overlay)
    bbox = draw.textbbox((0, 0), text, font=f)
    text_w = bbox[2] - bbox[0]
    text_h = bbox[3] - bbox[1]
    pad_x = round(15 * scale)
    pill_h = round(31 * scale)
    pill_w = text_w + pad_x * 2
    pill_x = round((canvas_w - pill_w) / 2)
    pill_y = round(19 * scale)
    fill = (*blend_rgb(bg, (255, 255, 255), 0.34), 160)
    draw.rounded_rectangle(
        (pill_x, pill_y, pill_x + pill_w, pill_y + pill_h),
        radius=round(11 * scale),
        fill=fill,
        outline=(*blend_rgb(bg, (255, 255, 255), 0.55), 90),
        width=max(1, round(1 * scale)),
    )
    tx = pill_x + pad_x - bbox[0]
    ty = pill_y + round((pill_h - text_h) / 2) - bbox[1] - max(1, round(1 * scale))
    draw.text((tx, ty), text, fill=(45, 45, 45, 118), font=f)
    canvas.alpha_composite(overlay)


def draw_copyright_overlay(canvas, text, bg, scale=1.0):
    if not text:
        return
    canvas_w, canvas_h = canvas.size
    f = font(round(18 * scale), True)
    overlay = Image.new("RGBA", canvas.size, (0, 0, 0, 0))
    draw = ImageDraw.Draw(overlay)
    bbox = draw.textbbox((0, 0), text, font=f)
    text_w = bbox[2] - bbox[0]
    text_h = bbox[3] - bbox[1]
    pad_x = round(18 * scale)
    pill_h = round(35 * scale)
    pill_w = text_w + pad_x * 2
    pill_x = round((canvas_w - pill_w) / 2)
    pill_y = canvas_h - round(45 * scale)
    fill = (*blend_rgb(bg, (255, 255, 255), 0.34), 210)
    draw.rounded_rectangle(
        (pill_x, pill_y, pill_x + pill_w, pill_y + pill_h),
        radius=round(12 * scale),
        fill=fill,
        outline=(*blend_rgb(bg, (255, 255, 255), 0.55), 120),
        width=max(1, round(1 * scale)),
    )
    tx = pill_x + pad_x - bbox[0]
    ty = pill_y + round((pill_h - text_h) / 2) - bbox[1] - max(1, round(1 * scale))
    draw.text((tx, ty), text, fill=(38, 38, 38, 150), font=f)
    canvas.alpha_composite(overlay)


def compact_param_lines(items):
    if len(items) <= 4:
        return items

    rows = []
    pairs = [
        items[0:2],
        items[2:4],
        items[4:6],
    ]
    for pair in pairs:
        if pair:
            rows.append(" | ".join(str(x) for x in pair if x))
    return rows


def draw_asset(canvas, path, center_x, center_y, max_w, max_h):
    img = Image.open(path).convert("RGBA")
    fitted = contain_fit(img, max_w, max_h)
    x = round(center_x - fitted.width / 2)
    y = round(center_y - fitted.height / 2)
    canvas.alpha_composite(fitted, (x, y))


def draw_portrait_card(context):
    photo_path = context.photo_path
    bg = context.bg
    camera_png = context.camera_png
    lens_png = context.lens_png
    camera_model = context.camera_model
    lens_model = context.lens_model
    line_items = context.line_items

    main = Image.open(photo_path).convert("RGB")
    raw_w, raw_h = main.size

    # 照片无损放置：照片在卡片中 100% 保持 1:1 原始像素（0 缩放下采样）
    scale = raw_w / PHOTO_W

    photo_box_w = raw_w
    photo_box_h = raw_h
    photo_x = round(PHOTO_X * scale)
    photo_y = round(PHOTO_Y * scale)
    photo_bottom = photo_y + photo_box_h

    # 卡片总高度随照片实际像素高度自适应延伸
    info_area_h = round(698 * scale)
    canvas_w = round(CANVAS_W * scale)
    canvas_h = photo_bottom + info_area_h

    outer_pad = round(OUTER_PAD * scale)
    card_r = round(CARD_R * scale)
    canvas = new_card_canvas(canvas_w, canvas_h, bg, outer_pad=outer_pad, card_r=card_r)

    photo_box = (photo_x, photo_y, photo_x + photo_box_w, photo_y + photo_box_h)
    paste_contained(
        canvas,
        main,
        photo_box,
        top_radius=round(24 * scale),
    )

    draw = ImageDraw.Draw(canvas)
    ink = (30, 30, 30, 255)
    muted = (76, 76, 76, 255)

    left_x = round(126 * scale)
    right_x = round(584 * scale)
    text_w = canvas_w - outer_pad - right_x - round(64 * scale)
    camera_area_y = photo_bottom + round(50 * scale)
    lens_area_y = camera_area_y + round(300 * scale)
    cam_y = camera_area_y + round(128 * scale)
    lens_y = lens_area_y + round(132 * scale)

    draw_asset(canvas, camera_png, left_x + round(126 * scale), cam_y, round(330 * scale), round(238 * scale))
    draw_asset(canvas, lens_png, left_x + round(126 * scale), lens_y, round(314 * scale), round(232 * scale))
    y = camera_area_y + round(48 * scale)
    y = draw_wrapped_text(draw, (right_x, y), camera_model, ink, round(40 * scale), text_w, True, max_lines=2, line_gap=round(8 * scale)) + round(14 * scale)
    for item in compact_param_lines(line_items[:6]):
        y = draw_wrapped_text(draw, (right_x, y), item, muted, round(30 * scale), text_w, False, max_lines=1, line_gap=round(6 * scale)) + round(8 * scale)

    lens_family, lens_params = split_lens_display_name(lens_model)
    y = draw_wrapped_text(draw, (right_x, lens_area_y + round(82 * scale)), lens_family, ink, round(40 * scale), text_w, True, max_lines=2, line_gap=round(6 * scale)) + round(16 * scale)
    draw_rich_lens_params(draw, (right_x, y), lens_params, muted, round(30 * scale), text_w, max_lines=2, line_gap=round(8 * scale))
    return canvas


def draw_landscape_card(context):
    photo_path = context.photo_path
    bg = context.bg
    camera_png = context.camera_png
    lens_png = context.lens_png
    camera_model = context.camera_model
    lens_model = context.lens_model
    line_items = context.line_items

    main = Image.open(photo_path).convert("RGB")
    raw_w, raw_h = main.size

    # 横版布局无损照片放置：照片在左侧 100% 点对点全尺寸无损 (以基准 912 高度计算 scale)
    scale = raw_h / 912

    photo_box_w = raw_w
    photo_box_h = raw_h

    photo_x = round(84 * scale)
    photo_y = round(84 * scale)

    panel_x = photo_x + photo_box_w + round(52 * scale)
    panel_w = round(434 * scale)

    canvas_w = panel_x + panel_w + round(54 * scale)
    canvas_h = photo_y + photo_box_h + round(84 * scale)

    outer_pad = round(OUTER_PAD * scale)
    card_r = round(CARD_R * scale)
    canvas = new_card_canvas(canvas_w, canvas_h, bg, outer_pad=outer_pad, card_r=card_r)

    photo_box = (
        photo_x,
        photo_y,
        photo_x + photo_box_w,
        photo_y + photo_box_h,
    )
    paste_contained(
        canvas,
        main,
        photo_box,
        top_radius=round(28 * scale),
        rounded_corners={"tl", "tr", "bl", "br"},
        align_x="start",
        align_y="start",
    )

    draw = ImageDraw.Draw(canvas)
    ink = (30, 30, 30, 255)
    muted = (76, 76, 76, 255)
    panel_center_x = panel_x + round(panel_w / 2)

    draw_asset(canvas, camera_png, panel_center_x, round(300 * scale), round(320 * scale), round(224 * scale))
    y = round(438 * scale)
    y = draw_centered_wrapped_text(draw, panel_center_x, y, camera_model, ink, round(38 * scale), panel_w, True, max_lines=2, line_gap=round(8 * scale)) + round(14 * scale)
    for item in compact_param_lines(line_items[:6]):
        y = draw_centered_wrapped_text(draw, panel_center_x, y, item, muted, round(28 * scale), panel_w, False, max_lines=1, line_gap=round(6 * scale)) + round(8 * scale)

    draw_asset(canvas, lens_png, panel_center_x, round(756 * scale), round(312 * scale), round(220 * scale))
    lens_family, lens_params = split_lens_display_name(lens_model)
    y = draw_centered_wrapped_text(draw, panel_center_x, round(862 * scale), lens_family, ink, round(36 * scale), panel_w, True, max_lines=2, line_gap=round(6 * scale)) + round(16 * scale)
    draw_centered_rich_lens_params(draw, panel_center_x, y, lens_params, muted, round(28 * scale), panel_w, max_lines=2, line_gap=round(8 * scale))
    return canvas

