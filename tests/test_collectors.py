import os
import urllib.error
import unittest
from unittest import mock

from comms_analyst_agent.collectors import (
    CollectionDiagnostics,
    collect_all,
    collect_linkedin,
    collect_rss_feeds,
    collect_threads,
    collect_x_posts,
)
from comms_analyst_agent.config import MonitoringConfig
from comms_analyst_agent.models import ContentItem


def _config(**overrides) -> MonitoringConfig:
    base = MonitoringConfig(
        target_name="Target",
        launch_name="Launch",
        github_terms=["Launch"],
        executive_names=[],
        hashtags=[],
        competitors=[],
        time_window_hours=24,
        rss_feeds=["https://example.com/feed.xml"],
        max_items_per_source=2,
        sources=["news", "rss", "reddit", "hackernews", "linkedin", "x", "threads"],
    )
    for key, value in overrides.items():
        setattr(base, key, value)
    return base


class CollectAllSelectionTests(unittest.TestCase):
    @mock.patch("comms_analyst_agent.collectors.collect_threads")
    @mock.patch("comms_analyst_agent.collectors.collect_linkedin")
    @mock.patch("comms_analyst_agent.collectors.collect_x_posts")
    @mock.patch("comms_analyst_agent.collectors.collect_rss_feeds")
    @mock.patch("comms_analyst_agent.collectors.collect_hacker_news")
    @mock.patch("comms_analyst_agent.collectors.collect_reddit")
    @mock.patch("comms_analyst_agent.collectors.collect_google_news")
    def test_collect_all_uses_enabled_sources(
        self,
        mock_news,
        mock_reddit,
        mock_hn,
        mock_rss,
        mock_x,
        mock_linkedin,
        mock_threads,
    ) -> None:
        mock_news.return_value = [ContentItem("n", "https://n", "News", None, None, "", "", "news", {})]
        mock_reddit.return_value = [ContentItem("r", "https://r", "Reddit", None, None, "", "", "reddit", {})]
        mock_hn.return_value = [ContentItem("h", "https://h", "HN", None, None, "", "", "hackernews", {})]
        mock_rss.return_value = [ContentItem("s", "https://s", "RSS", None, None, "", "", "rss", {})]
        mock_x.return_value = [ContentItem("x", "https://x", "X", None, None, "", "", "x", {})]
        mock_linkedin.return_value = [ContentItem("l", "https://l", "LinkedIn", None, None, "", "", "linkedin", {})]
        mock_threads.return_value = [ContentItem("t", "https://t", "Threads", None, None, "", "", "threads", {})]

        cfg = _config(sources=["linkedin", "reddit", "x", "threads"])
        items = collect_all(cfg)

        self.assertEqual({item.channel for item in items}, {"linkedin", "reddit", "x", "threads"})
        mock_news.assert_not_called()
        mock_rss.assert_not_called()
        mock_hn.assert_not_called()


class LinkedInCollectorTests(unittest.TestCase):
    def test_returns_empty_without_token(self) -> None:
        cfg = _config(sources=["linkedin"])
        with mock.patch.dict("os.environ", {}, clear=True):
            self.assertEqual(collect_linkedin(cfg), [])

    def test_maps_response_and_handles_rate_limit(self) -> None:
        cfg = _config(sources=["linkedin"], max_items_per_source=2)
        payload = {
            "elements": [
                {
                    "title": "Launch reactions",
                    "permalink": "https://www.linkedin.com/posts/1",
                    "authorName": "Author",
                    "created": {"time": "2026-01-01T00:00:00Z"},
                    "commentary": "Strong positive response.",
                    "engagement": {"reactionCount": 10, "commentaryCount": 3, "shareCount": 1},
                },
                {
                    "title": "Launch reactions 2",
                    "permalink": "https://www.linkedin.com/posts/2",
                    "authorName": "Author",
                    "created": {"time": "2026-01-01T00:05:00Z"},
                    "commentary": "Second page placeholder.",
                    "engagement": {"reactionCount": 5, "commentaryCount": 1, "shareCount": 0},
                },
            ]
        }
        rate_limit = urllib.error.HTTPError("https://api.linkedin.com/v2/posts", 429, "Too Many Requests", None, None)
        with (
            mock.patch.dict("os.environ", {"COMMS_LINKEDIN_ACCESS_TOKEN": "token"}, clear=True),
            mock.patch(
                "comms_analyst_agent.collectors._http_get_json",
                side_effect=[payload, rate_limit],
            ) as mock_get,
        ):
            items = collect_linkedin(cfg)

        self.assertEqual(len(items), 2)
        self.assertEqual(items[0].channel, "linkedin")
        self.assertEqual(items[0].source, "LinkedIn")
        self.assertEqual(items[0].engagement.get("reactions"), 10)
        self.assertGreaterEqual(mock_get.call_count, 1)


