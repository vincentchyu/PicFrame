"""
core.drawing — 文本折行与绘制公共工具

提供与具体方案（Scheme）无关的 Pillow 文本量算、折行、逐行绘制等通用原语。
新增方案直接 from core.drawing import ... 即可使用，无需重复实现。
"""

import re

from .fonts import font


def wrap_text(draw, text, font_obj, max_width):
    """将文本按最大宽度折行，返回字符串列表。

    优先按空格拆分单词；若单个单词仍超宽则按字符拆分。
    """
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
    """在 xy 位置逐行绘制折行文本，返回下一行的 Y 坐标。

    Args:
        draw: ImageDraw 实例。
        xy: 起始坐标 (x, y)。
        s: 待绘制字符串。
        fill: 字体颜色。
        size: 字号。
        max_width: 最大文本宽度（像素）。
        medium: 是否使用 Medium 字重。
        max_lines: 最大行数，超出则截断并追加省略号。
        line_gap: 行间距（像素）。
    """
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
    """居中版 draw_wrapped_text，返回下一行 Y 坐标。"""
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
    """绘制镜头参数文本，独立的 'S'（尼康 S-Line）使用 Medium 字重加强。

    返回下一行 Y 坐标。
    """
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
    """居中版 draw_rich_lens_params，返回下一行 Y 坐标。"""
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
