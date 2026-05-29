import unittest

from comms_analyst_agent.prompt_parser import (
    DEFAULT_RSS_FEEDS,
    _extract_exclude_domains,
    _extract_time_window,
    _extract_competitors,
    _extract_hashtags,
    _extract_source_focus,
    parse_prompt,
    describe_config,
)


class TimeWindowExtractionTests(unittest.TestCase):
    def test_hours_explicit(self) -> None:
        self.assertEqual(_extract_time_window("last 24 hours"), 24)

    def test_hours_abbrev(self) -> None:
        self.assertEqual(_extract_time_window("past 48 hrs"), 48)

    def test_days(self) -> None:
        self.assertEqual(_extract_time_window("last 3 days"), 72)

    def test_weeks(self) -> None:
        self.assertEqual(_extract_time_window("past 2 weeks"), 336)

    def test_default_no_match(self) -> None:
        self.assertEqual(_extract_time_window("track github copilot"), 72)


class HashtagExtractionTests(unittest.TestCase):
    def test_extracts_single(self) -> None:
        self.assertIn("#GitHub", _extract_hashtags("monitor #GitHub coverage"))

    def test_extracts_multiple(self) -> None:
        result = _extract_hashtags("watch #AI and #MachineLearning last 3 days")
        self.assertIn("#AI", result)
        self.assertIn("#MachineLearning", result)

    def test_no_hashtags(self) -> None:
        self.assertEqual(_extract_hashtags("track openai sora"), [])


class CompetitorExtractionTests(unittest.TestCase):
    def test_vs_pattern(self) -> None:
        result = _extract_competitors("GitHub Copilot vs OpenAI, GitLab")
        self.assertTrue(any("OpenAI" in r for r in result) or any("GitLab" in r for r in result))

    def test_competitors_keyword(self) -> None:
        result = _extract_competitors("track reactions, competitors: Runway, Pika")
        self.assertTrue(any("Runway" in r or "Pika" in r for r in result))

    def test_empty_when_none(self) -> None:
        self.assertEqual(_extract_competitors("track GitHub Copilot launch"), [])


class SourceFocusExtractionTests(unittest.TestCase):
    def test_extracts_single_source(self) -> None:
        self.assertEqual(_extract_source_focus("monitor LinkedIn reactions"), ["linkedin"])

    def test_extracts_article_aliases(self) -> None:
        result = _extract_source_focus("track online articles and reddit")
        self.assertIn("news", result)
        self.assertIn("rss", result)
        self.assertIn("reddit", result)

    def test_extracts_x_aliases(self) -> None:
        result = _extract_source_focus("monitor updates on X and Twitter")
        self.assertIn("x", result)


class ParsePromptTests(unittest.TestCase):
    def test_basic_topic_parsed(self) -> None:
        cfg = parse_prompt("Monitor sentiment around GitHub Copilot over the last 72 hours")
        self.assertIn("github copilot", cfg.launch_name.lower())

    def test_time_window_applied(self) -> None:
        cfg = parse_prompt("Track OpenAI Sora over the last 24 hours")
        self.assertEqual(cfg.time_window_hours, 24)

    def test_target_name_preserves_brand_casing(self) -> None:
        cfg = parse_prompt("Track sentiment around GitHub Copilot over the last 24 hours")
        self.assertEqual(cfg.target_name, "GitHub Copilot")

    def test_default_time_window(self) -> None:
        cfg = parse_prompt("Track GitHub Copilot")
        self.assertEqual(cfg.time_window_hours, 72)

    def test_default_feeds_present(self) -> None:
        cfg = parse_prompt("Track GitHub Copilot launch")
        for feed in DEFAULT_RSS_FEEDS:
            self.assertIn(feed, cfg.rss_feeds)

    def test_max_items_default(self) -> None:
        cfg = parse_prompt("Monitor GitHub Copilot")
        self.assertEqual(cfg.max_items_per_source, 25)

    def test_max_items_explicit(self) -> None:
        cfg = parse_prompt("Monitor GitHub Copilot top 10 items")
        self.assertEqual(cfg.max_items_per_source, 10)

    def test_source_focus_applied(self) -> None:
        cfg = parse_prompt("Monitor GitHub Copilot on LinkedIn, Reddit, and X over the last 24 hours")
        self.assertIn("linkedin", cfg.enabled_sources)
        self.assertIn("reddit", cfg.enabled_sources)
        self.assertIn("x", cfg.enabled_sources)
        self.assertNotIn("news", cfg.enabled_sources)

    def test_default_sources_used_when_not_specified(self) -> None:
        cfg = parse_prompt("Monitor GitHub Copilot")
        self.assertIn("news", cfg.enabled_sources)
        self.assertIn("rss", cfg.enabled_sources)

    def test_hashtags_extracted(self) -> None:
        cfg = parse_prompt("Track #GitHubCopilot over the last 48 hours")
        self.assertIn("#githubcopilot", cfg.hashtags)

    def test_product_launch_preset_adds_terms(self) -> None:
        cfg = parse_prompt("Track GitHub Copilot product launch over the last 72 hours")
        all_terms = " ".join(cfg.github_terms).lower()
        self.assertIn("launch", all_terms)

    def test_config_has_non_empty_target_name(self) -> None:
        cfg = parse_prompt("Analyse sentiment around OpenAI")
        self.assertTrue(cfg.target_name.strip())

    def test_config_is_monitoring_config_instance(self) -> None:
        from comms_analyst_agent.config import MonitoringConfig
        cfg = parse_prompt("Track Sora AI over the last 48 hours")
        self.assertIsInstance(cfg, MonitoringConfig)


class ExcludeDomainsTests(unittest.TestCase):
    def test_extracts_explicit_domain(self) -> None:
        result = _extract_exclude_domains("Track GitHub Copilot. Do not reference github.blog")
        self.assertIn("github.blog", result)

    def test_extracts_multiple_domains(self) -> None:
        result = _extract_exclude_domains("exclude techcrunch.com and theverge.com")
        self.assertIn("techcrunch.com", result)
        self.assertIn("theverge.com", result)

    def test_vendor_self_published_blogs_phrase(self) -> None:
        result = _extract_exclude_domains(
            "Do not reference GitHub self-published blogs"
        )
        self.assertIn("github.blog", result)
        self.assertIn("github.com", result)

    def test_no_exclusions_returns_empty(self) -> None:
        self.assertEqual(_extract_exclude_domains("monitor sentiment around copilot"), [])

    def test_parse_prompt_wires_exclude_domains(self) -> None:
        cfg = parse_prompt(
            'Track sentiment around "Copilot Pricing". Do not reference github.blog'
        )
        self.assertIn("github.blog", cfg.exclude_domains)


class DefaultRssFeedsTests(unittest.TestCase):
    def test_default_feeds_excludes_github_owned(self) -> None:
        joined = " ".join(DEFAULT_RSS_FEEDS).lower()
        self.assertNotIn("github.blog", joined)
        self.assertNotIn("github.com", joined)


class DescribeConfigTests(unittest.TestCase):
    def test_describe_contains_key_fields(self) -> None:
        cfg = parse_prompt("Monitor GitHub Copilot over the last 24 hours")
        desc = describe_config(cfg)
        self.assertIn("Time window", desc)
        self.assertIn("Search terms", desc)
        self.assertIn("Sources", desc)

    def test_describe_returns_string(self) -> None:
        cfg = parse_prompt("Track Sora")
        self.assertIsInstance(describe_config(cfg), str)


if __name__ == "__main__":
    unittest.main()
