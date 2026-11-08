"""Command-line entry point."""

from __future__ import annotations

import argparse
import logging
import sys
from pathlib import Path

from . import __version__


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="rss_reader",
        description="feeds.txt に登録したRSSフィードを一覧表示するRSSリーダー",
    )
    parser.add_argument(
        "--data-dir",
        type=Path,
        default=Path.cwd(),
        metavar="DIR",
        help="feeds.txt と read.json を置くフォルダ（既定: カレントフォルダ）",
    )
    parser.add_argument("--version", action="version", version=f"rss_reader {__version__}")
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    logging.basicConfig(level=logging.WARNING, format="%(levelname)s: %(message)s")

    data_dir: Path = args.data_dir
    if not data_dir.is_dir():
        print(f"rss_reader: エラー: データフォルダが存在しません: {data_dir}", file=sys.stderr)
        return 1

    # Import tkinter lazily so --help/--version work without a display
    import tkinter as tk

    from .gui import App

    root = tk.Tk()
    App(root, data_dir)
    root.mainloop()
    return 0


if __name__ == "__main__":
    sys.exit(main())
