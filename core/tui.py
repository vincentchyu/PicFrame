import curses
from pathlib import Path

from .batch import generate_from_source
from .presentation import get_presentation_scheme, load_presentation_schemes


def screen_add(stdscr, y, x, text, attr=0):
    height, width = stdscr.getmaxyx()
    if y < 0 or y >= height or x >= width:
        return
    safe_text = str(text)
    stdscr.addnstr(y, x, safe_text, max(0, width - x - 1), attr)


def read_path_prompt(stdscr, initial_path):
    curses.echo()
    curses.curs_set(1)
    stdscr.clear()
    screen_add(stdscr, 0, 0, "请输入源文件夹路径，然后按回车键:")
    screen_add(stdscr, 2, 0, str(initial_path))
    screen_add(stdscr, 4, 0, "> ")
    stdscr.refresh()
    raw = stdscr.getstr(4, 2).decode("utf-8", errors="replace").strip()
    curses.noecho()
    curses.curs_set(0)
    return Path(raw).expanduser() if raw else initial_path


def choose_source_dir(stdscr, start_dir):
    current = Path(start_dir).expanduser().resolve()
    selected = 0
    offset = 0

    while True:
        dirs = [p for p in current.iterdir() if p.is_dir() and not p.name.startswith(".")]
        dirs.sort(key=lambda p: p.name.lower())
        entries = [("..", current.parent), (". 选择此文件夹", current)] + [(p.name, p) for p in dirs]

        height, width = stdscr.getmaxyx()
        list_top = 4
        list_height = max(1, height - list_top - 2)
        selected = max(0, min(selected, len(entries) - 1))
        if selected < offset:
            offset = selected
        if selected >= offset + list_height:
            offset = selected - list_height + 1

        stdscr.clear()
        screen_add(stdscr, 0, 0, "PicFrame 源文件夹")
        screen_add(stdscr, 1, 0, str(current))
        screen_add(stdscr, 2, 0, "Enter：打开/选择 | Space：选择当前 | g: 输入路径 | q: 退出")

        for row, (label, path) in enumerate(entries[offset:offset + list_height], start=list_top):
            marker = "> " if offset + row - list_top == selected else "  "
            suffix = "/" if path.is_dir() else ""
            attr = curses.A_REVERSE if offset + row - list_top == selected else 0
            screen_add(stdscr, row, 0, f"{marker}{label}{suffix}", attr)

        stdscr.refresh()
        key = stdscr.getch()
        if key in (ord("q"), 27):
            return None
        if key in (curses.KEY_UP, ord("k")):
            selected -= 1
        elif key in (curses.KEY_DOWN, ord("j")):
            selected += 1
        elif key == curses.KEY_NPAGE:
            selected += list_height
        elif key == curses.KEY_PPAGE:
            selected -= list_height
        elif key == ord(" "):
            return current
        elif key == ord("g"):
            typed = read_path_prompt(stdscr, current)
            if typed.exists() and typed.is_dir():
                current = typed.resolve()
                selected = 0
                offset = 0
        elif key in (curses.KEY_ENTER, 10, 13):
            label, path = entries[selected]
            if label == ". choose this folder":
                return current
            current = path.resolve()
            selected = 0
            offset = 0


SCHEME_PREVIEWS = {
    "scheme1": (
        "┌─────────────────┐",
        "│     [ GPS ]     │",
        "│ ┌─────────────┐ │",
        "│ │             │ │",
        "│ │    PHOTO    │ │",
        "│ │             │ │",
        "│ └─────────────┘ │",
        "│ [📷] Camera     │",
        "│ [🔍] Lens       │",
        "│  © Copyright    │",
        "└─────────────────┘",
        "小红书 3:4 / 4:3 极简信息卡",
        "照片软背景，固定相机/镜头与曝光区域",
    ),
    "scheme2": (
        "┌───────────────────────┐",
        "│                       │",
        "│        PHOTO          │",
        "│                       │",
        "├───────────────────────┤",
        "│ 35mm f/1.8 | NIKON   │",
        "└───────────────────────┘",
        "右侧 Logo 水印带方案",
        "保持照片原始比例，底部拼接品牌Logo与水印",
    ),
}

