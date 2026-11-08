import io
import unittest
import urllib.error
from pathlib import Path
from unittest import mock

from rss_reader import fetcher
from rss_reader.models import FeedFetchError

FIXTURES = Path(__file__).parent / "fixtures"


class FakeResponse(io.BytesIO):
    def __enter__(self):
        return self

    def __exit__(self, *exc):
        self.close()


class FetchTest(unittest.TestCase):
    def test_returns_body_and_sends_user_agent(self):
        with mock.patch("urllib.request.urlopen", return_value=FakeResponse(b"<rss/>")) as m:
            self.assertEqual(fetcher.fetch("https://a.example/"), b"<rss/>")
        req = m.call_args.args[0]
        self.assertEqual(req.get_header("User-agent"), fetcher.USER_AGENT)

    def assert_fetch_error(self, exc, expected):
        with mock.patch("urllib.request.urlopen", side_effect=exc):
            with self.assertRaises(FeedFetchError) as cm:
                fetcher.fetch("https://a.example/")
        self.assertIn(expected, str(cm.exception))

    def test_http_error(self):
        err = urllib.error.HTTPError("https://a.example/", 404, "Not Found", {}, None)
        self.assert_fetch_error(err, "HTTP 404")

    def test_url_error(self):
        self.assert_fetch_error(urllib.error.URLError("name resolution failed"), "接続できません")

    def test_timeout(self):
        self.assert_fetch_error(TimeoutError(), "タイムアウト")

    def test_timeout_wrapped_in_url_error(self):
        self.assert_fetch_error(urllib.error.URLError(TimeoutError()), "タイムアウト")


class FetchAllTest(unittest.TestCase):
    def test_partial_failure_keeps_order(self):
        rss = (FIXTURES / "rss2.xml").read_bytes()
        broken = (FIXTURES / "broken.xml").read_bytes()

        def fake_fetch(url, timeout=fetcher.TIMEOUT_SEC):
            if url.endswith("/ng"):
                raise FeedFetchError("HTTP 500")
            if url.endswith("/broken"):
                return broken
            return rss

        urls = ["https://a.example/ok", "https://a.example/ng", "https://a.example/broken"]
        with mock.patch.object(fetcher, "fetch", side_effect=fake_fetch):
            results = fetcher.fetch_all(urls)

        self.assertEqual([r.url for r in results], urls)
        self.assertIsNone(results[0].error)
        self.assertEqual(results[0].feed.title, "Sample RSS2")
        self.assertEqual(results[1].error, "HTTP 500")
        self.assertIsNone(results[1].feed)
        self.assertIsNotNone(results[2].error)

    def test_empty(self):
        self.assertEqual(fetcher.fetch_all([]), [])


if __name__ == "__main__":
    unittest.main()
