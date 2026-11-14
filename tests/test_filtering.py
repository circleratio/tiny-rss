import unittest
from datetime import datetime, timezone

from rss_reader.filtering import filter_articles, matches_patterns, merge_articles, sort_articles
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

    def test_title_patterns_apply_only_to_their_feed(self):
        hit, miss, other = art("【週末レシピ】第1回", "u1"), art("新型CPU", "u2"), art("新型CPU", "u3")
        results = [
            FeedResult("f1", Feed("f1", "F1", [hit, miss]), None),
            FeedResult("f2", Feed("f2", "F2", [other]), None),
        ]
        self.assertEqual(merge_articles(results, {"f1": ("週末レシピ",)}), [hit, other])

    def test_excluded_link_survives_from_unfiltered_feed(self):
        a, b = art("other", "u1"), art("other", "u1")
        results = [
            FeedResult("f1", Feed("f1", "F1", [a]), None),
            FeedResult("f2", Feed("f2", "F2", [b]), None),
        ]
        merged = merge_articles(results, {"f1": ("series",), "f2": ()})
        self.assertEqual(len(merged), 1)
        self.assertIs(merged[0], b)


    def test_exclude_patterns_apply_only_to_their_feed(self):
        pr, ad, keep, other = art("【PR】新製品", "u1"), art("広告のお知らせ", "u2"), art("新型CPU", "u3"), art("PR特集", "u4")
        results = [
            FeedResult("f1", Feed("f1", "F1", [pr, ad, keep]), None),
            FeedResult("f2", Feed("f2", "F2", [other]), None),
        ]
        self.assertEqual(merge_articles(results, exclude_patterns={"f1": ("pr", "広告")}), [keep, other])

    def test_exclude_wins_over_title_patterns(self):
        hit, excluded, miss = art("週末レシピ 第1回", "u1"), art("週末レシピ PR版", "u2"), art("新型CPU", "u3")
        results = [FeedResult("f1", Feed("f1", "F1", [hit, excluded, miss]), None)]
        merged = merge_articles(results, {"f1": ("週末レシピ",)}, {"f1": ("PR",)})
        self.assertEqual(merged, [hit])

class MatchesPatternsTest(unittest.TestCase):
    def test_any_pattern_case_insensitive(self):
        self.assertTrue(matches_patterns("Hello World", ("xyz", "WORLD")))
        self.assertFalse(matches_patterns("Hello World", ("xyz", "abc")))

    def test_no_patterns_matches_everything(self):
        self.assertTrue(matches_patterns("anything", ()))


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