LAYOUT_PREVIEWS = {
    "portrait": (
        "┌─────────────────┐",
        "│     [ GPS ]     │",
        "│ ┌─────────────┐ │",
        "│ │             │ │",
        "│ │    PHOTO    │ │",
        "│ │             │ │",
        "│ └─────────────┘ │",
        "│ [📷] Camera     │",
        "│ [🔍] Lens       │",
        "│  © Copyright    │",
        "└─────────────────┘",
        "竖版 3:4 信息卡布局",
        "主图在上方固定框架，下方为器材参数",
    ),
    "landscape": (
        "┌───────────────────────┐",
        "│ [  GPS  ]             │",
        "│ ┌───────────┐  [📷]   │",
        "│ │           │  Camera │",
        "│ │   PHOTO   │  [🔍]   │",
        "│ │           │  Lens   │",
        "│ └───────────┘         │",
        "│      © Copyright      │",
        "└───────────────────────┘",
        "横版 4:3 左图卡布局",
        "适用于竖图源，主图在左侧，右侧陈列器材",
    ),
    "watermark_right_logo": (
        "┌───────────────────────┐",
        "│                       │",
        "│        PHOTO          │",
        "│                       │",
        "├───────────────────────┤",
        "│ 35mm f/1.8 | NIKON   │",
        "└───────────────────────┘",
        "底部 Logo 水印带布局",
        "原图比例展示，底部附加曝光参数与品牌标识",
    ),
}


def choose_scheme(stdscr):
    options = list(load_presentation_schemes().values())
    selected = 0
    while True:
        stdscr.clear()
        height, width = stdscr.getmaxyx()
        screen_add(stdscr, 0, 0, "PicFrame 展示方案")
        screen_add(stdscr, 2, 0, "请选择展示方案:")
        screen_add(stdscr, 3, 0, "Enter: 选择   q/Esc: 返回")
        for idx, scheme in enumerate(options, start=5):
            attr = curses.A_REVERSE if idx - 5 == selected else 0
            marker = "> " if idx - 5 == selected else "  "
            screen_add(stdscr, idx, 0, f"{marker}{scheme.scheme_id:<9} {scheme.name}", attr)

        current_scheme = options[selected]
        preview_data = SCHEME_PREVIEWS.get(current_scheme.scheme_id)
        if preview_data and width >= 70:
            px = max(38, min(width - 38, 44))
            screen_add(stdscr, 4, px, "┌── 布局线框预览 ─────────────────┐", curses.A_DIM)
            lines = preview_data[:-2]
            desc1, desc2 = preview_data[-2], preview_data[-1]
            for r_idx, line in enumerate(lines, start=5):
                screen_add(stdscr, r_idx, px + 2, line)
            desc_y = 5 + len(lines) + 1
            screen_add(stdscr, desc_y, px + 2, desc1, curses.A_BOLD)
            screen_add(stdscr, desc_y + 1, px + 2, desc2, curses.A_DIM)
            screen_add(stdscr, desc_y + 3, px, "└─────────────────────────────────┘", curses.A_DIM)

        stdscr.refresh()
        key = stdscr.getch()
        if key in (ord("q"), 27):
            return None
        if key in (curses.KEY_UP, ord("k")):
            selected = max(0, selected - 1)
        elif key in (curses.KEY_DOWN, ord("j")):
            selected = min(len(options) - 1, selected + 1)
        elif key in (curses.KEY_ENTER, 10, 13):
            return options[selected].scheme_id


def choose_layout(stdscr, scheme_id):
    scheme = get_presentation_scheme(scheme_id)
    options = list(scheme.layouts)
    selected = options.index(scheme.default_layout)
    descriptions = {
        "portrait": "照片源保持 3:4 的比例。",
        "landscape": "照片源使用 4:3 左图卡。",
        "watermark_right_logo": "底部品牌 Logo 水印带。",
    }
    while True:
        stdscr.clear()
        height, width = stdscr.getmaxyx()
        screen_add(stdscr, 0, 0, f"PicFrame 布局 - {scheme.name}")
        screen_add(stdscr, 2, 0, "请选择渲染布局方案:")
        screen_add(stdscr, 3, 0, "Enter: 选择   q/Esc: 返回")
        for idx, layout in enumerate(options, start=5):
            attr = curses.A_REVERSE if idx - 5 == selected else 0
            marker = "> " if idx - 5 == selected else "  "
            screen_add(stdscr, idx, 0, f"{marker}{layout:<21} {descriptions.get(layout, '')}", attr)

        current_layout = options[selected]
        preview_data = LAYOUT_PREVIEWS.get(current_layout)
        if preview_data and width >= 70:
            px = max(42, min(width - 38, 48))
            screen_add(stdscr, 4, px, "┌── 布局线框预览 ─────────────────┐", curses.A_DIM)
            lines = preview_data[:-2]
            desc1, desc2 = preview_data[-2], preview_data[-1]
            for r_idx, line in enumerate(lines, start=5):
                screen_add(stdscr, r_idx, px + 2, line)
            desc_y = 5 + len(lines) + 1
            screen_add(stdscr, desc_y, px + 2, desc1, curses.A_BOLD)
            screen_add(stdscr, desc_y + 1, px + 2, desc2, curses.A_DIM)
            screen_add(stdscr, desc_y + 3, px, "└─────────────────────────────────┘", curses.A_DIM)

        stdscr.refresh()
        key = stdscr.getch()
        if key in (ord("q"), 27):
            return None
        if key in (curses.KEY_UP, ord("k")):
            selected = max(0, selected - 1)
        elif key in (curses.KEY_DOWN, ord("j")):
            selected = min(len(options) - 1, selected + 1)
        elif key in (curses.KEY_ENTER, 10, 13):
            return options[selected]


