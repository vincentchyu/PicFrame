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
        "┌───────────────────────┐",
        "│        PHOTO          │",
        "│    (忠实摄影原片)     │",
        "├───────────┬───────────┤",
        "│ [01/ASCII]│[02/TELEM] │",
        "│ ████░░███ │MODEL::Z6  │",
        "│ █████████ │TONE::[■■] │",
        "└───────────┴───────────┘",
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
        "┌───────────────────────┐",
        "│        PHOTO          │",
        "│    (忠实摄影原片)     │",
        "├───────────┬───────────┤",
        "│ [01/ASCII]│[02/TELEM] │",
        "│ ████░░███ │MODEL::Z6  │",
        "│ █████████ │TONE::[■■] │",
        "└───────────┴───────────┘",
        "智能自适应黑客终端 HUD 装裱",
        "智能亮暗自适应终端底板 + 左右分栏大画幅 ASCII 伴侣艺术",
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


import queue
import threading
import time

from .domain.events import EventLevel, PipelineStage, ProgressEvent
from .domain.task import TaskSummary
from .plan import plan_batch


def confirm_plan(stdscr, source_dir, scheme_id, layout, compression):
    """展示预检 (Dry-Run / Plan) 结果与参数清单，等待用户确认执行。"""
    stdscr.clear()
    screen_add(stdscr, 0, 0, "PicFrame 任务预检与体检 (Plan / Dry-Run)", curses.A_BOLD)
    screen_add(stdscr, 1, 0, "正在快速扫描元数据并评估依赖...", curses.A_DIM)
    stdscr.refresh()

    plan_res = plan_batch(source_dir, scheme=scheme_id, layout=layout)
    if plan_res.total_photos == 0:
        stdscr.clear()
        screen_add(stdscr, 0, 0, "PicFrame 任务预检失败", curses.A_BOLD)
        screen_add(stdscr, 2, 0, f"源路径: {source_dir}")
        for idx, w in enumerate(plan_res.warnings, start=4):
            screen_add(stdscr, idx, 0, f"⚠️  {w.reason}")
            if w.suggestion:
                screen_add(stdscr, idx + 1, 4, f"建议: {w.suggestion}", curses.A_DIM)
        screen_add(stdscr, len(plan_res.warnings) * 2 + 6, 0, "按任意键返回...")
        stdscr.refresh()
        stdscr.getch()
        return False

    while True:
        stdscr.clear()
        height, width = stdscr.getmaxyx()
        screen_add(stdscr, 0, 0, "PicFrame 任务预检就绪 (Plan / Ready)", curses.A_BOLD)
        screen_add(stdscr, 1, 0, "─" * min(width - 2, 60), curses.A_DIM)

        screen_add(stdscr, 2, 0, f"📁 源文件夹: {source_dir}")
        screen_add(stdscr, 3, 0, f"🎨 渲染方案: {scheme_id} ({layout})")
        screen_add(stdscr, 4, 0, f"📦 输出格式: {'高精 PNG' if compression == 'none' else '移动端 JPEG'}")
        screen_add(stdscr, 5, 0, f"📊 待处理照片: {plan_res.total_photos} 张 (就绪 {plan_res.ready_count} 张)")
        screen_add(stdscr, 6, 0, f"⏱️ 预估总耗时: 约 {plan_res.estimated_duration_sec:.1f} 秒")
        screen_add(stdscr, 7, 0, f"🛰️ GPS 覆盖度: {plan_res.details.get('gps_coverage', '未知')}")

        cams = plan_res.details.get("detected_cameras", [])
        if cams:
            screen_add(stdscr, 8, 0, f"📷 检测机身: {', '.join(cams[:2])}")
        lenses = plan_res.details.get("detected_lenses", [])
        if lenses:
            screen_add(stdscr, 9, 0, f"🔍 检测镜头: {', '.join(lenses[:2])}")

        row = 11
        if plan_res.warnings:
            screen_add(stdscr, row, 0, "⚠️  体检告警提示:", curses.A_BOLD)
            row += 1
            for w in plan_res.warnings[:3]:
                screen_add(stdscr, row, 2, f"• {w.reason}")
                row += 1

        screen_add(stdscr, row + 1, 0, "─" * min(width - 2, 60), curses.A_DIM)
        screen_add(stdscr, row + 2, 0, "Enter: 立即启动执行   q/Esc: 返回修改参数", curses.A_STANDOUT)
        stdscr.refresh()

        key = stdscr.getch()
        if key in (ord("q"), 27):
            return False
        if key in (curses.KEY_ENTER, 10, 13):
            return True


