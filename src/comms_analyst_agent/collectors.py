from __future__ import annotations

import datetime as dt
import json
import os
import urllib.error
import urllib.parse
import urllib.request
import xml.etree.ElementTree as ET
from typing import Any

from .config import MonitoringConfig
from .models import ContentItem

USER_AGENT = "CommsAnalystAgent/0.1 (+https://github.com/BrylanCole/CommsAnalystAgent)"


def _http_get_json(url: str, headers: dict[str, str] | None = None) -> dict[str, Any]:
    request_headers = {"User-Agent": USER_AGENT, **(headers or {})}
    req = urllib.request.Request(url, headers=request_headers)
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


def _domain_allowed(url: str, allowlist: list[str]) -> bool:
    if not allowlist:
        return True
    host = urllib.parse.urlparse(url).netloc.lower()
    if not host:
        return False
    normalized = [domain.lower().lstrip(".") for domain in allowlist if domain.strip()]
    return any(host == domain or host.endswith(f".{domain}") for domain in normalized)


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
                if not _domain_allowed(link, config.article_domains):
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


def collect_linkedin(config: MonitoringConfig) -> list[ContentItem]:
    def _collect() -> list[ContentItem]:
        access_token = os.getenv("COMMS_LINKEDIN_ACCESS_TOKEN", "").strip()
        if not access_token:
            return []

        api_base = os.getenv("COMMS_LINKEDIN_API_BASE", "https://api.linkedin.com").rstrip("/")
        headers = {"Authorization": "Bearer " + access_token}
        page_size = min(config.max_items_per_source, 10)
        items: list[ContentItem] = []

        for term in config.search_terms:
            start = 0
            term_count = 0
            while start < config.max_items_per_source:
                query = urllib.parse.quote_plus(term)
                url = (
                    f"{api_base}/v2/posts"
                    f"?q=search&keywords={query}&count={page_size}&start={start}"
                )
                try:
                    data = _http_get_json(url, headers=headers)
                except urllib.error.HTTPError as exc:
                    if exc.code == 429:
                        break
                    raise

                records = data.get("elements") or data.get("data") or []
                if not records:
                    break

                for record in records:
                    text = (
                        record.get("commentary")
                        or record.get("text")
                        or record.get("message")
                        or record.get("summary")
                        or ""
                    )
                    title = (
                        record.get("title")
                        or text.splitlines()[0]
                        or f"LinkedIn mention: {term}"
                    )
                    permalink = (
                        record.get("permalink")
                        or record.get("url")
                        or record.get("activity")
                        or ""
                    )
                    if not permalink:
                        continue

                    created = record.get("created") or {}
                    engagement = record.get("engagement") or record.get("metrics") or {}
                    author = record.get("authorName") or record.get("author") or None

                    items.append(
                        ContentItem(
                            title=title.strip()[:180],
                            url=str(permalink).strip(),
                            source="LinkedIn",
                            author=author,
                            published_at=str(
                                created.get("time")
                                or record.get("publishedAt")
                                or record.get("createdAt")
                                or ""
                            ).strip()
                            or None,
                            snippet=text.strip()[:600],
                            content=text.strip()[:2000],
                            channel="linkedin",
                            engagement={
                                "reactions": engagement.get("reactionCount"),
                                "comments": engagement.get("commentaryCount"),
                                "shares": engagement.get("shareCount"),
                            },
                        )
                    )
                    term_count += 1
                    if term_count >= config.max_items_per_source:
                        break

                if term_count >= config.max_items_per_source:
                    break
                if len(records) < page_size:
                    break
                start += page_size

        return items

    return _safe_collect(_collect)


