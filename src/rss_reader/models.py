"""Data classes and exceptions shared across modules."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime


@dataclass(frozen=True)
class Article:
    title: str
    link: str  # key for read-state management
    published: datetime | None  # timezone-aware, normalized to UTC
    feed_title: str


@dataclass(frozen=True)
class Feed:
    url: str
    title: str
    articles: list[Article] = field(default_factory=list)


@dataclass(frozen=True)
class FeedResult:
    url: str
    feed: Feed | None
    error: str | None  # user-facing message on failure


class RssReaderError(Exception):
    """Base class for application errors."""


class ConfigError(RssReaderError):
    """Raised when the feed list cannot be loaded."""


class FeedFetchError(RssReaderError):
    """Raised when a feed cannot be downloaded."""


class FeedParseError(RssReaderError):
    """Raised when a feed cannot be parsed."""
