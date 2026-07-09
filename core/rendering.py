import colorsys
import re

import numpy as np
from PIL import Image, ImageDraw, ImageFilter

from .config import CANVAS_H, CANVAS_W, CARD_R, INFO_Y, LAYOUTS, OUTER_PAD, PHOTO_H, PHOTO_W, PHOTO_X, PHOTO_Y
from .fonts import font
from .metadata import (
    fmt_ev,
    fmt_f_number,
    fmt_focal,
    fmt_gps,
    fmt_model,
    lens_asset_keys,
    photo_year,
    run_exif,
    source_icc_profile,
    split_lens_display_name,
)
from .utils import unique_values


def rounded_rect_mask(size, radius, scale=4):
    scaled_size = (size[0] * scale, size[1] * scale)
    mask = Image.new("L", scaled_size, 0)
    ImageDraw.Draw(mask).rounded_rectangle(
        (0, 0, scaled_size[0], scaled_size[1]),
        radius=radius * scale,
        fill=255,
    )
    return mask.resize(size, Image.Resampling.LANCZOS)


def contain_fit(img, w, h):
    scale = min(w / img.width, h / img.height)
    nw, nh = round(img.width * scale), round(img.height * scale)
    return img.resize((nw, nh), Image.Resampling.LANCZOS)


def is_portrait_photo(path):
    with Image.open(path) as img:
        return img.width < img.height


def top_rounded_mask(size, radius):
    return selective_rounded_mask(size, radius, {"tl", "tr"})


def selective_rounded_mask(size, radius, corners, scale=4):
    scaled_size = (size[0] * scale, size[1] * scale)
    scaled_radius = radius * scale
    mask = Image.new("L", scaled_size, 0)
    draw = ImageDraw.Draw(mask)
    draw.rounded_rectangle((0, 0, scaled_size[0], scaled_size[1]), radius=scaled_radius, fill=255)
    if "tl" not in corners:
        draw.rectangle((0, 0, scaled_radius, scaled_radius), fill=255)
    if "tr" not in corners:
        draw.rectangle((scaled_size[0] - scaled_radius, 0, scaled_size[0], scaled_radius), fill=255)
    if "bl" not in corners:
        draw.rectangle((0, scaled_size[1] - scaled_radius, scaled_radius, scaled_size[1]), fill=255)
    if "br" not in corners:
        draw.rectangle(
            (scaled_size[0] - scaled_radius, scaled_size[1] - scaled_radius, scaled_size[0], scaled_size[1]),
            fill=255,
        )
    return mask.resize(size, Image.Resampling.LANCZOS)


def paste_contained(dst, src, box, top_radius=0, rounded_corners=None, align_x="center", align_y="center"):
    w = box[2] - box[0]
    h = box[3] - box[1]
    fitted = contain_fit(src, w, h)
    if align_x == "start":
        x = box[0]
    elif align_x == "end":
        x = box[2] - fitted.width
    else:
        x = box[0] + round((w - fitted.width) / 2)
    if align_y == "start":
        y = box[1]
    elif align_y == "end":
        y = box[3] - fitted.height
    else:
        y = box[1] + round((h - fitted.height) / 2)
    layer = fitted.convert("RGBA")
    if top_radius and rounded_corners:
        layer.putalpha(selective_rounded_mask(layer.size, top_radius, set(rounded_corners)))
    elif top_radius:
        layer.putalpha(top_rounded_mask(layer.size, top_radius))
    dst.alpha_composite(layer, (x, y))
    return (x, y, fitted.width, fitted.height)


def blend_rgb(a, b, t):
    return tuple(round(a[i] * (1 - t) + b[i] * t) for i in range(3))


def draw_top_gps(canvas, text, bg):
    if not text:
        return
    canvas_w, _ = canvas.size
    f = font(19, False)
    overlay = Image.new("RGBA", canvas.size, (0, 0, 0, 0))
    draw = ImageDraw.Draw(overlay)
    bbox = draw.textbbox((0, 0), text, font=f)
    text_w = bbox[2] - bbox[0]
    text_h = bbox[3] - bbox[1]
    pad_x = 15
    pill_h = 31
    pill_w = text_w + pad_x * 2
    pill_x = round((canvas_w - pill_w) / 2)
    pill_y = 19
    fill = (*blend_rgb(bg, (255, 255, 255), 0.34), 160)
    draw.rounded_rectangle(
        (pill_x, pill_y, pill_x + pill_w, pill_y + pill_h),
        radius=11,
        fill=fill,
        outline=(*blend_rgb(bg, (255, 255, 255), 0.55), 90),
        width=1,
    )
    tx = pill_x + pad_x - bbox[0]
    ty = pill_y + round((pill_h - text_h) / 2) - bbox[1] - 1
    draw.text((tx, ty), text, fill=(45, 45, 45, 118), font=f)
    canvas.alpha_composite(overlay)


