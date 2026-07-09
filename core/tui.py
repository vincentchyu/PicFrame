import curses
from pathlib import Path

from .batch import generate_from_source


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
        screen_add(stdscr, 0, 0, "PicFrame34 源文件夹")
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


def choose_layout(stdscr):
    options = [
        ("portrait", "照片源保持 3:4 的比例。"),
        ("landscape", "照片源使用 4:3 左图卡。"),
    ]
    selected = 1
    while True:
        stdscr.clear()
        screen_add(stdscr, 0, 0, "PicFrame34 布局")
        screen_add(stdscr, 2, 0, "请选择宽度小于高度的源照片进行渲染:")
        screen_add(stdscr, 3, 0, "Enter: 选择   q/Esc: 返回")
        for idx, (name, desc) in enumerate(options, start=5):
            attr = curses.A_REVERSE if idx - 5 == selected else 0
            marker = "> " if idx - 5 == selected else "  "
            screen_add(stdscr, idx, 0, f"{marker}{name:<9} {desc}", attr)
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
        screen_add(stdscr, 0, 0, "PicFrame34 generating")
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
    layout = choose_layout(stdscr)
    if layout is None:
        return 0

    try:
        result = generate_from_source(source_dir, progress_callback=tui_status_callback(stdscr), layout=layout)
    except Exception as exc:
        stdscr.clear()
        screen_add(stdscr, 0, 0, "PicFrame34 failed")
        screen_add(stdscr, 2, 0, str(exc))
        screen_add(stdscr, 4, 0, "Press any key to exit.")
        stdscr.refresh()
        stdscr.getch()
        return 1

    stdscr.clear()
    screen_add(stdscr, 0, 0, "PicFrame34 complete")
    screen_add(stdscr, 2, 0, f"Source: {result['source_dir']}")
    screen_add(stdscr, 3, 0, f"Output: {result['result_dir']}")
    screen_add(stdscr, 4, 0, f"Layout: {result['layout']}")
    screen_add(stdscr, 5, 0, f"Cards: {len(result['outputs'])}")
    if result["contact_sheet"]:
        screen_add(stdscr, 6, 0, f"Contact sheet: {result['contact_sheet']}")
    screen_add(stdscr, 8, 0, "Press any key to exit.")
    stdscr.refresh()
    stdscr.getch()
    return 0

