import unittest

from comms_analyst_agent.analysis import analyze_items, classify_item
from comms_analyst_agent.config import MonitoringConfig
from comms_analyst_agent.models import ContentItem


class AnalysisTests(unittest.TestCase):
    def setUp(self) -> None:
        self.config = MonitoringConfig(
            target_name="test",
            launch_name="launch",
            github_terms=["GitHub"],
            executive_names=[],
            hashtags=[],
            competitors=["GitLab"],
            time_window_hours=72,
            rss_feeds=[],
            max_items_per_source=10,
        )

    def test_classify_excited(self) -> None:
        item = ContentItem(
            title="Amazing launch, huge developer win",
            url="https://example.com/a",
            source="example",
            author=None,
            published_at=None,
            snippet="awesome and excited",
            content="",
            channel="news",
            engagement={},
        )
        label, confidence, themes = classify_item(item)
        self.assertEqual(label, "Excited")
        self.assertGreater(confidence, 0.5)
        self.assertIsInstance(themes, list)

    def test_analyze_detects_competitor_mentions(self) -> None:
        items = [
            ContentItem(
                title="GitHub launch compared to GitLab",
                url="https://example.com/1",
                source="example",
                author=None,
                published_at=None,
                snippet="versus GitLab",
                content="",
                channel="news",
                engagement={},
            )
        ]
        result = analyze_items(items, self.config)
        self.assertTrue(any("GitLab" in x for x in result.competitive_comparisons))


if __name__ == "__main__":
    unittest.main()