def collect_x_posts(config: MonitoringConfig) -> list[ContentItem]:
    def _collect() -> list[ContentItem]:
        bearer_token = os.getenv("COMMS_X_BEARER_TOKEN", "").strip()
        if not bearer_token:
            return []

        api_base = os.getenv("COMMS_X_API_BASE", "https://api.x.com").rstrip("/")
        headers = {"Authorization": "Bearer " + bearer_token}
        page_size = max(10, min(config.max_items_per_source, 100))
        items: list[ContentItem] = []

        for term in config.search_terms:
            query = urllib.parse.quote_plus(f'"{term}" lang:en -is:retweet')
            url = (
                f"{api_base}/2/tweets/search/recent"
                f"?query={query}&max_results={page_size}"
                "&tweet.fields=created_at,author_id,public_metrics,text"
                "&expansions=author_id"
                "&user.fields=username,name"
            )
            try:
                data = _http_get_json(url, headers=headers)
            except urllib.error.HTTPError as exc:
                if exc.code in {401, 403, 429}:
                    break
                raise

            records = data.get("data") or []
            users = {user.get("id"): user for user in data.get("includes", {}).get("users", [])}
            term_count = 0
            for record in records:
                tweet_id = str(record.get("id") or "").strip()
                if not tweet_id:
                    continue
                author_id = str(record.get("author_id") or "").strip()
                user = users.get(author_id, {})
                username = str(user.get("username") or "").strip()
                permalink = (
                    f"https://x.com/{username}/status/{tweet_id}"
                    if username
                    else f"https://x.com/i/web/status/{tweet_id}"
                )
                text = str(record.get("text") or "").strip()
                metrics = record.get("public_metrics") or {}
                items.append(
                    ContentItem(
                        title=(text.splitlines()[0] or f"X post mention: {term}")[:180],
                        url=permalink,
                        source="X",
                        author=(f"@{username}" if username else None),
                        published_at=str(record.get("created_at") or "").strip() or None,
                        snippet=text[:600],
                        content=text[:2000],
                        channel="x",
                        engagement={
                            "likes": metrics.get("like_count"),
                            "reposts": metrics.get("retweet_count"),
                            "replies": metrics.get("reply_count"),
                            "quotes": metrics.get("quote_count"),
                        },
                    )
                )
                term_count += 1
                if term_count >= config.max_items_per_source:
                    break

        return items

    return _safe_collect(_collect)


def collect_threads(config: MonitoringConfig) -> list[ContentItem]:
    def _collect() -> list[ContentItem]:
        access_token = os.getenv("COMMS_THREADS_ACCESS_TOKEN", "").strip()
        if not access_token:
            return []

        api_base = os.getenv("COMMS_THREADS_API_BASE", "https://graph.threads.net").rstrip("/")
        api_version = os.getenv("COMMS_THREADS_API_VERSION", "v1.0").strip("/") or "v1.0"
        search_type = os.getenv("COMMS_THREADS_SEARCH_TYPE", "TOP").strip() or "TOP"
        fields = "id,text,permalink,timestamp,username,media_type"
        items: list[ContentItem] = []

        for term in config.search_terms:
            query = urllib.parse.quote_plus(term)
            url = (
                f"{api_base}/{api_version}/keyword_search"
                f"?q={query}&search_type={search_type}"
                f"&fields={fields}"
                f"&access_token={urllib.parse.quote_plus(access_token)}"
            )
            try:
                data = _http_get_json(url)
            except urllib.error.HTTPError as exc:
                if exc.code in {401, 403, 429}:
                    break
                raise

            records = data.get("data") or []
            term_count = 0
            for record in records:
                permalink = str(record.get("permalink") or "").strip()
                if not permalink:
                    continue
                text = str(record.get("text") or "").strip()
                username = str(record.get("username") or "").strip()
                title = (text.splitlines()[0] if text else f"Threads mention: {term}")[:180]
                items.append(
                    ContentItem(
                        title=title,
                        url=permalink,
                        source="Threads",
                        author=(f"@{username}" if username else None),
                        published_at=str(record.get("timestamp") or "").strip() or None,
                        snippet=text[:600],
                        content=text[:2000],
                        channel="threads",
                        engagement={},
                    )
                )
                term_count += 1
                if term_count >= config.max_items_per_source:
                    break

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
                if not _domain_allowed(link, config.article_domains):
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
    sources = config.enabled_sources
    collected: list[ContentItem] = []
    if "news" in sources:
        collected.extend(collect_google_news(config))
    if "reddit" in sources:
        collected.extend(collect_reddit(config))
    if "hackernews" in sources:
        collected.extend(collect_hacker_news(config))
    if "rss" in sources:
        collected.extend(collect_rss_feeds(config))
    if "linkedin" in sources:
        collected.extend(collect_linkedin(config))
    if "x" in sources:
        collected.extend(collect_x_posts(config))
    if "threads" in sources:
        collected.extend(collect_threads(config))
    return deduplicate_items(collected)
