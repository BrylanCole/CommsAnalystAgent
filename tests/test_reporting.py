import unittest

from comms_analyst_agent.analysis import analyze_items
from comms_analyst_agent.config import MonitoringConfig
from comms_analyst_agent.models import ContentItem
from comms_analyst_agent.reporting import build_markdown_report


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

        self.assertIn("## Executive Summary", report)
        self.assertIn("## Sentiment Snapshot", report)
        self.assertIn("## Media Coverage Summary", report)
        self.assertIn("## Sources / Evidence", report)


if __name__ == "__main__":
    unittest.main()