def draw_copyright_overlay(canvas, text, bg):
    if not text:
        return
    canvas_w, canvas_h = canvas.size
    f = font(18, True)
    overlay = Image.new("RGBA", canvas.size, (0, 0, 0, 0))
    draw = ImageDraw.Draw(overlay)
    bbox = draw.textbbox((0, 0), text, font=f)
    text_w = bbox[2] - bbox[0]
    text_h = bbox[3] - bbox[1]
    pad_x = 18
    pill_h = 35
    pill_w = text_w + pad_x * 2
    pill_x = round((canvas_w - pill_w) / 2)
    pill_y = canvas_h - 45
    fill = (*blend_rgb(bg, (255, 255, 255), 0.34), 210)
    draw.rounded_rectangle(
        (pill_x, pill_y, pill_x + pill_w, pill_y + pill_h),
        radius=12,
        fill=fill,
        outline=(*blend_rgb(bg, (255, 255, 255), 0.55), 120),
        width=1,
    )
    tx = pill_x + pad_x - bbox[0]
    ty = pill_y + round((pill_h - text_h) / 2) - bbox[1] - 1
    draw.text((tx, ty), text, fill=(38, 38, 38, 150), font=f)
    canvas.alpha_composite(overlay)


def dominant_bg(path):
    img = Image.open(path).convert("RGB")
    img.thumbnail((220, 220), Image.Resampling.LANCZOS)
    arr = np.asarray(img).astype(np.float32)
    h, w, _ = arr.shape
    y0, y1 = int(h * 0.05), int(h * 0.95)
    x0, x1 = int(w * 0.05), int(w * 0.95)
    pixels = arr[y0:y1, x0:x1].reshape(-1, 3)
    if len(pixels) > 7000:
        pixels = pixels[np.linspace(0, len(pixels) - 1, 7000).astype(int)]

    centers = np.quantile(pixels, np.linspace(0.12, 0.88, 5), axis=0)
    labels = np.zeros(len(pixels), dtype=np.int64)
    for _ in range(12):
        dist = ((pixels[:, None, :] - centers[None, :, :]) ** 2).sum(axis=2)
        labels = dist.argmin(axis=1)
        centers = np.array([
            pixels[labels == i].mean(axis=0) if np.any(labels == i) else centers[i]
            for i in range(5)
        ])

    rgb = centers[np.bincount(labels, minlength=5).argmax()] / 255.0
    hue, light, sat = colorsys.rgb_to_hls(*rgb)
    light = min(max(light, 0.78), 0.9)
    sat = min(sat * 0.32, 0.16)
    return tuple(int(round(c * 255)) for c in colorsys.hls_to_rgb(hue, light, sat))


def draw_text(draw, xy, s, fill, size, medium=False):
    if not s:
        return (0, 0, 0, 0)
    f = font(size, medium)
    draw.text(xy, str(s), fill=fill, font=f)
    return draw.textbbox(xy, str(s), font=f)


def wrap_text(draw, text, font_obj, max_width):
    text = str(text)
    if not text:
        return []

    tokens = text.split(" ")
    if len(tokens) > 1:
        lines = []
        line = ""
        for token in tokens:
            candidate = token if not line else f"{line} {token}"
            if draw.textlength(candidate, font=font_obj) <= max_width:
                line = candidate
            else:
                if line:
                    lines.append(line)
                if draw.textlength(token, font=font_obj) <= max_width:
                    line = token
                else:
                    lines.extend(wrap_text(draw, token, font_obj, max_width))
                    line = ""
        if line:
            lines.append(line)
        return lines

    lines = []
    line = ""
    for ch in text:
        candidate = line + ch
        if draw.textlength(candidate, font=font_obj) <= max_width:
            line = candidate
        else:
            if line:
                lines.append(line)
            line = ch
    if line:
        lines.append(line)
    return lines