def _init_tui_colors():
    """初始化 TUI 彩色主题配对"""
    if curses.has_colors():
        try:
            curses.start_color()
            curses.use_default_colors()
            curses.init_pair(1, curses.COLOR_GREEN, -1)    # 绿色：成功/重点
            curses.init_pair(2, curses.COLOR_CYAN, -1)     # 青色：AI/VLM/地貌主体
            curses.init_pair(3, curses.COLOR_MAGENTA, -1)  # 洋红：几何/SVG/ASCII
            curses.init_pair(4, curses.COLOR_YELLOW, -1)   # 黄色：告警
            curses.init_pair(5, curses.COLOR_RED, -1)      # 红色：错误
        except Exception:
            pass


def _get_event_attr(ev: ProgressEvent) -> int:
    """根据微步骤事件的标签与级别返回色彩与字体修饰"""
    tag = ev.step_tag.upper()
    has_color = curses.has_colors()

    if ev.level == EventLevel.ERROR:
        return curses.color_pair(5) | curses.A_BOLD if has_color else curses.A_STANDOUT
    if ev.level == EventLevel.WARN:
        return curses.color_pair(4) | curses.A_BOLD if has_color else curses.A_STANDOUT
    if ev.level == EventLevel.SUCCESS or "[DONE]" in tag:
        return curses.color_pair(1) | curses.A_BOLD if has_color else curses.A_BOLD

    if "[VLM" in tag or "[SPATIAL]" in tag:
        return curses.color_pair(2) if has_color else curses.A_NORMAL
    if "[ASCII]" in tag or "[SOBEL]" in tag or "[GEOMETRIC]" in tag or "[SVG]" in tag:
        return curses.color_pair(3) if has_color else curses.A_NORMAL
    if "[ASSET]" in tag or "[LOGO]" in tag or "[EXIF]" in tag:
        return curses.color_pair(1) if has_color else curses.A_NORMAL

    return curses.A_NORMAL


