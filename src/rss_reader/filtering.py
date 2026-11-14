"""Merging, sorting and filtering of articles."""

from __future__ import annotations

from collections.abc import Callable, Mapping, Sequence

from .models import Article, Category, FeedResult


def merge_articles(
    results: list[FeedResult],
    title_patterns: Mapping[str, Sequence[str]] | None = None,
    exclude_patterns: Mapping[str, Sequence[str]] | None = None,
) -> list[Article]:
    """Concatenate articles of successful feeds, dropping duplicate links.

    Articles of a feed with title patterns are kept only if they match one,
    and articles matching any of the feed's exclude patterns are dropped.
    """
    title_patterns = title_patterns or {}
    exclude_patterns = exclude_patterns or {}
    seen: set[str] = set()
    merged: list[Article] = []
    for result in results:
        if result.feed is None:
            continue
        patterns = title_patterns.get(result.url, ())
        excludes = exclude_patterns.get(result.url, ())
        for article in result.feed.articles:
            if not matches_patterns(article.title, patterns):
                continue
            if excludes and matches_patterns(article.title, excludes):
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


def articles_by_category(
    categories: list[Category], results: list[FeedResult]
) -> list[tuple[str, list[Article]]]:
    """Return ``(category name, sorted articles)`` for each category, in order.

    Each category uses its own feeds' patterns, so a URL listed in two
    categories may show different articles in each.
    """
    by_url = {r.url: r for r in results}
    tabs: list[tuple[str, list[Article]]] = []
    for category in categories:
        feeds = [f for f in category.feeds if f.url in by_url]
        merged = merge_articles(
            [by_url[f.url] for f in feeds],
            {f.url: f.title_patterns for f in feeds},
            {f.url: f.exclude_patterns for f in feeds},
        )
        tabs.append((category.name, sort_articles(merged)))
    return tabs
