import unittest
from datetime import datetime, timezone

from rss_reader.filtering import filter_articles, merge_articles, sort_articles
from rss_reader.models import Article, Feed, FeedResult


def art(title, link, day=None):
    published = datetime(2026, 11, day, tzinfo=timezone.utc) if day else None
    return Article(title=title, link=link, published=published, feed_title="F")


class MergeTest(unittest.TestCase):
    def test_skips_failed_and_duplicate_links(self):
        a1, a2, dup = art("A", "u1"), art("B", "u2"), art("A again", "u1")
        results = [
            FeedResult("f1", Feed("f1", "F1", [a1, a2]), None),
            FeedResult("f2", None, "HTTP 500"),
            FeedResult("f3", Feed("f3", "F3", [dup]), None),
        ]
        self.assertEqual(merge_articles(results), [a1, a2])


class SortTest(unittest.TestCase):
    def test_newest_first_and_undated_last(self):
        n1, old, n2, new = art("n1", "1"), art("old", "2", 1), art("n2", "3"), art("new", "4", 8)
        self.assertEqual(sort_articles([n1, old, n2, new]), [new, old, n1, n2])


class FilterTest(unittest.TestCase):
    def setUp(self):
        self.articles = [art("新型CPU発表", "1"), art("cpu benchmark", "2"), art("クラウド", "3")]
        self.read = {"2"}

    def run_filter(self, query, unread_only=False):
        return [a.link for a in filter_articles(self.articles, query, unread_only, self.read.__contains__)]

    def test_case_insensitive_substring(self):
        self.assertEqual(self.run_filter("Cpu"), ["1", "2"])

    def test_query_is_stripped(self):
        self.assertEqual(self.run_filter("  クラウド "), ["3"])

    def test_empty_query_returns_all(self):
        self.assertEqual(self.run_filter(""), ["1", "2", "3"])

    def test_unread_only(self):
        self.assertEqual(self.run_filter("", unread_only=True), ["1", "3"])

    def test_query_and_unread_only(self):
        self.assertEqual(self.run_filter("cpu", unread_only=True), ["1"])

    def test_no_match(self):
        self.assertEqual(self.run_filter("zzz"), [])


if __name__ == "__main__":
    unittest.main()