def choose_compression(stdscr):
    options = [("none", "不压缩（PNG）"), ("jpeg", "压缩（JPEG）")]
    selected = 0
    while True:
        stdscr.clear()
        screen_add(stdscr, 0, 0, "PicFrame 输出压缩")
        screen_add(stdscr, 2, 0, "请选择卡片输出格式:")
        screen_add(stdscr, 3, 0, "Enter: 选择   q/Esc: 返回")
        for idx, (_, label) in enumerate(options, start=5):
            active = idx - 5 == selected
            screen_add(stdscr, idx, 0, f"{' >' if active else '  '} {label}", curses.A_REVERSE if active else 0)
        stdscr.refresh()
        key = stdscr.getch()
        if key in (ord("q"), 27):
            return None
        if key in (curses.KEY_UP, ord("k")):
            selected = max(0, selected - 1)
        elif key in (curses.KEY_DOWN, ord("j")):
            selected = min(len(options) - 1, selected + 1)
        elif key in (curses.KEY_ENTER, 10, 13):
            return options[selected][0]


def tui_status_callback(stdscr):
    def callback(stage, index, total, photo, result_dir):
        stdscr.clear()
        screen_add(stdscr, 0, 0, "PicFrame generating")
        screen_add(stdscr, 1, 0, f"Output: {result_dir}")
        if stage == "processing" and photo:
            screen_add(stdscr, 3, 0, f"[{index}/{total}] {photo.name}")
        elif stage == "generated" and photo:
            screen_add(stdscr, 3, 0, f"[{index}/{total}] generated {photo.stem}_card.png")
        elif stage == "contact_sheet":
            screen_add(stdscr, 3, 0, "Building contact-sheet.jpg")
        elif stage == "done":
            screen_add(stdscr, 3, 0, f"Done. Generated {total} cards.")
        stdscr.refresh()
    return callback


def run_tui(stdscr):
    curses.curs_set(0)
    source_dir = choose_source_dir(stdscr, Path.cwd())
    if source_dir is None:
        return 0
    scheme = choose_scheme(stdscr)
    if scheme is None:
        return 0
    layout = choose_layout(stdscr, scheme)
    if layout is None:
        return 0
    compression = choose_compression(stdscr)
    if compression is None:
        return 0

    try:
        result = generate_from_source(
            source_dir,
            progress_callback=tui_status_callback(stdscr),
            layout=layout,
            scheme=scheme,
            compression=compression,
        )
    except Exception as exc:
        stdscr.clear()
        screen_add(stdscr, 0, 0, "PicFrame failed")
        screen_add(stdscr, 2, 0, str(exc))
        screen_add(stdscr, 4, 0, "Press any key to exit.")
        stdscr.refresh()
        stdscr.getch()
        return 1

    stdscr.clear()
    screen_add(stdscr, 0, 0, "PicFrame complete")
    screen_add(stdscr, 2, 0, f"Source: {result['source_dir']}")
    screen_add(stdscr, 3, 0, f"Output: {result['result_dir']}")
    screen_add(stdscr, 4, 0, f"Scheme: {result['scheme']}")
    screen_add(stdscr, 5, 0, f"Layout: {result['layout']}")
    screen_add(stdscr, 6, 0, f"Renderer: {result['renderer_id']}")
    screen_add(stdscr, 7, 0, f"Compression: {result['compression']} ({result['format']})")
    screen_add(stdscr, 8, 0, f"Cards: {len(result['outputs'])}")
    if result["contact_sheet"]:
        screen_add(stdscr, 9, 0, f"Contact sheet: {result['contact_sheet']}")
    screen_add(stdscr, 10, 0, f"Manifest: {result['manifest']}")
    screen_add(stdscr, 11, 0, "Press any key to exit.")
    stdscr.refresh()
    stdscr.getch()
    return 0
