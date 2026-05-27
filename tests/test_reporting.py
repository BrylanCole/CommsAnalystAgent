import unittest

from comms_analyst_agent.analysis import analyze_items
from comms_analyst_agent.config import MonitoringConfig
from comms_analyst_agent.models import ContentItem
from comms_analyst_agent.reporting import build_markdown_report, build_slack_summary


class ReportingTests(unittest.TestCase):
    def test_report_contains_required_sections(self) -> None:
        config = MonitoringConfig(
            target_name="Target",
            launch_name="Launch",
            github_terms=["GitHub"],
            executive_names=[],
            hashtags=[],
            competitors=[],
            time_window_hours=24,
            rss_feeds=[],
            max_items_per_source=5,
        )
        items = [
            ContentItem(
                title="GitHub announced update",
                url="https://example.com/post",
                source="Example News",
                author="author",
                published_at="2026-01-01",
                snippet="announced",
                content="announced update",
                channel="news",
                engagement={},
            )
        ]
        analysis = analyze_items(items, config)
        report = build_markdown_report(config, analysis)

        self.assertIn("# Target — Deep Sentiment Analysis", report)
        self.assertIn("## Executive Summary", report)
        self.assertIn("## Social Performance", report)
        self.assertIn("## Overall Sentiment:", report)
        self.assertIn("## Key Amplifiers", report)
        self.assertIn("## Top Risks & Mitigations", report)
        self.assertIn("## Sources Analyzed", report)

    def test_slack_summary_contains_key_sections(self) -> None:
        config = MonitoringConfig(
            target_name="Target",
            launch_name="Launch",
            github_terms=["GitHub"],
            executive_names=[],
            hashtags=[],
            competitors=["Cursor"],
            time_window_hours=24,
            rss_feeds=[],
            max_items_per_source=5,
        )
        items = [
            ContentItem(
                title="Pricing concern is growing",
                url="https://www.reddit.com/r/test/post",
                source="r/Test",
                author="author",
                published_at="2026-01-01",
                snippet="users worry about cost and value",
                content="users worry about cost and value versus Cursor",
                channel="reddit",
                engagement={"score": 25, "num_comments": 9},
            ),
            ContentItem(
                title="Developers compare update versus Cursor",
                url="https://news.ycombinator.com/item?id=1",
                source="Hacker News",
                author="author",
                published_at="2026-01-01",
                snippet="discussion about value tradeoff",
                content="pricing and value discussion compared to Cursor",
                channel="hackernews",
                engagement={"points": 42},
            ),
            ContentItem(
                title="Professionals discuss launch impact",
                url="https://www.linkedin.com/posts/example",
                source="LinkedIn",
                author="author",
                published_at="2026-01-01",
                snippet="discussion in industry circles",
                content="industry professionals discuss launch impact and positioning",
                channel="linkedin",
                engagement={"reactions": 14},
            ),
        ]
        analysis = analyze_items(items, config)
        summary = build_slack_summary(config, analysis)

        self.assertIn("*Target — Deep Sentiment Analysis*", summary)
        self.assertIn("*Coverage Totals*", summary)
        self.assertIn("Total # of articles:", summary)
        self.assertIn("Total # of posts:", summary)
        self.assertIn("*Top Headlines*", summary)
        self.assertIn("Majority sentiment:", summary)
        self.assertIn("*Key Themes / Messages*", summary)
        self.assertIn("*Top News Mentioned*", summary)
        self.assertIn("*Competitor Mentions / Comparisons*", summary)
        self.assertIn("*Direct Social Post Links*", summary)


if __name__ == "__main__":
    unittest.main()