def render_execution_and_summary(stdscr, source, scheme, layout, compression):
    """在 TUI 内部启动后台线程执行渲染，前台平滑刷新进度条、彩色微步骤与方案专属遥测面板。"""
    _init_tui_colors()
    event_queue = queue.Queue()
    result_holder = {}
    error_holder = {}

    def worker():
        try:
            res = generate_from_source(
                source,
                scheme=scheme,
                layout=layout,
                compression=compression,
                event_callback=event_queue.put,
            )
            result_holder["result"] = res
        except Exception as exc:
            error_holder["error"] = exc

    t = threading.Thread(target=worker, daemon=True)
    t.start()

    stdscr.nodelay(True)
    stdscr.timeout(50)

    recent_logs: list[ProgressEvent] = []
    current_stage = PipelineStage.SCANNING
    current_index = 0
    total_items = 0
    current_msg = "正在初始化流水线..."
    current_photo = ""
    telemetry_facts: dict = {}

    while t.is_alive() or not event_queue.empty():
        while True:
            try:
                ev: ProgressEvent = event_queue.get_nowait()
                current_stage = ev.stage
                current_msg = ev.message
                if ev.current_index:
                    current_index = ev.current_index
                if ev.total_items:
                    total_items = ev.total_items
                if ev.photo_path:
                    # 切换照片时清理上一张的部分瞬时遥测
                    if current_photo != ev.photo_path.name:
                        current_photo = ev.photo_path.name
                        telemetry_facts = {}

                # 累积当前照片专属的客制化业务数据
                if ev.details:
                    telemetry_facts.update(ev.details)

                recent_logs.append(ev)
                if len(recent_logs) > 9:
                    recent_logs.pop(0)
            except queue.Empty:
                break

        # 绘制实时仪表板
        stdscr.clear()
        height, width = stdscr.getmaxyx()
        green_attr = curses.color_pair(1) | curses.A_BOLD if curses.has_colors() else curses.A_BOLD
        cyan_attr = curses.color_pair(2) if curses.has_colors() else curses.A_NORMAL
        magenta_attr = curses.color_pair(3) if curses.has_colors() else curses.A_NORMAL
        dim_attr = curses.A_DIM

        screen_add(stdscr, 0, 0, "⚡ PicFrame 摄影卡片批量渲染流水线", curses.A_BOLD)
        screen_add(stdscr, 1, 0, "─" * min(width - 2, 78), dim_attr)

        # 进度条
        pct = (current_index / total_items) if total_items > 0 else 0.0
        bar_len = max(10, min(width - 30, 36))
        filled = int(bar_len * pct)
        bar_str = f"[{'█' * filled}{'░' * (bar_len - filled)}] {int(pct * 100)}%"
        screen_add(stdscr, 3, 0, f"阶段: {current_stage.value}  ({current_index}/{total_items})", curses.A_BOLD)
        screen_add(stdscr, 4, 0, bar_str, green_attr)

        screen_add(stdscr, 6, 0, f"当前任务: {current_msg}")
        if current_photo:
            screen_add(stdscr, 7, 0, f"正在处理: {current_photo}  |  方案: {scheme} ({layout})", dim_attr)

        # 判断是否双栏显示遥测面板
        is_split = width >= 80
        left_w = min(width // 2 + 2, 48) if is_split else width

        # 左栏：微步骤日志
        screen_add(stdscr, 9, 0, "📜 实时微步骤事件日志:", curses.A_BOLD)
        for idx, log_ev in enumerate(recent_logs, start=10):
            if idx >= height - 2:
                break
            tag = f"{log_ev.step_tag} " if log_ev.step_tag else ""
            attr = _get_event_attr(log_ev)
            msg_text = f"• {tag}{log_ev.message}"
            if is_split:
                safe_len = left_w - 4
                msg_text = msg_text[:safe_len]
            screen_add(stdscr, idx, 0, msg_text, attr)

        # 右栏：方案专属客制化业务数据与遥测面板 (Telemetry Inspector)
        if is_split:
            rx = left_w + 2
            for ry in range(9, min(height - 1, 20)):
                screen_add(stdscr, ry, rx - 2, "│", dim_attr)

            screen_add(stdscr, 9, rx, "🛰️ 业务数据与遥测洞察 (Telemetry):", curses.A_BOLD)
            r_row = 10

            if scheme == "scheme4":
                # 方案4 VLM 专属语义事实
                st = telemetry_facts.get("scene_type")
                mood = telemetry_facts.get("mood")
                hero = telemetry_facts.get("hero_focus")
                title = telemetry_facts.get("title")
                subtitle = telemetry_facts.get("subtitle")
                art = telemetry_facts.get("concept_title")
                pal = telemetry_facts.get("palette_hex")
                geom = telemetry_facts.get("geometry_mode")
                svg_l = telemetry_facts.get("svg_len")

                if st or mood:
                    screen_add(stdscr, r_row, rx, f"├─ 场景地貌: {st or '自然'} / {mood or '原画光影'}", cyan_attr)
                    r_row += 1
                if hero:
                    screen_add(stdscr, r_row, rx, f"├─ 核心主角: {hero}", cyan_attr)
                    r_row += 1
                if title:
                    screen_add(stdscr, r_row, rx, f"├─ 策展标题: \"{title}\"", green_attr)
                    r_row += 1
                if subtitle:
                    screen_add(stdscr, r_row, rx, f"├─ 诗性副标: \"{subtitle}\"", dim_attr)
                    r_row += 1
                if art:
                    screen_add(stdscr, r_row, rx, f"├─ 艺术理论: {art}", magenta_attr)
                    r_row += 1
                if pal and isinstance(pal, dict):
                    hex_str = " ".join([f"{k}:{v}" for k, v in list(pal.items())[:3]])
                    screen_add(stdscr, r_row, rx, f"├─ 提取色板: {hex_str}", green_attr)
                    r_row += 1
                if geom or svg_l:
                    screen_add(stdscr, r_row, rx, f"└─ 几何工序: {geom or 'Delaunay'} ({svg_l or 0} 字符)", magenta_attr)
                    r_row += 1
                if r_row == 10:
                    screen_add(stdscr, r_row, rx, "├─ 等待 VLM 视觉大模型深度解构...", dim_attr)

            elif scheme == "scheme3":
                # 方案3 极客 ASCII 遥测
                cam = telemetry_facts.get("camera")
                gps = telemetry_facts.get("gps")
                bg = telemetry_facts.get("bg_color")
                charset = telemetry_facts.get("charset")
                kernel = telemetry_facts.get("edge_kernel")

                if cam:
                    screen_add(stdscr, r_row, rx, f"├─ 机身型号: {cam}", green_attr)
                    r_row += 1
                if gps:
                    screen_add(stdscr, r_row, rx, f"├─ GPS遥测: {gps}", green_attr)
                    r_row += 1
                if kernel:
                    screen_add(stdscr, r_row, rx, f"├─ 边缘算子: {kernel} (梯度量化完成)", cyan_attr)
                    r_row += 1
                if charset:
                    screen_add(stdscr, r_row, rx, f"├─ 字符矩阵: 48×64 ({charset})", magenta_attr)
                    r_row += 1
                if bg:
                    screen_add(stdscr, r_row, rx, f"└─ 终端基底: RGB{bg} (自适应明暗)", dim_attr)
                    r_row += 1

            elif scheme == "scheme2":
                # 方案2 水印带参数
                cam = telemetry_facts.get("camera")
                lens = telemetry_facts.get("lens")
                logo = telemetry_facts.get("brand_logo")
                mode = telemetry_facts.get("mode")

                if cam or lens:
                    screen_add(stdscr, r_row, rx, f"├─ 器材组合: {cam or ''} {lens or ''}", green_attr)
                    r_row += 1
                if logo:
                    screen_add(stdscr, r_row, rx, f"├─ 品牌Logo: {logo} (右侧布局)", cyan_attr)
                    r_row += 1
                if mode:
                    screen_add(stdscr, r_row, rx, f"└─ 水印算法: {mode} (无损拼接)", dim_attr)
                    r_row += 1

            else:
                # 方案1 极简卡片参数
                cam = telemetry_facts.get("camera")
                lens = telemetry_facts.get("lens")
                exp = telemetry_facts.get("exposure")
                c_asset = telemetry_facts.get("camera_asset")
                l_asset = telemetry_facts.get("lens_asset")
                bg = telemetry_facts.get("bg_rgb")

                if cam or lens:
                    screen_add(stdscr, r_row, rx, f"├─ 器材型号: {cam or ''} | {lens or ''}", green_attr)
                    r_row += 1
                if exp:
                    screen_add(stdscr, r_row, rx, f"├─ 曝光参数: {exp}", cyan_attr)
                    r_row += 1
                if c_asset or l_asset:
                    screen_add(stdscr, r_row, rx, f"├─ 图标匹配: 机身[{c_asset or '默认'}] 镜头[{l_asset or '默认'}]", magenta_attr)
                    r_row += 1
                if bg:
                    screen_add(stdscr, r_row, rx, f"└─ 软调色板: RGB{bg}", dim_attr)
                    r_row += 1

        stdscr.refresh()
        stdscr.getch()  # 吞噬非阻塞按键
        time.sleep(0.03)

    t.join()
    stdscr.nodelay(False)

    if "error" in error_holder:
        stdscr.clear()
        screen_add(stdscr, 0, 0, "❌ PicFrame 执行遇到严重错误", curses.A_BOLD)
        screen_add(stdscr, 2, 0, f"错误原因: {error_holder['error']}")
        screen_add(stdscr, 4, 0, "按任意键退出...")
        stdscr.refresh()
        stdscr.getch()
        return 1

    # 渲染任务结算卡片
    res = result_holder.get("result", {})
    summary: TaskSummary = res.get("summary")
    while True:
        stdscr.clear()
        height, width = stdscr.getmaxyx()
        screen_add(stdscr, 0, 0, "🎉 PicFrame 摄影卡片批量生成完毕！", curses.A_BOLD)
        screen_add(stdscr, 1, 0, "─" * min(width - 2, 70), curses.A_DIM)

        green_attr = curses.color_pair(1) | curses.A_BOLD if curses.has_colors() else curses.A_BOLD
        screen_add(stdscr, 3, 0, f"✅ 成功生成: {summary.success} / {summary.total} 张", green_attr)
        screen_add(stdscr, 4, 0, f"⏱️ 实际总耗时: {summary.elapsed_seconds:.2f} 秒")
        screen_add(stdscr, 5, 0, f"📁 成品目录: {res.get('result_dir')}")
        if summary.contact_sheet:
            screen_add(stdscr, 6, 0, f"🖼️ 摄影总览联系单: {summary.contact_sheet.name}")
        if summary.report_path:
            screen_add(stdscr, 7, 0, f"📑 生成结算报告: {summary.report_path.name}")

        row = 9
        if summary.warnings:
            screen_add(stdscr, row, 0, f"⚠️  告警记录 ({len(summary.warnings)} 条):", curses.A_BOLD)
            row += 1
            for w in summary.warnings[:4]:
                screen_add(stdscr, row, 2, f"• {w.reason}")
                row += 1

        screen_add(stdscr, row + 2, 0, "按 Enter 或 q/Esc 返回主工作台...", curses.A_STANDOUT)
        stdscr.refresh()
        key = stdscr.getch()
        if key in (curses.KEY_ENTER, 10, 13, ord("q"), 27, ord(" ")):
            break

    return 0


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

    # 预检与体检确认
    if not confirm_plan(stdscr, source, scheme, layout, compression):
        return 0

    # 启动 TUI 实时进度与结算仪表板
    return render_execution_and_summary(stdscr, source, scheme, layout, compression)


def launch_tui(start_dir=None):
    return curses.wrapper(run_tui)


