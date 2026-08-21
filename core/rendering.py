import colorsys
from pathlib import Path
import numpy as np
from PIL import Image, ImageDraw, ImageFilter, ImageFile

ImageFile.LOAD_TRUNCATED_IMAGES = True


def dominant_bg(path):
    """公共核心函数：根据图像像素分布主色提取软卡片背景色。"""
    with Image.open(path) as img:
        img.draft("RGB", (220, 220))
        img = img.convert("RGB")
        img.thumbnail((220, 220), Image.Resampling.BOX)
        arr = np.asarray(img).astype(np.float32)
        h, w, _ = arr.shape
        pixels = arr[int(h * 0.05):int(h * 0.95), int(w * 0.05):int(w * 0.95)].reshape(-1, 3)
        if len(pixels) == 0:
            pixels = arr.reshape(-1, 3)
        if len(pixels) == 0:
            return (240, 240, 240)
        if len(pixels) > 2000:
            pixels = pixels[np.linspace(0, len(pixels) - 1, 2000).astype(int)]

        centers = np.quantile(pixels, np.linspace(0.12, 0.88, 5), axis=0)
        labels = np.zeros(len(pixels), dtype=np.int64)
        for _ in range(8):
            dist = ((pixels[:, None, :] - centers[None, :, :]) ** 2).sum(axis=2)
            labels = dist.argmin(axis=1)
            centers = np.array([
                pixels[labels == i].mean(axis=0) if np.any(labels == i) else centers[i]
                for i in range(5)
            ])

        raw_rgb = centers[np.bincount(labels, minlength=5).argmax()] / 255.0
        rgb = np.clip(raw_rgb, 0.0, 1.0)
        hue, light, sat = colorsys.rgb_to_hls(float(rgb[0]), float(rgb[1]), float(rgb[2]))
        light = min(max(light, 0.78), 0.9)
        sat = min(sat * 0.32, 0.16)
        return tuple(int(round(c * 255)) for c in colorsys.hls_to_rgb(hue, light, sat))


from .config import CARD_R, OUTER_PAD
from .context import RendererContext
from .fonts import font
from .metadata import source_icc_profile
from .renderer import load_renderer


RenderContext = RendererContext


def rounded_rect_mask(size, radius, scale=None):
    return selective_rounded_mask(size, radius, {"tl", "tr", "bl", "br"}, scale=scale)



def contain_fit(img, w, h):
    scale = min(w / img.width, h / img.height)
    nw, nh = round(img.width * scale), round(img.height * scale)
    return img.resize((nw, nh), Image.Resampling.LANCZOS)


def blend_rgb(a, b, t):
    """将两个 RGB 元组按比例 t 线性插值（LERP）。t=0 返回 a，t=1 返回 b。"""
    return tuple(round(a[i] * (1 - t) + b[i] * t) for i in range(3))


def resize_by_width(image, width):
    """等比例缩放图像到指定宽度。"""
    old_width, height = image.size
    new_height = round(height * width / old_width)
    return image.resize((width, new_height), Image.Resampling.LANCZOS)


def resize_by_height(image, height):
    """等比例缩放图像到指定高度。"""
    width, old_height = image.size
    new_width = round(width * height / old_height)
    return image.resize((new_width, height), Image.Resampling.LANCZOS)


def pad_image(image, padding_size, sides="tb", color=(0, 0, 0, 0)):
    """在图像的指定边（t/b/l/r 任意组合）添加空白 padding。

    Args:
        image: PIL Image 对象。
        padding_size: 各边添加的像素大小。
        sides: 字符串，包含要添加 padding 的边：'t'（上）、'b'（下）、'l'（左）、'r'（右）。
        color: 填充颜色，默认透明。
    """
    total_width, total_height = image.size
    x_offset, y_offset = 0, 0
    if "t" in sides:
        total_height += padding_size
        y_offset += padding_size
    if "b" in sides:
        total_height += padding_size
    if "l" in sides:
        total_width += padding_size
        x_offset += padding_size
    if "r" in sides:
        total_width += padding_size
    output = Image.new(image.mode, (total_width, total_height), color)
    output.paste(image, (x_offset, y_offset))
    return output


def create_text_image(content, font_obj, fill="black", transparent_color=(0, 0, 0, 0)):
    """公共核心函数：将文本内容渲染为透明背景的 Image 对象。"""
    if not content:
        content = "   "
    _, _, text_width, text_height = font_obj.getbbox(content)
    image = Image.new("RGBA", (max(1, text_width), max(1, text_height)), color=transparent_color)
    ImageDraw.Draw(image).text((0, 0), content, fill=fill, font=font_obj)
    return image


def concatenate_images(images, align="left", transparent_color=(0, 0, 0, 0)):
    """公共核心函数：纵向拼接多个 Image 图像块，支持 left / center / right 对齐。"""
    if not images:
        return Image.new("RGBA", (1, 1), transparent_color)
    widths, heights = zip(*(image.size for image in images))
    output = Image.new("RGBA", (max(widths), sum(heights)), color=transparent_color)
    y_offset = 0
    for image in images:
        x_offset = 0
        if align == "center":
            x_offset = int((output.width - image.width) / 2)
        elif align == "right":
            x_offset = output.width - image.width
        output.paste(image, (x_offset, y_offset))
        y_offset += image.height
    return output