def draw_wrapped_text(draw, xy, s, fill, size, max_width, medium=False, max_lines=None, line_gap=8):
    if not s:
        return xy[1]
    f = font(size, medium)
    lines = wrap_text(draw, s, f, max_width)
    if max_lines and len(lines) > max_lines:
        lines = lines[:max_lines]
        ellipsis = "..."
        while lines[-1] and draw.textlength(lines[-1] + ellipsis, font=f) > max_width:
            lines[-1] = lines[-1][:-1]
        lines[-1] = lines[-1] + ellipsis

    x, y = xy
    for line in lines:
        draw.text((x, y), line, fill=fill, font=f)
        box = draw.textbbox((x, y), line, font=f)
        y = box[3] + line_gap
    return y


def draw_centered_wrapped_text(draw, center_x, y, s, fill, size, max_width, medium=False, max_lines=None, line_gap=8):
    if not s:
        return y
    f = font(size, medium)
    lines = wrap_text(draw, s, f, max_width)
    if max_lines and len(lines) > max_lines:
        lines = lines[:max_lines]
        ellipsis = "..."
        while lines[-1] and draw.textlength(lines[-1] + ellipsis, font=f) > max_width:
            lines[-1] = lines[-1][:-1]
        lines[-1] = lines[-1] + ellipsis

    for line in lines:
        bbox = draw.textbbox((0, 0), line, font=f)
        line_w = bbox[2] - bbox[0]
        x = round(center_x - line_w / 2) - bbox[0]
        draw.text((x, y), line, fill=fill, font=f)
        box = draw.textbbox((x, y), line, font=f)
        y = box[3] + line_gap
    return y


def draw_rich_lens_params(draw, xy, s, fill, size, max_width, max_lines=2, line_gap=8):
    if not s:
        return xy[1]

    regular = font(size, False)
    bold = font(size, True)
    lines = wrap_text(draw, s, regular, max_width)
    if max_lines and len(lines) > max_lines:
        lines = lines[:max_lines]
        ellipsis = "..."
        while lines[-1] and draw.textlength(lines[-1] + ellipsis, font=regular) > max_width:
            lines[-1] = lines[-1][:-1]
        lines[-1] = lines[-1] + ellipsis

    x, y = xy
    for line in lines:
        cursor_x = x
        max_bottom = y
        for part in re.split(r"(\bS\b)", line):
            if not part:
                continue
            part_font = bold if part == "S" else regular
            draw.text((cursor_x, y), part, fill=fill, font=part_font)
            box = draw.textbbox((cursor_x, y), part, font=part_font)
            cursor_x = box[2]
            max_bottom = max(max_bottom, box[3])
        y = max_bottom + line_gap
    return y


def draw_centered_rich_lens_params(draw, center_x, y, s, fill, size, max_width, max_lines=2, line_gap=8):
    if not s:
        return y

    regular = font(size, False)
    bold = font(size, True)
    lines = wrap_text(draw, s, regular, max_width)
    if max_lines and len(lines) > max_lines:
        lines = lines[:max_lines]
        ellipsis = "..."
        while lines[-1] and draw.textlength(lines[-1] + ellipsis, font=regular) > max_width:
            lines[-1] = lines[-1][:-1]
        lines[-1] = lines[-1] + ellipsis

    for line in lines:
        parts = [part for part in re.split(r"(\bS\b)", line) if part]
        line_w = sum(draw.textlength(part, font=(bold if part == "S" else regular)) for part in parts)
        cursor_x = round(center_x - line_w / 2)
        max_bottom = y
        for part in parts:
            part_font = bold if part == "S" else regular
            draw.text((cursor_x, y), part, fill=fill, font=part_font)
            box = draw.textbbox((cursor_x, y), part, font=part_font)
            cursor_x = box[2]
            max_bottom = max(max_bottom, box[3])
        y = max_bottom + line_gap
    return y


def compact_param_lines(items):
    if len(items) <= 4:
        return items

    # Keep the camera area fixed: pair short exposure settings instead of
    # letting extra rows push into the lens area.
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


