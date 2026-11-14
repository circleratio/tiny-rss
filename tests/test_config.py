import tempfile
import unittest
from pathlib import Path

from rss_reader.config import load_feeds
from rss_reader.models import ConfigError, FeedConfig


def urls(path):
    return [f.url for f in load_feeds(path)]


class LoadFeedsTest(unittest.TestCase):
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
        self.assertEqual(urls(self.path), ["https://a.example/rss", "http://b.example/feed"])

    def test_bom(self):
        self.write("https://a.example/rss\n", encoding="utf-8-sig")
        self.assertEqual(urls(self.path), ["https://a.example/rss"])

    def test_ignores_non_http_lines(self):
        self.write("ftp://x.example/\nnot a url\nhttps://a.example/rss\n")
        with self.assertLogs("rss_reader.config", level="WARNING"):
            self.assertEqual(urls(self.path), ["https://a.example/rss"])

    def test_removes_duplicates_keeping_order(self):
        self.write("https://b.example/\nhttps://a.example/\nhttps://b.example/\n")
        self.assertEqual(urls(self.path), ["https://b.example/", "https://a.example/"])

    def test_missing_file(self):
        with self.assertRaises(ConfigError) as cm:
            load_feeds(self.path)
        self.assertIn("feeds.txt が見つかりません", str(cm.exception))
        self.assertIn("feeds.example.txt", str(cm.exception))

    def test_no_valid_urls(self):
        self.write("# only comments\n\n")
        self.assertEqual(urls(self.path), [])

    def test_title_patterns(self):
        self.write(
            "https://a.example/rss\n"
            "    title:週末レシピ\n"
            "\tTITLE:  Second Series  \n"
            "https://b.example/rss\n"
        )
        self.assertEqual(
            load_feeds(self.path),
            [
                FeedConfig("https://a.example/rss", ("週末レシピ", "Second Series")),
                FeedConfig("https://b.example/rss", ()),
            ],
        )

    def test_patterns_belong_to_preceding_url_only(self):
        self.write("https://a.example/\nhttps://b.example/\n  title:x\n")
        self.assertEqual(
            load_feeds(self.path),
            [FeedConfig("https://a.example/", ()), FeedConfig("https://b.example/", ("x",))],
        )

    def test_ignores_invalid_indented_lines(self):
        self.write(
            "  title:orphan\n"
            "https://a.example/\n"
            "  keyword:foo\n"
            "  title:   \n"
            "  # title:commented\n"
            "  title:ok\n"
        )
        with self.assertLogs("rss_reader.config", level="WARNING") as cm:
            feeds = load_feeds(self.path)
        self.assertEqual(feeds, [FeedConfig("https://a.example/", ("ok",))])
        self.assertEqual(len(cm.output), 3)

    def test_indented_lines_after_non_url_line_are_ignored(self):
        self.write("https://a.example/\nnot a url\n  title:x\n")
        with self.assertLogs("rss_reader.config", level="WARNING"):
            self.assertEqual(load_feeds(self.path), [FeedConfig("https://a.example/", ())])

    def test_patterns_of_duplicate_url_are_ignored(self):
        self.write("https://a.example/\nhttps://a.example/\n  title:x\n")
        self.assertEqual(load_feeds(self.path), [FeedConfig("https://a.example/", ())])

    def test_exclude_patterns(self):
        self.write(
            "https://a.example/rss\n"
            "    !title:PR\n"
            "\t!TITLE:  広告  \n"
            "    title:週末レシピ\n"
            "https://b.example/rss\n"
        )
        self.assertEqual(
            load_feeds(self.path),
            [
                FeedConfig("https://a.example/rss", ("週末レシピ",), ("PR", "広告")),
                FeedConfig("https://b.example/rss", (), ()),
            ],
        )

    def test_ignores_invalid_exclude_lines(self):
        self.write(
            "  !title:orphan\n"
            "https://a.example/\n"
            "  !title:   \n"
            "  ! title:spaced\n"
            "  !keyword:foo\n"
            "  !title:ok\n"
        )
        with self.assertLogs("rss_reader.config", level="WARNING") as cm:
            feeds = load_feeds(self.path)
        self.assertEqual(feeds, [FeedConfig("https://a.example/", (), ("ok",))])
        self.assertEqual(len(cm.output), 4)

    def test_example_file_has_no_active_patterns(self):
        example = Path(__file__).resolve().parent.parent / "feeds.example.txt"
        feeds = load_feeds(example)
        self.assertEqual(len(feeds), 2)
        self.assertTrue(all(f.title_patterns == () and f.exclude_patterns == () for f in feeds))


if __name__ == "__main__":
    unittest.main()
