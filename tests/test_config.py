import tempfile
import unittest
from pathlib import Path

from rss_reader.config import load_feed_urls
from rss_reader.models import ConfigError


class LoadFeedUrlsTest(unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.dir = Path(self._tmp.name)
        self.path = self.dir / "feeds.txt"

    def tearDown(self):
        self._tmp.cleanup()

    def write(self, text: str, encoding: str = "utf-8"):
        self.path.write_text(text, encoding=encoding)

    def test_skips_comments_blanks_and_strips(self):
        self.write("# comment\n\n  https://a.example/rss  \n\t\nhttp://b.example/feed\n")
        self.assertEqual(load_feed_urls(self.path), ["https://a.example/rss", "http://b.example/feed"])

    def test_bom(self):
        self.write("https://a.example/rss\n", encoding="utf-8-sig")
        self.assertEqual(load_feed_urls(self.path), ["https://a.example/rss"])

    def test_ignores_non_http_lines(self):
        self.write("ftp://x.example/\nnot a url\nhttps://a.example/rss\n")
        with self.assertLogs("rss_reader.config", level="WARNING"):
            self.assertEqual(load_feed_urls(self.path), ["https://a.example/rss"])

    def test_removes_duplicates_keeping_order(self):
        self.write("https://b.example/\nhttps://a.example/\nhttps://b.example/\n")
        self.assertEqual(load_feed_urls(self.path), ["https://b.example/", "https://a.example/"])

    def test_missing_file(self):
        with self.assertRaises(ConfigError) as cm:
            load_feed_urls(self.path)
        self.assertIn("feeds.txt が見つかりません", str(cm.exception))

    def test_no_valid_urls(self):
        self.write("# only comments\n\n")
        self.assertEqual(load_feed_urls(self.path), [])


if __name__ == "__main__":
    unittest.main()