def new_card_canvas(width, height, bg, outer_pad=OUTER_PAD, card_r=CARD_R):
    canvas = Image.new("RGBA", (width, height), (232, 232, 228, 255))
    shadow = Image.new("RGBA", (width, height), (0, 0, 0, 0))
    sd = ImageDraw.Draw(shadow)
    sd.rounded_rectangle(
        (outer_pad, outer_pad + 10, width - outer_pad, height - outer_pad + 10),
        radius=card_r,
        fill=(0, 0, 0, 34),
    )
    canvas.alpha_composite(shadow.filter(ImageFilter.GaussianBlur(18)))

    card = Image.new("RGBA", (width - outer_pad * 2, height - outer_pad * 2), (*bg, 255))
    canvas.paste(card, (outer_pad, outer_pad), rounded_rect_mask(card.size, card_r))
    return canvas


def draw_portrait_card(photo_path, exif, bg, camera_png, lens_png, camera_model, lens_model, line_items):
    canvas = new_card_canvas(CANVAS_W, CANVAS_H, bg)
    main = Image.open(photo_path).convert("RGB")
    paste_contained(
        canvas,
        main,
        (PHOTO_X, PHOTO_Y, PHOTO_X + PHOTO_W, PHOTO_Y + PHOTO_H),
        top_radius=24,
    )

    draw = ImageDraw.Draw(canvas)
    ink = (30, 30, 30, 255)
    muted = (76, 76, 76, 255)

    left_x = 126
    right_x = 584
    text_w = CANVAS_W - OUTER_PAD - right_x - 64
    camera_area_y = INFO_Y + 20
    lens_area_y = INFO_Y + 320
    cam_y = camera_area_y + 128
    lens_y = lens_area_y + 132
    draw_asset(canvas, camera_png, left_x + 126, cam_y, 330, 238)
    draw_asset(canvas, lens_png, left_x + 126, lens_y, 314, 232)
    y = camera_area_y + 48
    y = draw_wrapped_text(draw, (right_x, y), camera_model, ink, 40, text_w, True, max_lines=2, line_gap=8) + 14
    for item in compact_param_lines(line_items[:6]):
        y = draw_wrapped_text(draw, (right_x, y), item, muted, 30, text_w, False, max_lines=1, line_gap=6) + 8

    lens_family, lens_params = split_lens_display_name(lens_model)
    y = draw_wrapped_text(draw, (right_x, lens_area_y + 82), lens_family, ink, 40, text_w, True, max_lines=2, line_gap=6) + 16
    draw_rich_lens_params(draw, (right_x, y), lens_params, muted, 30, text_w, max_lines=2, line_gap=8)
    return canvas


def draw_landscape_card(photo_path, exif, bg, camera_png, lens_png, camera_model, lens_model, line_items):
    canvas_w = 1440
    canvas_h = 1080
    canvas = new_card_canvas(canvas_w, canvas_h, bg)

    main = Image.open(photo_path).convert("RGB")
    paste_contained(
        canvas,
        main,
        (84, 84, 900, 996),
        top_radius=28,
        rounded_corners={"tl", "tr", "bl", "br"},
        align_x="start",
        align_y="start",
    )

    draw = ImageDraw.Draw(canvas)
    ink = (30, 30, 30, 255)
    muted = (76, 76, 76, 255)
    panel_x = 952
    panel_w = canvas_w - OUTER_PAD - panel_x - 54
    panel_center_x = panel_x + round(panel_w / 2)

    draw_asset(canvas, camera_png, panel_center_x, 300, 320, 224)
    y = 438
    y = draw_centered_wrapped_text(draw, panel_center_x, y, camera_model, ink, 38, panel_w, True, max_lines=2, line_gap=8) + 14
    for item in compact_param_lines(line_items[:6]):
        y = draw_centered_wrapped_text(draw, panel_center_x, y, item, muted, 28, panel_w, False, max_lines=1, line_gap=6) + 8

    draw_asset(canvas, lens_png, panel_center_x, 756, 312, 220)
    lens_family, lens_params = split_lens_display_name(lens_model)
    y = draw_centered_wrapped_text(draw, panel_center_x, 862, lens_family, ink, 36, panel_w, True, max_lines=2, line_gap=6) + 14
    draw_centered_rich_lens_params(draw, panel_center_x, y, lens_params, muted, 28, panel_w, max_lines=2, line_gap=8)
    return canvas


