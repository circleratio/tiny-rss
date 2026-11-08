"""Parsing of RSS 2.0 / RSS 1.0 (RDF) / Atom feeds."""

from __future__ import annotations

import codecs
import html
import re
import xml.etree.ElementTree as ET
from datetime import datetime, timezone
from email.utils import parsedate_to_datetime
from urllib.parse import urljoin, urlparse

from .models import Article, Feed, FeedParseError

NS = {
    "rdf": "http://www.w3.org/1999/02/22-rdf-syntax-ns#",
    "rss1": "http://purl.org/rss/1.0/",
    "atom": "http://www.w3.org/2005/Atom",
    "dc": "http://purl.org/dc/elements/1.1/",
}

UNTITLED = "(無題)"

_WS_RE = re.compile(r"\s+")
_DECL_RE = re.compile(rb"""^\s*<\?xml[^>]*?(\s+encoding\s*=\s*["']([A-Za-z0-9._-]+)["'])""")
# Encodings supported natively by expat (normalized codec names)
_EXPAT_CODECS = {"utf-8", "utf-16", "utf-16-le", "utf-16-be", "ascii", "latin-1", "iso8859-1"}


def parse_feed(data: bytes, url: str) -> Feed:
    """Parse feed XML *data* fetched from *url*."""
    try:
        root = ET.fromstring(_to_expat_encoding(data))
    except ET.ParseError as e:
        raise FeedParseError(f"XMLを解析できません: {e}") from None

    if root.tag == "rss":
        title, items = _parse_rss2(root, url)
    elif root.tag == f"{{{NS['rdf']}}}RDF":
        title, items = _parse_rss1(root, url)
    elif root.tag == f"{{{NS['atom']}}}feed":
        title, items = _parse_atom(root, url)
    else:
        raise FeedParseError("未対応のフィード形式です")

    feed_title = title or urlparse(url).hostname or url
    articles = [
        Article(title=t, link=link, published=pub, feed_title=feed_title)
        for t, link, pub in items
        if link
    ]
    return Feed(url=url, title=feed_title, articles=articles)


def parse_date(text: str | None) -> datetime | None:
    """Parse an RFC 822 or ISO 8601 date string into an aware UTC datetime."""
    if not text:
        return None
    text = text.strip()
    dt: datetime | None = None
    try:
        dt = parsedate_to_datetime(text)
    except (TypeError, ValueError, IndexError):
        pass
    if dt is None:
        iso = text[:-1] + "+00:00" if text.endswith(("Z", "z")) else text
        try:
            dt = datetime.fromisoformat(iso)
        except ValueError:
            return None
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    return dt.astimezone(timezone.utc)


def _to_expat_encoding(data: bytes) -> bytes:
    """Re-encode documents in encodings expat cannot handle (e.g. Shift_JIS) to UTF-8."""
    m = _DECL_RE.match(data)
    if m is None:
        return data
    name = m.group(2).decode("ascii")
    try:
        codec = codecs.lookup(name).name
    except LookupError:
        raise FeedParseError(f"未対応の文字コードです: {name}") from None
    if codec in _EXPAT_CODECS:
        return data
    try:
        text = data.decode(codec, errors="replace")
    except UnicodeError as e:
        raise FeedParseError(f"文字コードを変換できません: {e}") from None
    # Drop the encoding pseudo-attribute so expat treats the document as UTF-8
    text = text[: m.start(1)] + text[m.end(1):]
    return text.encode("utf-8")


def _clean_title(text: str | None) -> str:
    return _WS_RE.sub(" ", html.unescape(text or "")).strip()


def _text(elem: ET.Element | None) -> str:
    if elem is None:
        return ""
    return "".join(elem.itertext()).strip()


def _abs_link(base: str, link: str) -> str:
    link = link.strip()
    return urljoin(base, link) if link else ""


def _parse_rss2(root: ET.Element, url: str):
    channel = root.find("channel")
    if channel is None:
        raise FeedParseError("channel 要素がありません")
    items = []
    for item in channel.findall("item"):
        date_text = _text(item.find("pubDate")) or _text(item.find("dc:date", NS))
        items.append((
            _clean_title(_text(item.find("title"))) or UNTITLED,
            _abs_link(url, _text(item.find("link"))),
            parse_date(date_text),
        ))
    return _clean_title(_text(channel.find("title"))), items


def _parse_rss1(root: ET.Element, url: str):
    channel = root.find("rss1:channel", NS)
    items = []
    for item in root.findall("rss1:item", NS):
        items.append((
            _clean_title(_text(item.find("rss1:title", NS))) or UNTITLED,
            _abs_link(url, _text(item.find("rss1:link", NS))),
            parse_date(_text(item.find("dc:date", NS))),
        ))
    return _clean_title(_text(channel.find("rss1:title", NS) if channel is not None else None)), items


def _atom_link(entry: ET.Element, base: str) -> str:
    # rel defaults to "alternate" when omitted (RFC 4287)
    for link in entry.findall("atom:link", NS):
        href = link.get("href", "")
        if link.get("rel", "alternate") == "alternate" and href:
            return _abs_link(base, href)
    return ""


def _parse_atom(root: ET.Element, url: str):
    items = []
    for entry in root.findall("atom:entry", NS):
        date_text = _text(entry.find("atom:published", NS)) or _text(entry.find("atom:updated", NS))
        items.append((
            _clean_title(_text(entry.find("atom:title", NS))) or UNTITLED,
            _atom_link(entry, url),
            parse_date(date_text),
        ))
    return _clean_title(_text(root.find("atom:title", NS))), items
