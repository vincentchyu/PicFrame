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
    "scheme3": (
        "> [01 / MATRIX DECODE]   ",
        "|        PHOTO          |",
        "|    (忠实摄影原片)     |",
        "+-----------------------+",
        "|  ████░░░░████░░████  |",
        "|  ██████████████████  |",
        "| [02 / TELEMETRY DATA] |",
        "| MODEL :: NIKON Z6III  |",
        "| EXIF  :: 120mm · f/5.6|",
        "+-----------------------+",
        "黑客终端与 ASCII 结构解构方案",
        "智能自适应黑客终端 HUD 仪表舱与原图主色 ASCII 解构双联",
    ),
    "scheme4": (
        "┌───────────────────────┐",
        "│        PHOTO          │",
        "│    (忠实摄影原片)     │",
        "├───────────────────────┤",
        "│ ┌─ ─ ─ ─ ─ ─ ─ ─ ─ ─┐ │",
        "│ │  ~ ~ ┼ [◎] 01 ~ ~ │ │",
        "│ └─ ─ ─ ─ ─ ─ ─ ─ ─ ─┘ │",
        "│     THE BLUE HOUR     │",
        "│   Light & Dialogue    │",
        "└───────────────────────┘",
        "编辑艺术双联方案 (Editorial Diptych)",
        "原片忠实呈现 + 象牙白面板，支持微观晶格肌理与精工手稿骨架解构",
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
    "gallery_ascii_terminal": (
        "> [01 / MATRIX DECODE]   ",
        "|        PHOTO          |",
        "|    (忠实摄影原片)     |",
        "+-----------------------+",
        "|  ████░░░░████░░████  |",
        "|  ██████████████████  |",
        "| [02 / TELEMETRY DATA] |",
        "| MODEL :: NIKON Z6III  |",
        "| EXIF  :: 120mm · f/5.6|",
        "+-----------------------+",
        "智能自适应黑客终端 HUD 装裱",
        "智能亮暗自适应终端底板 + 极客荧光/深墨绿 HUD 仪表舱",
    ),
    "gallery_ascii_diptych": (
        "┌───────────────────────┐",
        "│        PHOTO          │",
        "│    (忠实摄影原片)     │",
        "├───────────────────────┤",
        "│  ██░░░░░░░░░░░░░░██  │",
        "│  ████░░░░████░░████  │",
        "│  ██████████████████  │",
        "│ AUTH :: VINCENT CHYU  │",
        "│     [■ ■ ■ ■] 色卡   │",
        "└───────────────────────┘",
        "原片主色 ASCII 解构双联",
        "原片提取主色背景 + 真实色彩 ASCII 结构画 + 色卡网格",
    ),
    "editorial_diptych": (
        "┌───────────────────────┐",
        "│        PHOTO          │",
        "│    (忠实摄影原片)     │",
        "├───────────────────────┤",
        "│    ─── [▲][▼] ───     │",
        "│   (200 晶格几何肌理)  │",
        "│     THE BLUE HOUR     │",
        "│   Light & Dialogue    │",
        "└───────────────────────┘",
        "经典几何肌理双联 (200 晶格)",
        "高密微晶格拟合微观光影肌理 + 移动端清晰大字阶",
    ),
    "editorial_guidance": (
        "┌───────────────────────┐",
        "│        PHOTO          │",
        "│    (忠实摄影原片)     │",
        "├───────────────────────┤",
        "│ ┌─ ─ ─ ─ ─ ─ ─ ─ ─ ─┐ │",
        "│ │  ~ ~ ┼ [◎] 01 ~ ~ │ │",
        "│ └─ ─ ─ ─ ─ ─ ─ ─ ─ ─┘ │",
        "│     AUTUMN GRAZING    │",
        "│   Slope & Focal Axis  │",
        "└───────────────────────┘",
        "精工手稿风与视觉骨架引导",
        "实线主轮廓 + 辅助虚线 + 光影排线 + 浅彩焦点准星微标",
    ),
    "editorial_asymmetric": (
        "┌───────────────────────┐",
        "│        PHOTO          │",
        "│    (忠实摄影原片)     │",
        "├───────────────────────┤",
        "│       ── [■][■] • ──  │",
        "│  FIRST LIGHT          │",
        "│  The Awakening        │",
        "└───────────────────────┘",
        "非对称现代主义画册布局",
        "右偏几何抽象母题 + 左下角大写衬线标题，张力十足",
    ),
    "editorial_minimal": (
        "┌───────────────────────┐",
        "│        PHOTO          │",
        "│    (忠实摄影原片)     │",
        "├───────────────────────┤",
        "│                       │",
        "│      ──── [■] ────    │",
        "│     SILENT AXIS       │",
        "│                       │",
        "└───────────────────────┘",
        "极简留白空间画册布局",
        "超高比例象牙色留白 + 极细结构线与色块记忆",
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
        "gallery_ascii_terminal": "智能自适应明暗黑客终端 + 极客 HUD 仪表舱。",
        "gallery_ascii_diptych": "原片主色调 + 真实色彩 ASCII 结构画双联。",
        "editorial_diptych": "经典几何肌理双联 (200 晶格退火拟合)。",
        "editorial_guidance": "精工手稿风 + 视觉骨架与浅彩双焦点准星。",
        "editorial_asymmetric": "非对称现代主义画册 + 左下对齐大写衬线标题。",
        "editorial_minimal": "极简超大留白画册 + 极细结构线与色块记忆。",
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
            screen_add(stdscr, idx, 0, f"{marker}{layout:<21} {descriptions.get(layout, )}", attr)

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
    options = [("none", "无压缩 (输出原尺寸高精 PNG)"), ("jpeg", "移动端优化 (输出 1080 边长优质 JPEG)")]
    selected = 0
    while True:
        stdscr.clear()
        screen_add(stdscr, 0, 0, "PicFrame 输出格式与压缩")
        screen_add(stdscr, 2, 0, "请选择输出图像格式与压缩策略:")
        screen_add(stdscr, 3, 0, "Enter: 选择   q/Esc: 返回")
        for idx, (val, desc) in enumerate(options, start=5):
            attr = curses.A_REVERSE if idx - 5 == selected else 0
            marker = "> " if idx - 5 == selected else "  "
            screen_add(stdscr, idx, 0, f"{marker}{val:<8} {desc}", attr)
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


def run_tui(stdscr):
    curses.curs_set(0)
    source = choose_source_dir(stdscr, Path.cwd())
    if not source:
        return 0
    scheme = choose_scheme(stdscr)
    if not scheme:
        return 0
    layout = choose_layout(stdscr, scheme)
    if not layout:
        return 0
    compression = choose_compression(stdscr)
    if not compression:
        return 0

    curses.endwin()
    result = generate_from_source(source, scheme=scheme, layout=layout, compression=compression)
    print(f"\n生成成功！成品已保存至: {result['result_dir']}")
    for out in result["outputs"]:
        print(out)
    if result["contact_sheet"]:
        print(result["contact_sheet"])
    return 0


def launch_tui(start_dir=None):
    return curses.wrapper(run_tui)

