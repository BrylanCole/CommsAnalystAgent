from __future__ import annotations

import json
from dataclasses import dataclass, field
from pathlib import Path

DEFAULT_SOURCES: list[str] = ["news", "rss", "reddit", "hackernews", "linkedin", "x"]
SOURCE_ALIASES: dict[str, str] = {
    "hacker news": "hackernews",
    "hn": "hackernews",
    "google news": "news",
    "article": "news",
    "articles": "news",
    "twitter": "x",
    "tweet": "x",
    "tweets": "x",
}


@dataclass
class MonitoringConfig:
    target_name: str
    launch_name: str
    github_terms: list[str]
    executive_names: list[str]
    hashtags: list[str]
    competitors: list[str]
    time_window_hours: int
    rss_feeds: list[str]
    max_items_per_source: int = 25
    sources: list[str] = field(default_factory=lambda: list(DEFAULT_SOURCES))
    article_domains: list[str] = field(default_factory=list)

    @property
    def search_terms(self) -> list[str]:
        terms = [self.launch_name, *self.github_terms, *self.executive_names, *self.hashtags]
        seen: set[str] = set()
        unique: list[str] = []
        for term in terms:
            normalized = term.strip()
            if not normalized:
                continue
            key = normalized.lower()
            if key in seen:
                continue
            seen.add(key)
            unique.append(normalized)
        return unique

    @property
    def enabled_sources(self) -> set[str]:
        normalized: set[str] = set()
        for source in self.sources or DEFAULT_SOURCES:
            key = source.strip().lower()
            if not key:
                continue
            normalized.add(SOURCE_ALIASES.get(key, key))
        return normalized


def load_config(config_path: str | Path) -> MonitoringConfig:
    raw = json.loads(Path(config_path).read_text(encoding="utf-8"))
    return MonitoringConfig(
        target_name=raw["target_name"],
        launch_name=raw["launch_name"],
        github_terms=raw.get("github_terms", []),
        executive_names=raw.get("executive_names", []),
        hashtags=raw.get("hashtags", []),
        competitors=raw.get("competitors", []),
        time_window_hours=int(raw.get("time_window_hours", 72)),
        rss_feeds=raw.get("rss_feeds", []),
        max_items_per_source=int(raw.get("max_items_per_source", 25)),
        sources=raw.get("sources", list(DEFAULT_SOURCES)),
        article_domains=raw.get("article_domains", []),
    )
