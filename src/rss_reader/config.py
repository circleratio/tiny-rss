"""Loading of the feed list file (feeds.txt)."""

from __future__ import annotations

import logging
from pathlib import Path

from .models import ConfigError

FEEDS_FILENAME = "feeds.txt"

logger = logging.getLogger(__name__)


def load_feed_urls(path: Path) -> list[str]:
    """Return feed URLs listed in *path*, skipping blanks, comments and duplicates."""
    try:
        text = Path(path).read_text(encoding="utf-8-sig")
    except FileNotFoundError:
        raise ConfigError(
            f"feeds.txt が見つかりません: {path}（feeds.example.txt をコピーして作成してください）"
        ) from None
    except OSError as e:
        raise ConfigError(f"feeds.txt を読み込めません: {path} ({e})") from None

    urls: list[str] = []
    seen: set[str] = set()
    for lineno, raw in enumerate(text.splitlines(), start=1):
        line = raw.strip()
        if not line or line.startswith("#"):
            continue
        if not line.lower().startswith(("http://", "https://")):
            logger.warning("%s:%d: URLではない行を無視しました: %s", path, lineno, line)
            continue
        if line in seen:
            continue
        seen.add(line)
        urls.append(line)
    return urls