class XCollectorTests(unittest.TestCase):
    def test_returns_empty_without_token(self) -> None:
        cfg = _config(sources=["x"])
        with mock.patch.dict("os.environ", {}, clear=True):
            self.assertEqual(collect_x_posts(cfg), [])

    def test_maps_response_records(self) -> None:
        cfg = _config(sources=["x"], max_items_per_source=2)
        payload = {
            "data": [
                {
                    "id": "123",
                    "author_id": "a1",
                    "text": "Launch reactions on X",
                    "created_at": "2026-01-01T00:00:00Z",
                    "public_metrics": {"like_count": 5, "retweet_count": 2, "reply_count": 1, "quote_count": 0},
                }
            ],
            "includes": {"users": [{"id": "a1", "username": "authorx", "name": "Author X"}]},
        }
        with (
            mock.patch.dict("os.environ", {"COMMS_X_BEARER_TOKEN": "token"}, clear=True),
            mock.patch("comms_analyst_agent.collectors._http_get_json", return_value=payload),
        ):
            items = collect_x_posts(cfg)

        self.assertEqual(len(items), 1)
        self.assertEqual(items[0].channel, "x")
        self.assertIn("https://x.com/authorx/status/123", items[0].url)
        self.assertEqual(items[0].engagement.get("likes"), 5)


class ThreadsCollectorTests(unittest.TestCase):
    def test_returns_empty_without_token(self) -> None:
        cfg = _config(sources=["threads"])
        with mock.patch.dict("os.environ", {}, clear=True):
            self.assertEqual(collect_threads(cfg), [])

    def test_maps_response_records(self) -> None:
        cfg = _config(sources=["threads"], max_items_per_source=2)
        payload = {
            "data": [
                {
                    "id": "987",
                    "text": "Excited about the launch on Threads",
                    "permalink": "https://www.threads.net/@authort/post/abc",
                    "timestamp": "2026-02-01T00:00:00Z",
                    "username": "authort",
                    "media_type": "TEXT_POST",
                }
            ]
        }
        with (
            mock.patch.dict(
                "os.environ", {"COMMS_THREADS_ACCESS_TOKEN": "token"}, clear=True
            ),
            mock.patch(
                "comms_analyst_agent.collectors._http_get_json", return_value=payload
            ),
        ):
            items = collect_threads(cfg)

        self.assertEqual(len(items), 1)
        self.assertEqual(items[0].channel, "threads")
        self.assertEqual(items[0].source, "Threads")
        self.assertEqual(items[0].author, "@authort")
        self.assertEqual(items[0].url, "https://www.threads.net/@authort/post/abc")


