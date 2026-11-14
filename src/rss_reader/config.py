"""Loading of the feed list file (feeds.txt)."""

from __future__ import annotations

import logging
from pathlib import Path

from .models import Category, ConfigError, FeedConfig

FEEDS_FILENAME = "feeds.txt"
TITLE_PREFIX = "title:"
EXCLUDE_TITLE_PREFIX = "!title:"
UNCATEGORIZED = "未分類"

logger = logging.getLogger(__name__)


def load_categories(path: Path) -> list[Category]:
    """Return the categories listed in *path*, each with its feeds.

    A non-indented ``# name`` line starts a category; indented ``#`` lines are
    comments. URLs before the first category belong to ``UNCATEGORIZED``.
    A URL line may be followed by indented ``title:<pattern>`` (show only
    matching articles) and ``!title:<pattern>`` (hide matching articles) lines.
    Blanks and URLs repeated within a category are skipped; categories without
    any URL are dropped.
    """
    try:
        text = Path(path).read_text(encoding="utf-8-sig")
    except FileNotFoundError:
        raise ConfigError(
            f"feeds.txt が見つかりません: {path}（feeds.example.txt をコピーして作成してください）"
        ) from None
    except OSError as e:
        raise ConfigError(f"feeds.txt を読み込めません: {path} ({e})") from None

    # category name -> URL -> (title patterns, exclude patterns); dicts keep insertion order
    categories: dict[str, dict[str, tuple[list[str], list[str]]]] = {}
    category = UNCATEGORIZED
    current: tuple[list[str], list[str]] | None = None  # patterns of the URL that indented lines belong to
    skipping = False  # True while inside the block of an ignored duplicate URL
    for lineno, raw in enumerate(text.splitlines(), start=1):
        line = raw.strip()
        if not line:
            continue
        indented = raw[0] in " \t"
        if line.startswith("#"):
            name = line.lstrip("#").strip()
            if not indented and name:
                category, current, skipping = name, None, False
                categories.setdefault(name, {})  # fixes the tab order at first appearance
            continue
        is_url = line.lower().startswith(("http://", "https://"))
        if indented and not is_url:
            if skipping:
                continue
            exclude = _parse_prefixed(line, EXCLUDE_TITLE_PREFIX)
            pattern = _parse_prefixed(line, TITLE_PREFIX)
            if current is None or not (exclude or pattern):
                logger.warning("%s:%d: 表示パターンとして解釈できない行を無視しました: %s", path, lineno, line)
                continue
            if exclude:
                current[1].append(exclude)
            else:
                current[0].append(pattern)
            continue
        if not is_url:
            logger.warning("%s:%d: URLではない行を無視しました: %s", path, lineno, line)
            current, skipping = None, False
            continue
        feeds = categories.setdefault(category, {})
        if line in feeds:
            current, skipping = None, True
            continue
        current, skipping = ([], []), False
        feeds[line] = current
    return [
        Category(name, tuple(FeedConfig(url, tuple(t), tuple(x)) for url, (t, x) in feeds.items()))
        for name, feeds in categories.items()
        if feeds
    ]


def unique_urls(categories: list[Category]) -> list[str]:
    """Return every feed URL once, in order of first appearance."""
    return list(dict.fromkeys(f.url for c in categories for f in c.feeds))


def _parse_prefixed(line: str, prefix: str) -> str:
    """Return the pattern after *prefix* (case-insensitive), or an empty string if absent."""
    if not line.lower().startswith(prefix):
        return ""
    return line[len(prefix):].strip()