def arrange_images_side(background, images, side="left", padding=200, is_start=False):
    """公共核心函数：沿左右侧排列并按背景高度自动比例缩放粘贴 Image 列表。"""
    if side == "right":
        x_offset = background.width - padding if is_start else background.width
        for image in reversed(images):
            if image is None:
                continue
            fitted = resize_by_height(image, background.height)
            x_offset -= fitted.width
            x_offset -= padding
            background.paste(fitted, (x_offset, 0))
    else:
        x_offset = padding if is_start else 0
        for image in images:
            if image is None:
                continue
            fitted = resize_by_height(image, background.height)
            background.paste(fitted, (x_offset, 0))
            x_offset += fitted.width + padding


def is_portrait_photo(path):
    with Image.open(path) as img:
        return img.width < img.height


def top_rounded_mask(size, radius):
    return selective_rounded_mask(size, radius, {"tl", "tr"})


def selective_rounded_mask(size, radius, corners, scale=None):
    if scale is None:
        min_dim = min(size)
        if min_dim >= 2000:
            scale = 1
        elif min_dim >= 1000:
            scale = 2
        else:
            scale = 4

    if scale == 1:
        mask = Image.new("L", size, 0)
        draw = ImageDraw.Draw(mask)
        draw.rounded_rectangle((0, 0, size[0], size[1]), radius=radius, fill=255)
        if "tl" not in corners:
            draw.rectangle((0, 0, radius, radius), fill=255)
        if "tr" not in corners:
            draw.rectangle((size[0] - radius, 0, size[0], radius), fill=255)
        if "bl" not in corners:
            draw.rectangle((0, size[1] - radius, radius, size[1]), fill=255)
        if "br" not in corners:
            draw.rectangle((size[0] - radius, size[1] - radius, size[0], size[1]), fill=255)
        return mask

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
    resample_filter = Image.Resampling.BOX if scale == 2 else Image.Resampling.LANCZOS
    return mask.resize(size, resample_filter)



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


def get_renderer(presentation):
    return load_renderer(presentation.renderer)


def calculate_card_scale(photo_size, base_frame_size):
    """公共核心函数：根据照片原始尺寸与基准框架尺寸，计算原图无损渲染所需的放缩比例 scale。"""
    raw_w, raw_h = photo_size
    frame_w, frame_h = base_frame_size
    fit_scale = min(frame_w / raw_w, frame_h / raw_h)
    if fit_scale < 1.0:
        return 1.0 / fit_scale
    return 1.0


def apply_card_compression(canvas, output_policy, target_base=1080):
    """公共核心函数：在输出前的最后环节，统一对渲染完成的卡片做尺寸压缩。"""
    if output_policy and output_policy.compression == "jpeg":
        if canvas.width >= canvas.height:
            return resize_by_height(canvas, target_base) if canvas.height > target_base else canvas
        else:
            return resize_by_width(canvas, target_base) if canvas.width > target_base else canvas
    return canvas


def make_card(
    photo_path,
    result_dir,
    renderer,
    presentation,
    layout=None,
    output_policy=None,
    asset_dir=None,
    exif=None,
    debug=False,
    step_callback=None,
):
    from .output import OutputPolicy

    photo_path = Path(photo_path)
    result_dir = Path(result_dir)
    output_policy = output_policy or OutputPolicy()
    layout = str(layout or presentation.default_layout).strip().lower()
    if layout not in presentation.layouts:
        raise ValueError(f"Layout {layout!r} is not supported by {presentation.scheme_id}")
    if presentation.scheme_id == "scheme1":
        effective_layout = layout if is_portrait_photo(photo_path) else presentation.default_layout
    else:
        effective_layout = layout

    debug_dir = None
    if debug:
        debug_dir = result_dir / f"{photo_path.stem}_debug"
        debug_dir.mkdir(parents=True, exist_ok=True)

    context = renderer.prepare_context(
        photo_path,
        asset_dir or result_dir.parent,
        presentation,
        layout,
        compression=output_policy.compression,
        exif=exif,
        step_callback=step_callback,
    )

    context = RenderContext(
        **{
            **context.__dict__,
            "effective_layout": effective_layout,
            "compression": output_policy.compression,
            "debug": debug,
            "debug_dir": debug_dir,
        }
    )
    canvas = renderer.apply_overlays(renderer.render(context), context)
    canvas = apply_card_compression(canvas, output_policy)
    icc_profile = source_icc_profile(photo_path, context.exif)
    out = result_dir / f"{photo_path.stem}_card{output_policy.suffix}"
    output_policy.save_card(canvas, out, icc_profile)

    if debug and debug_dir:
        # 保存一份到 debug 目录作为阶段 5 最终产物 (05_02_final_card.jpg)
        final_debug_out = debug_dir / f"05_02_final_card{output_policy.suffix}"
        output_policy.save_card(canvas, final_debug_out, icc_profile)

    return out



def make_contact_sheet(outputs, result_dir, output_policy=None, columns=5):
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
        with Image.open(path) as im_src:
            im = im_src.convert("RGB")
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
    from .output import OutputPolicy

    (output_policy or OutputPolicy()).save_contact_sheet(sheet, out, icc_profile)
    return out