def make_card(photo_path, result_dir, gear_assets, layout="portrait"):
    if layout not in LAYOUTS:
        raise ValueError(f"Unsupported layout: {layout}")
    effective_layout = layout if is_portrait_photo(photo_path) else "portrait"

    exif = run_exif(photo_path)
    bg = dominant_bg(photo_path)
    icc_profile = source_icc_profile(photo_path, exif)

    camera_model = fmt_model(exif)
    camera_keys = unique_values([
        exif.get("CameraModelName"),
        exif.get("Model"),
        camera_model,
    ])
    camera_png = next((gear_assets["cameras"][key] for key in camera_keys if key in gear_assets["cameras"]), None)
    if not camera_png:
        print(f"Warning: no camera PNG match for {photo_path.name}: {camera_model or 'unknown camera'}; using default")
        camera_png = gear_assets["default_camera"]

    lens_model = (exif.get("LensModel") or exif.get("LensID") or exif.get("Lens") or "").strip()
    lens_keys = lens_asset_keys(lens_model)
    lens_png = next((gear_assets["lenses"][key] for key in lens_keys if key in gear_assets["lenses"]), None)
    if not lens_png:
        print(f"Warning: no lens PNG match for {photo_path.name}: {lens_model}; using default")
        lens_png = gear_assets["default_lens"]

    line_items = [
        exif.get("Format") if exif.get("Format") and str(exif.get("Format")).lower() != "image/jpeg" else None,
        fmt_f_number(exif.get("FNumber") or exif.get("Aperture")),
        exif.get("ExposureTime") or exif.get("ShutterSpeed"),
        f"ISO {exif.get('ISO')}" if exif.get("ISO") else None,
        fmt_focal(exif.get("FocalLength")),
        fmt_ev(exif.get("ExposureCompensation")),
        exif.get("WhiteBalance"),
    ]
    line_items = [x for x in line_items if x]

    if effective_layout == "landscape":
        canvas = draw_landscape_card(photo_path, exif, bg, camera_png, lens_png, camera_model, lens_model, line_items)
    else:
        canvas = draw_portrait_card(photo_path, exif, bg, camera_png, lens_png, camera_model, lens_model, line_items)

    draw_top_gps(canvas, fmt_gps(exif), bg)
    draw_copyright_overlay(
        canvas,
        f"\N{COPYRIGHT SIGN} {photo_year(exif)} Vincent Chyu PHOTOGRAPHY - All rights reserved",
        bg,
    )

    out = result_dir / f"{photo_path.stem}_card.png"
    save_kwargs = {"quality": 95}
    if icc_profile:
        save_kwargs["icc_profile"] = icc_profile
    canvas.convert("RGB").save(out, **save_kwargs)
    return out


def make_contact_sheet(outputs, result_dir, columns=5):
    if not outputs:
        return None

    thumb_w = 216
    thumb_h = 288
    cell_w = 236
    cell_h = 326
    label_h = 30
    rows = (len(outputs) + columns - 1) // columns

    sheet = Image.new("RGB", (cell_w * columns, cell_h * rows), (240, 240, 240))
    label_font = font(14)
    for idx, path in enumerate(outputs):
        im = Image.open(path).convert("RGB")
        im.thumbnail((thumb_w, thumb_h), Image.Resampling.LANCZOS)
        cell = Image.new("RGB", (cell_w, cell_h), (246, 246, 246))
        cell.paste(im, ((cell_w - im.width) // 2, 8))

        draw = ImageDraw.Draw(cell)
        name = path.name
        while name and draw.textlength(name, font=label_font) > cell_w - 16:
            name = name[:-1]
        if name != path.name:
            name = name[:-3] + "..."
        draw.text((8, cell_h - label_h + 5), name, fill=(30, 30, 30), font=label_font)

        x = (idx % columns) * cell_w
        y = (idx // columns) * cell_h
        sheet.paste(cell, (x, y))

    out = result_dir / "contact-sheet.jpg"
    icc_profile = None
    with Image.open(outputs[0]) as first:
        icc_profile = first.info.get("icc_profile")
    save_kwargs = {"quality": 92}
    if icc_profile:
        save_kwargs["icc_profile"] = icc_profile
    sheet.save(out, **save_kwargs)
    return out