class ArticleDomainFilterTests(unittest.TestCase):
    def test_rss_domain_allowlist_filters_items(self) -> None:
        cfg = _config(article_domains=["allowed.com"])
        xml_payload = """
        <rss><channel>
          <item><title>Launch arrives on allowed</title><link>https://allowed.com/post</link><description>Launch covered here</description></item>
          <item><title>Launch arrives on blocked</title><link>https://blocked.com/post</link><description>Launch covered here</description></item>
        </channel></rss>
        """
        with mock.patch("comms_analyst_agent.collectors._http_get_text", return_value=xml_payload):
            items = collect_rss_feeds(cfg)
        self.assertEqual(len(items), 1)
        self.assertIn("allowed.com", items[0].url)


class RssTopicFilterTests(unittest.TestCase):
    def test_rss_drops_items_unrelated_to_search_terms(self) -> None:
        cfg = _config(github_terms=["Copilot Pricing"])
        xml_payload = """
        <rss><channel>
          <item><title>Copilot Pricing changes announced</title><link>https://example.com/a</link><description>details</description></item>
          <item><title>Unrelated open source roundup</title><link>https://example.com/b</link><description>weekend reading</description></item>
        </channel></rss>
        """
        with mock.patch("comms_analyst_agent.collectors._http_get_text", return_value=xml_payload):
            items = collect_rss_feeds(cfg)
        self.assertEqual(len(items), 1)
        self.assertIn("/a", items[0].url)

    def test_rss_excludes_blocked_domains(self) -> None:
        cfg = _config(github_terms=["Launch"], exclude_domains=["github.blog"])
        xml_payload = """
        <rss><channel>
          <item><title>Launch update on github blog</title><link>https://github.blog/launch</link><description>announcement</description></item>
          <item><title>Launch update on neutral site</title><link>https://example.com/launch</link><description>announcement</description></item>
        </channel></rss>
        """
        with mock.patch("comms_analyst_agent.collectors._http_get_text", return_value=xml_payload):
            items = collect_rss_feeds(cfg)
        self.assertEqual(len(items), 1)
        self.assertIn("example.com", items[0].url)


class CollectionDiagnosticsTests(unittest.TestCase):
    def test_records_skipped_when_token_missing(self) -> None:
        cfg = _config(sources=["x", "linkedin", "threads"])
        diagnostics = CollectionDiagnostics()
        with mock.patch.dict("os.environ", {}, clear=True):
            items = collect_all(cfg, diagnostics=diagnostics)
        self.assertEqual(items, [])
        self.assertEqual(diagnostics.sources["x"].status, "skipped")
        self.assertIn("COMMS_X_BEARER_TOKEN", diagnostics.sources["x"].reason)
        self.assertEqual(diagnostics.sources["linkedin"].status, "skipped")
        self.assertEqual(diagnostics.sources["threads"].status, "skipped")

    def test_records_ok_status_for_successful_collector(self) -> None:
        cfg = _config(github_terms=["Launch"])
        xml_payload = """
        <rss><channel>
          <item><title>Launch update</title><link>https://example.com/a</link><description>Launch covered</description></item>
        </channel></rss>
        """
        diagnostics = CollectionDiagnostics()
        with mock.patch("comms_analyst_agent.collectors._http_get_text", return_value=xml_payload):
            collect_rss_feeds(cfg, diagnostics=diagnostics)
        self.assertEqual(diagnostics.sources["rss"].status, "ok")
        self.assertEqual(diagnostics.sources["rss"].count, 1)

    def test_records_error_status_when_http_fails(self) -> None:
        cfg = _config(github_terms=["Launch"])
        diagnostics = CollectionDiagnostics()
        http_error = urllib.error.HTTPError(
            "https://example.com/feed", 503, "Service Unavailable", None, None
        )
        with mock.patch(
            "comms_analyst_agent.collectors._http_get_text", side_effect=http_error
        ):
            items = collect_rss_feeds(cfg, diagnostics=diagnostics)
        self.assertEqual(items, [])
        self.assertEqual(diagnostics.sources["rss"].status, "error")
        self.assertIn("503", diagnostics.sources["rss"].reason)


if __name__ == "__main__":
    unittest.main()
