import unittest
from datetime import datetime, timezone
from pathlib import Path

from rss_reader.models import FeedParseError
from rss_reader.parser import UNTITLED, parse_date, parse_feed

FIXTURES = Path(__file__).parent / "fixtures"


def load(name: str, url: str):
    return parse_feed((FIXTURES / name).read_bytes(), url)


def utc(*args):
    return datetime(*args, tzinfo=timezone.utc)


class ParseRss2Test(unittest.TestCase):
    def setUp(self):
        self.feed = load("rss2.xml", "https://example.com/rss")

    def test_feed_title(self):
        self.assertEqual(self.feed.title, "Sample RSS2")

    def test_articles_without_link_are_dropped(self):
        self.assertEqual(
            [a.link for a in self.feed.articles],
            ["https://example.com/a1", "https://example.com/a2", "https://example.com/a3",
             "https://example.com/a5"],
        )

    def test_title_unescaped_and_whitespace_collapsed(self):
        self.assertEqual(self.feed.articles[0].title, "新型CPU & GPU 発表")

    def test_untitled(self):
        self.assertEqual(self.feed.articles[3].title, UNTITLED)

    def test_dates(self):
        a = self.feed.articles
        self.assertEqual(a[0].published, utc(2026, 11, 8, 3, 30))
        self.assertEqual(a[1].published, utc(2026, 11, 7, 10, 0))  # dc:date fallback
        self.assertIsNone(a[2].published)

    def test_feed_title_on_articles(self):
        self.assertTrue(all(a.feed_title == "Sample RSS2" for a in self.feed.articles))


class ParseRss1Test(unittest.TestCase):
    def test_shift_jis_rdf(self):
        feed = load("rss1.rdf", "https://example.jp/index.rdf")
        self.assertEqual(feed.title, "サンプルRDF")
        self.assertEqual([a.title for a in feed.articles], ["記事その1", "記事その2"])
        self.assertEqual(feed.articles[0].link, "https://example.jp/r1")
        self.assertEqual(feed.articles[0].published, utc(2026, 11, 8, 0, 0))
        self.assertIsNone(feed.articles[1].published)


class ParseEncodingTest(unittest.TestCase):
    def test_euc_jp(self):
        xml = ('<?xml version="1.0" encoding="EUC-JP"?>\n'
               '<rss version="2.0"><channel><title>日本語</title>'
               '<item><title>記事</title><link>https://e.example/1</link></item>'
               '</channel></rss>')
        feed = parse_feed(xml.encode("euc_jp"), "https://e.example/rss")
        self.assertEqual(feed.title, "日本語")
        self.assertEqual(feed.articles[0].title, "記事")

    def test_unknown_encoding(self):
        data = b'<?xml version="1.0" encoding="x-no-such"?><rss/>'
        with self.assertRaises(FeedParseError):
            parse_feed(data, "https://e.example/rss")


class ParseAtomTest(unittest.TestCase):
    def setUp(self):
        self.feed = load("atom.xml", "https://example.org/feed.atom")

    def test_feed_title(self):
        self.assertEqual(self.feed.title, "Sample Atom")

    def test_alternate_link_resolved_to_absolute(self):
        self.assertEqual(self.feed.articles[0].link, "https://example.org/posts/1")

    def test_link_without_rel_is_alternate(self):
        self.assertEqual(self.feed.articles[1].link, "https://example.org/posts/2")

    def test_entry_with_only_self_link_is_dropped(self):
        self.assertEqual(len(self.feed.articles), 2)

    def test_html_title(self):
        self.assertEqual(self.feed.articles[0].title, "Atom <entry> one")

    def test_published_preferred_over_updated(self):
        self.assertEqual(self.feed.articles[0].published, utc(2026, 11, 8, 1, 2, 3))
        self.assertEqual(self.feed.articles[1].published, utc(2026, 11, 6))


class ParseErrorTest(unittest.TestCase):
    def test_broken_xml(self):
        with self.assertRaises(FeedParseError):
            load("broken.xml", "https://example.com/")

    def test_unknown_root(self):
        with self.assertRaises(FeedParseError) as cm:
            load("unknown_root.xml", "https://example.com/")
        self.assertIn("未対応", str(cm.exception))

    def test_missing_feed_title_uses_hostname(self):
        data = b'<rss version="2.0"><channel><item><link>https://h.example/1</link></item></channel></rss>'
        feed = parse_feed(data, "https://h.example/rss")
        self.assertEqual(feed.title, "h.example")


class ParseDateTest(unittest.TestCase):
    def test_rfc822_with_offset(self):
        self.assertEqual(parse_date("Sun, 08 Nov 2026 12:30:00 +0900"), utc(2026, 11, 8, 3, 30))

    def test_rfc822_gmt(self):
        self.assertEqual(parse_date("Sun, 08 Nov 2026 12:30:00 GMT"), utc(2026, 11, 8, 12, 30))

    def test_rfc822_without_zone_assumes_utc(self):
        self.assertEqual(parse_date("Sun, 08 Nov 2026 12:30:00 -0000"), utc(2026, 11, 8, 12, 30))

    def test_iso_z(self):
        self.assertEqual(parse_date("2026-11-08T01:02:03Z"), utc(2026, 11, 8, 1, 2, 3))

    def test_iso_offset(self):
        self.assertEqual(parse_date("2026-11-08T09:00:00+09:00"), utc(2026, 11, 8))

    def test_iso_date_only(self):
        self.assertEqual(parse_date("2026-11-08"), utc(2026, 11, 8))

    def test_invalid(self):
        self.assertIsNone(parse_date("yesterday"))
        self.assertIsNone(parse_date(""))
        self.assertIsNone(parse_date(None))


if __name__ == "__main__":
    unittest.main()
