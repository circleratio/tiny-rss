"""Merging, sorting and filtering of articles."""

from __future__ import annotations

from collections.abc import Callable

from .models import Article, FeedResult


def merge_articles(results: list[FeedResult]) -> list[Article]:
    """Concatenate articles of successful feeds, dropping duplicate links."""
    seen: set[str] = set()
    merged: list[Article] = []
    for result in results:
        if result.feed is None:
            continue
        for article in result.feed.articles:
            if article.link in seen:
                continue
            seen.add(article.link)
            merged.append(article)
    return merged


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
