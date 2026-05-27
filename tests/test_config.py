import json
import tempfile
import unittest
from pathlib import Path

from comms_analyst_agent.config import DEFAULT_SOURCES, MonitoringConfig, load_config


class ConfigTests(unittest.TestCase):
    def test_enabled_sources_normalize_aliases(self) -> None:
        config = MonitoringConfig(
            target_name="Target",
            launch_name="Launch",
            github_terms=["Launch"],
            executive_names=[],
            hashtags=[],
            competitors=[],
            time_window_hours=24,
            rss_feeds=[],
            sources=["Hacker News", "LinkedIn", "news"],
        )
        self.assertIn("hackernews", config.enabled_sources)
        self.assertIn("linkedin", config.enabled_sources)
        self.assertIn("news", config.enabled_sources)

    def test_load_config_defaults_new_fields(self) -> None:
        payload = {
            "target_name": "Target",
            "launch_name": "Launch",
            "github_terms": [],
            "executive_names": [],
            "hashtags": [],
            "competitors": [],
            "time_window_hours": 24,
            "rss_feeds": [],
        }
        with tempfile.TemporaryDirectory() as temp_dir:
            path = Path(temp_dir) / "config.json"
            path.write_text(json.dumps(payload), encoding="utf-8")
            loaded = load_config(path)
        self.assertEqual(loaded.sources, DEFAULT_SOURCES)
        self.assertEqual(loaded.article_domains, [])


if __name__ == "__main__":
    unittest.main()
