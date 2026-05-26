from __future__ import annotations

import datetime as dt
import json
import urllib.error
import urllib.parse
import urllib.request
import xml.etree.ElementTree as ET
from typing import Any

from .config import MonitoringConfig
from .models import ContentItem

USER_AGENT = "CommsAnalystAgent/0.1 (+https://github.com/BrylanCole/CommsAnalystAgent)"


def _http_get_json(url: str) -> dict[str, Any]:
    req = urllib.request.Request(url, headers={"User-Agent": USER_AGENT})
    with urllib.request.urlopen(req, timeout=20) as response:
        return json.loads(response.read().decode("utf-8"))


def _http_get_text(url: str) -> str:
    req = urllib.request.Request(url, headers={"User-Agent": USER_AGENT})
    with urllib.request.urlopen(req, timeout=20) as response:
        return response.read().decode("utf-8", errors="ignore")


def _safe_collect(fn: Any) -> list[ContentItem]:
    try:
        return fn()
    except (urllib.error.URLError, TimeoutError, ET.ParseError, json.JSONDecodeError, KeyError, ValueError):
        return []


def collect_google_news(config: MonitoringConfig) -> list[ContentItem]:
    def _collect() -> list[ContentItem]:
        items: list[ContentItem] = []
        for term in config.search_terms:
            query = urllib.parse.quote_plus(f"{term} when:{max(1, config.time_window_hours // 24)}d")
            url = f"https://news.google.com/rss/search?q={query}&hl=en-US&gl=US&ceid=US:en"
            xml_text = _http_get_text(url)
            root = ET.fromstring(xml_text)
            for node in root.findall("./channel/item")[: config.max_items_per_source]:
                title = (node.findtext("title") or "").strip()
                link = (node.findtext("link") or "").strip()
                source = (node.findtext("source") or "Google News").strip()
                pub_date = (node.findtext("pubDate") or "").strip() or None
                description = (node.findtext("description") or "").strip()
                if not title or not link:
                    continue
                items.append(
                    ContentItem(
                        title=title,
                        url=link,
                        source=source,
                        author=None,
                        published_at=pub_date,
                        snippet=description,
                        content=description,
                        channel="news",
                        engagement={},
                    )
                )
        return items

    return _safe_collect(_collect)


def collect_reddit(config: MonitoringConfig) -> list[ContentItem]:
    def _collect() -> list[ContentItem]:
        items: list[ContentItem] = []
        window = "day" if config.time_window_hours <= 24 else "week" if config.time_window_hours <= 168 else "month"
        for term in config.search_terms:
            query = urllib.parse.quote_plus(term)
            url = (
                "https://www.reddit.com/search.json"
                f"?q={query}&sort=new&t={window}&limit={config.max_items_per_source}"
            )
            data = _http_get_json(url)
            posts = data.get("data", {}).get("children", [])
            for post in posts:
                details = post.get("data", {})
                permalink = details.get("permalink")
                if not permalink:
                    continue
                items.append(
                    ContentItem(
                        title=details.get("title", "").strip(),
                        url=f"https://www.reddit.com{permalink}",
                        source=f"r/{details.get('subreddit', 'unknown')}",
                        author=details.get("author"),
                        published_at=dt.datetime.utcfromtimestamp(details.get("created_utc", 0)).isoformat() + "Z",
                        snippet=(details.get("selftext", "") or "")[:600],
                        content=(details.get("selftext", "") or "")[:2000],
                        channel="reddit",
                        engagement={
                            "score": details.get("score"),
                            "num_comments": details.get("num_comments"),
                        },
                    )
                )
        return items

    return _safe_collect(_collect)


def collect_hacker_news(config: MonitoringConfig) -> list[ContentItem]:
    def _collect() -> list[ContentItem]:
        items: list[ContentItem] = []
        now = dt.datetime.now(dt.timezone.utc)
        min_time = now - dt.timedelta(hours=config.time_window_hours)
        min_epoch = int(min_time.timestamp())
        for term in config.search_terms:
            query = urllib.parse.quote_plus(term)
            url = (
                "https://hn.algolia.com/api/v1/search_by_date"
                f"?query={query}&tags=story&numericFilters=created_at_i>{min_epoch}&hitsPerPage={config.max_items_per_source}"
            )
            data = _http_get_json(url)
            for hit in data.get("hits", []):
                item_url = hit.get("url") or f"https://news.ycombinator.com/item?id={hit.get('objectID')}"
                items.append(
                    ContentItem(
                        title=(hit.get("title") or "").strip(),
                        url=item_url,
                        source="Hacker News",
                        author=hit.get("author"),
                        published_at=hit.get("created_at"),
                        snippet=(hit.get("story_text") or "")[:600],
                        content=(hit.get("comment_text") or hit.get("story_text") or "")[:2000],
                        channel="hackernews",
                        engagement={"points": hit.get("points")},
                    )
                )
        return items

    return _safe_collect(_collect)


def collect_rss_feeds(config: MonitoringConfig) -> list[ContentItem]:
    def _collect() -> list[ContentItem]:
        items: list[ContentItem] = []
        for feed_url in config.rss_feeds:
            xml_text = _http_get_text(feed_url)
            root = ET.fromstring(xml_text)
            feed_items = root.findall("./channel/item")
            for node in feed_items[: config.max_items_per_source]:
                title = (node.findtext("title") or "").strip()
                link = (node.findtext("link") or "").strip()
                source = urllib.parse.urlparse(feed_url).netloc or "rss"
                if not title or not link:
                    continue
                description = (node.findtext("description") or "").strip()
                items.append(
                    ContentItem(
                        title=title,
                        url=link,
                        source=source,
                        author=node.findtext("author") or None,
                        published_at=node.findtext("pubDate") or None,
                        snippet=description,
                        content=description,
                        channel="rss",
                        engagement={},
                    )
                )
        return items

    return _safe_collect(_collect)


def deduplicate_items(items: list[ContentItem]) -> list[ContentItem]:
    seen: set[str] = set()
    result: list[ContentItem] = []
    for item in items:
        key = f"{item.url.lower()}::{item.title.strip().lower()}"
        if key in seen:
            continue
        seen.add(key)
        result.append(item)
    return result


def collect_all(config: MonitoringConfig) -> list[ContentItem]:
    collected = [
        *collect_google_news(config),
        *collect_reddit(config),
        *collect_hacker_news(config),
        *collect_rss_feeds(config),
    ]
    return deduplicate_items(collected)
