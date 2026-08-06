import argparse
import curses
import subprocess
import sys
from pathlib import Path

from .batch import generate, generate_from_source
from .presentation import load_presentation_schemes
from .tui import run_tui


def main():
    parser = argparse.ArgumentParser(description="Generate PicFrame photography info cards.")
    parser.add_argument("--source", help="folder that directly contains source photos")
    parser.add_argument("--output", help="output folder for --source; defaults to <source>/PicFrame")
    schemes = load_presentation_schemes()
    parser.add_argument("--scheme", choices=sorted(schemes), default="scheme1", help="presentation scheme")
    parser.add_argument("--layout", help="layout within the selected presentation scheme")
    parser.add_argument("--compression", choices=("none", "jpeg"), default="none", help="card output encoding")
    parser.add_argument("--legacy-task", help="legacy task folder containing src/")
    args = parser.parse_args()

    if args.source and args.legacy_task:
        parser.error("--source and --legacy-task cannot be used together")
    if args.output and not args.source:
        parser.error("--output can only be used with --source")

    try:
        if args.legacy_task:
            generate(Path(args.legacy_task), layout=args.layout, scheme=args.scheme, compression=args.compression)
            return 0
        if args.source:
            result = generate_from_source(
                Path(args.source),
                Path(args.output) if args.output else None,
                layout=args.layout,
                scheme=args.scheme,
                compression=args.compression,
            )
            print(f"Generated {len(result['outputs'])} cards in {result['result_dir']}")
            for out in result["outputs"]:
                print(out)
            if result["contact_sheet"]:
                print(result["contact_sheet"])
            return 0
        return curses.wrapper(run_tui)
    except (FileNotFoundError, NotADirectoryError, ValueError, subprocess.CalledProcessError) as exc:
        print(f"Error: {exc}", file=sys.stderr)
        return 1
