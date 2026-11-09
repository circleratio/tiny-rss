"""Merging, sorting and filtering of articles."""

from __future__ import annotations

from collections.abc import Callable, Mapping, Sequence

from .models import Article, FeedResult


def merge_articles(
    results: list[FeedResult],
    title_patterns: Mapping[str, Sequence[str]] | None = None,
) -> list[Article]:
    """Concatenate articles of successful feeds, dropping duplicate links.

    Articles of a feed with title patterns are kept only if they match one.
    """
    title_patterns = title_patterns or {}
    seen: set[str] = set()
    merged: list[Article] = []
    for result in results:
        if result.feed is None:
            continue
        patterns = title_patterns.get(result.url, ())
        for article in result.feed.articles:
            if not matches_patterns(article.title, patterns):
                continue
            if article.link in seen:
                continue
            seen.add(article.link)
            merged.append(article)
    return merged


def matches_patterns(title: str, patterns: Sequence[str]) -> bool:
    """True if *title* contains any of *patterns* (case-insensitive), or none are given."""
    if not patterns:
        return True
    folded = title.casefold()
    return any(p.casefold() in folded for p in patterns)


def sort_articles(articles: list[Article]) -> list[Article]:
    """Sort newest first; articles without a date go last in original order."""
    dated = [a for a in articles if a.published is not None]
    undated = [a for a in articles if a.published is None]
    dated.sort(key=lambda a: a.published, reverse=True)
    return dated + undated


def filter_articles(
    articles: list[Article],
    query: str,
    unread_only: bool,
    is_read: Callable[[str], bool],
) -> list[Article]:
    """Keep articles whose title contains *query* (case-insensitive)."""
    needle = query.strip().casefold()
    return [
        a
        for a in articles
        if (not needle or needle in a.title.casefold())
        and not (unread_only and is_read(a.link))
    ]
