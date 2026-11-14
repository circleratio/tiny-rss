import tempfile
import unittest
from pathlib import Path

from rss_reader.config import UNCATEGORIZED, load_categories, unique_urls
from rss_reader.models import Category, ConfigError, FeedConfig


def load_feeds(path):
    """Feeds of all categories, flattened in order."""
    return [f for c in load_categories(path) for f in c.feeds]


def urls(path):
    return [f.url for f in load_feeds(path)]


def names(path):
    return [c.name for c in load_categories(path)]


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
            load_categories(self.path)
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
        self.assertEqual(names(example), ["ニュース", "趣味"])
        feeds = load_feeds(example)
        self.assertEqual(len(feeds), 4)
        self.assertTrue(all(f.title_patterns == () and f.exclude_patterns == () for f in feeds))


class CategoriesTest(unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.path = Path(self._tmp.name) / "feeds.txt"

    def tearDown(self):
        self._tmp.cleanup()

    def write(self, text: str):
        self.path.write_text(text, encoding="utf-8")

    def test_headers_split_categories(self):
        self.write(
            "# 技術ニュース\n"
            "https://a.example/\n"
            "https://b.example/\n"
            "\n"
            "##  サブカル  \n"
            "https://c.example/\n"
        )
        self.assertEqual(
            load_categories(self.path),
            [
                Category("技術ニュース", (FeedConfig("https://a.example/"), FeedConfig("https://b.example/"))),
                Category("サブカル", (FeedConfig("https://c.example/"),)),
            ],
        )

    def test_categories_without_urls_are_dropped(self):
        self.write("# 説明のコメント\n# もう1行\n# ニュース\nhttps://a.example/\n# 空の分類\n")
        self.assertEqual(names(self.path), ["ニュース"])

    def test_bare_hash_is_not_a_header(self):
        self.write("# ニュース\n#\n#   \nhttps://a.example/\n")
        self.assertEqual(names(self.path), ["ニュース"])

    def test_indented_hash_is_a_comment(self):
        self.write("# ニュース\nhttps://a.example/\n    # メモ\n    title:x\nhttps://b.example/\n")
        self.assertEqual(
            load_categories(self.path),
            [Category("ニュース", (FeedConfig("https://a.example/", ("x",)), FeedConfig("https://b.example/")))],
        )

    def test_same_name_categories_are_merged_at_first_position(self):
        self.write("# A\n# B\nhttps://b.example/\n# A\nhttps://a.example/\n# B\nhttps://c.example/\n")
        self.assertEqual(
            load_categories(self.path),
            [
                Category("A", (FeedConfig("https://a.example/"),)),
                Category("B", (FeedConfig("https://b.example/"), FeedConfig("https://c.example/"))),
            ],
        )

    def test_urls_before_first_header_are_uncategorized_and_first(self):
        self.write("https://a.example/\n# ニュース\nhttps://b.example/\n")
        self.assertEqual(names(self.path), [UNCATEGORIZED, "ニュース"])
        self.assertEqual(load_categories(self.path)[0].feeds, (FeedConfig("https://a.example/"),))

    def test_no_headers_means_single_uncategorized(self):
        self.write("https://a.example/\nhttps://b.example/\n")
        self.assertEqual(names(self.path), [UNCATEGORIZED])

    def test_same_url_in_two_categories_keeps_each_patterns(self):
        self.write(
            "# A\nhttps://x.example/\n  !title:PR\n"
            "# B\nhttps://x.example/\n  title:連載\n"
        )
        self.assertEqual(
            load_categories(self.path),
            [
                Category("A", (FeedConfig("https://x.example/", (), ("PR",)),)),
                Category("B", (FeedConfig("https://x.example/", ("連載",)),)),
            ],
        )

    def test_duplicate_url_within_category_is_ignored(self):
        self.write("# A\nhttps://x.example/\nhttps://y.example/\nhttps://x.example/\n  title:z\n")
        self.assertEqual(
            load_categories(self.path),
            [Category("A", (FeedConfig("https://x.example/"), FeedConfig("https://y.example/")))],
        )

    def test_indented_line_right_after_header_is_ignored(self):
        self.write("https://a.example/\n# B\n  title:x\nhttps://b.example/\n")
        with self.assertLogs("rss_reader.config", level="WARNING"):
            categories = load_categories(self.path)
        self.assertEqual(
            categories,
            [
                Category(UNCATEGORIZED, (FeedConfig("https://a.example/"),)),
                Category("B", (FeedConfig("https://b.example/"),)),
            ],
        )

    def test_unique_urls(self):
        self.write("# A\nhttps://x.example/\nhttps://y.example/\n# B\nhttps://z.example/\nhttps://x.example/\n")
        self.assertEqual(
            unique_urls(load_categories(self.path)),
            ["https://x.example/", "https://y.example/", "https://z.example/"],
        )


if __name__ == "__main__":
    unittest.main()
