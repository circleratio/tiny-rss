"""Loading of the feed list file (feeds.txt)."""

from __future__ import annotations

import logging
from pathlib import Path

from .models import ConfigError, FeedConfig

FEEDS_FILENAME = "feeds.txt"
TITLE_PREFIX = "title:"

logger = logging.getLogger(__name__)


def load_feeds(path: Path) -> list[FeedConfig]:
    """Return feeds listed in *path* with their per-feed title patterns.

    A URL line may be followed by indented ``title:<pattern>`` lines.
    Blanks, comments and duplicate URLs are skipped.
    """
    try:
        text = Path(path).read_text(encoding="utf-8-sig")
    except FileNotFoundError:
        raise ConfigError(
            f"feeds.txt が見つかりません: {path}（feeds.example.txt をコピーして作成してください）"
        ) from None
    except OSError as e:
        raise ConfigError(f"feeds.txt を読み込めません: {path} ({e})") from None

    urls: list[str] = []
    patterns: dict[str, list[str]] = {}
    current: str | None = None  # URL that indented lines belong to
    skipping = False  # True while inside the block of an ignored duplicate URL
    for lineno, raw in enumerate(text.splitlines(), start=1):
        line = raw.strip()
        if not line or line.startswith("#"):
            continue
        is_url = line.lower().startswith(("http://", "https://"))
        if raw[0] in " \t" and not is_url:
            if skipping:
                continue
            pattern = _parse_title_pattern(line)
            if current is None or not pattern:
                logger.warning("%s:%d: 表示パターンとして解釈できない行を無視しました: %s", path, lineno, line)
                continue
            patterns[current].append(pattern)
            continue
        if not is_url:
            logger.warning("%s:%d: URLではない行を無視しました: %s", path, lineno, line)
            current, skipping = None, False
            continue
        if line in patterns:
            current, skipping = None, True
            continue
        current, skipping = line, False
        patterns[line] = []
        urls.append(line)
    return [FeedConfig(url, tuple(patterns[url])) for url in urls]


def _parse_title_pattern(line: str) -> str:
    """Return the pattern of a ``title:`` line, or an empty string if it is not one."""
    if not line.lower().startswith(TITLE_PREFIX):
        return ""
    return line[len(TITLE_PREFIX):].strip()
