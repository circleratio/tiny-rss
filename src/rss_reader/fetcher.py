"""Downloading feeds over HTTP."""

from __future__ import annotations

import urllib.error
import urllib.request
from concurrent.futures import ThreadPoolExecutor

from . import __version__
from .models import FeedFetchError, FeedResult, RssReaderError
from .parser import parse_feed

USER_AGENT = f"rss_reader/{__version__}"
TIMEOUT_SEC = 15
MAX_WORKERS = 8


def fetch(url: str, timeout: float = TIMEOUT_SEC) -> bytes:
    """Download *url* and return the response body."""
    req = urllib.request.Request(url, headers={"User-Agent": USER_AGENT})
    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            return resp.read()
    except urllib.error.HTTPError as e:
        raise FeedFetchError(f"HTTP {e.code}") from None
    except urllib.error.URLError as e:
        if isinstance(e.reason, TimeoutError):
            raise FeedFetchError("タイムアウト") from None
        raise FeedFetchError(f"接続できません: {e.reason}") from None
    except TimeoutError:
        raise FeedFetchError("タイムアウト") from None
    except OSError as e:
        raise FeedFetchError(f"接続できません: {e}") from None


def fetch_feed(url: str) -> FeedResult:
    """Fetch and parse one feed. Never raises application errors."""
    try:
        return FeedResult(url=url, feed=parse_feed(fetch(url), url), error=None)
    except RssReaderError as e:
        return FeedResult(url=url, feed=None, error=str(e))


def fetch_all(urls: list[str]) -> list[FeedResult]:
    """Fetch all feeds in parallel, returning results in the order of *urls*."""
    if not urls:
        return []
    with ThreadPoolExecutor(max_workers=min(MAX_WORKERS, len(urls))) as pool:
        return list(pool.map(fetch_feed, urls))
