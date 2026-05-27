"""prompt_parser.py — convert a plain-English prompt into a MonitoringConfig.

This module is intentionally dependency-free (no external AI/LLM calls).
It uses lightweight keyword extraction and sensible defaults so non-technical
team members can type a sentence instead of editing a JSON file.
"""

from __future__ import annotations

import re

from .config import DEFAULT_SOURCES, MonitoringConfig

# ---------------------------------------------------------------------------
# Default feeds used when the user does not mention a specific source
# ---------------------------------------------------------------------------
DEFAULT_RSS_FEEDS: list[str] = [
    "https://hnrss.org/frontpage",
    "https://github.blog/feed/",
]

# ---------------------------------------------------------------------------
# Built-in topic presets  (key = trigger phrase → partial config dict)
# ---------------------------------------------------------------------------
PROMPT_PRESETS: dict[str, dict] = {
    "product launch": {
        "label": "product launch",
        "extra_terms": ["launch", "announcement", "release", "new feature", "GA", "generally available"],
        "hashtag_hints": ["#launch", "#newrelease"],
    },
    "executive announcement": {
        "label": "executive announcement",
        "extra_terms": ["CEO", "CTO", "executive", "statement", "announcement"],
        "hashtag_hints": [],
    },
    "crisis": {
        "label": "crisis monitoring",
        "extra_terms": ["outage", "incident", "security", "breach", "vulnerability", "backlash"],
        "hashtag_hints": [],
    },
    "competitor": {
        "label": "competitor reaction",
        "extra_terms": ["vs", "versus", "compared to", "alternative"],
        "hashtag_hints": [],
    },
}


# ---------------------------------------------------------------------------
# Time-window extraction helpers
# ---------------------------------------------------------------------------
_TIME_RE = re.compile(
    r"(?:last|past|in the last|over the last)\s+(\d+)\s*(hours|hour|hrs|hr|days|day|weeks|week)",
    re.IGNORECASE,
)

def _extract_time_window(text: str) -> int:
    """Return hours for phrases like 'last 24 hours', 'past 3 days', etc. Default 72."""
    m = _TIME_RE.search(text)
    if not m:
        return 72
    amount = int(m.group(1))
    unit = m.group(2).lower()
    if unit.startswith("hour") or unit.startswith("hr"):
        return max(1, amount)
    if unit.startswith("week"):
        return min(720, amount * 168)
    return min(720, amount * 24)  # days


# ---------------------------------------------------------------------------
# Hashtag extraction
# ---------------------------------------------------------------------------
_HASHTAG_RE = re.compile(r"#\w+")


def _extract_hashtags(text: str) -> list[str]:
    return _HASHTAG_RE.findall(text)


# ---------------------------------------------------------------------------
# Source-focus extraction
# ---------------------------------------------------------------------------
_SOURCE_MAP: dict[str, list[str]] = {
    "reddit": ["reddit"],
    "linkedin": ["linkedin"],
    "x": ["x"],
    "twitter": ["x"],
    "hacker news": ["hackernews"],
    "hn": ["hackernews"],
    "news": ["news"],
    "article": ["news", "rss"],
    "articles": ["news", "rss"],
    "blog": ["rss"],
    "blogs": ["rss"],
    "rss": ["rss"],
}

def _extract_source_focus(text: str) -> list[str]:
    """Return channel labels mentioned in the prompt (empty = all sources)."""
    lower = text.lower()
    found: list[str] = []
    for keyword, channels in _SOURCE_MAP.items():
        if keyword in lower:
            for ch in channels:
                if ch not in found:
                    found.append(ch)
    return found


# ---------------------------------------------------------------------------
# Competitor extraction
# ---------------------------------------------------------------------------
_COMPETITOR_SIGNALS = re.compile(
    r"competitor[s]?\s*[:\-]?\s*([\w,\s]+?)(?:\.|,|\n|and |\bas well\b|$)",
    re.IGNORECASE,
)
_VS_SIGNAL = re.compile(
    r"\bvs\.?\s+([\w\s,]+?)(?:\.|,|\n|$)",
    re.IGNORECASE,
)


def _extract_competitors(text: str) -> list[str]:
    competitors: list[str] = []
    for pattern in (_COMPETITOR_SIGNALS, _VS_SIGNAL):
        for m in pattern.finditer(text):
            for name in re.split(r"[,\s]+and\s+|,\s*", m.group(1)):
                name = name.strip().strip(".")
                if name and name not in competitors:
                    competitors.append(name)
    return competitors[:6]


# ---------------------------------------------------------------------------
# Executive/person name extraction
# ---------------------------------------------------------------------------
_EXEC_RE = re.compile(
    r"(?:executive[s]?|named?|ceo|cto|cmo|vp|director|led? by|from)\s+([A-Z][a-z]+(?:\s+[A-Z][a-z]+)+)",
)


def _extract_executives(text: str) -> list[str]:
    return [m.group(1).strip() for m in _EXEC_RE.finditer(text)]


# ---------------------------------------------------------------------------
# Core topic extraction
# ---------------------------------------------------------------------------
def _extract_topic(text: str) -> str:
    """Pull out the main topic phrase from the prompt."""
    # Try quoted topic first
    quoted = re.search(r'"([^"]+)"', text)
    if quoted:
        return quoted.group(1).strip()

    # Strip time phrases to reduce noise
    cleaned = _TIME_RE.sub("", text)
    # Strip hashtags
    cleaned = _HASHTAG_RE.sub("", cleaned)
    # Take the first significant noun phrase (heuristic: up to 5 words after
    # common trigger verbs)
    trigger = re.search(
        r"(?:coverage and sentiment (?:around|for|on)|sentiment (?:around|for|on)|coverage of|about|monitor|track|analyse|analyze|watch|research|report on|focus on)\s+(.+)",
        cleaned,
        re.IGNORECASE,
    )
    if trigger:
        phrase = trigger.group(1).strip()
        phrase = re.sub(
            r"^(?:coverage and sentiment|sentiment)\s+(?:around|for|on)\s+",
            "",
            phrase,
            flags=re.IGNORECASE,
        )
        return " ".join(phrase.split()[:7]).rstrip(".,;")

    # Fallback: first non-stopword chunk
    stopwords = {"please", "can", "you", "i", "want", "need", "run", "do", "a", "an", "the", "to"}
    words = [w for w in cleaned.split() if w.lower() not in stopwords]
    return " ".join(words[:6]).rstrip(".,;") or "unknown topic"


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

def parse_prompt(prompt: str) -> MonitoringConfig:
    """Convert a free-text prompt into a MonitoringConfig.

    Parameters
    ----------
    prompt:
        A natural-language request such as
        "Track sentiment around OpenAI Sora over the last 48 hours".

    Returns
    -------
    MonitoringConfig
        Ready to pass into the existing pipeline.
    """
    topic = _extract_topic(prompt)
    terms = [topic] if topic else []

    # Apply any matching preset to enrich terms/hashtags
    preset_hashtags: list[str] = []
    for trigger, preset in PROMPT_PRESETS.items():
        if trigger in prompt.lower():
            terms += preset["extra_terms"]
            preset_hashtags += preset.get("hashtag_hints", [])
            break

    # Deduplicate terms preserving order
    seen: set[str] = set()
    unique_terms: list[str] = []
    for t in terms:
        key = t.lower().strip()
        if key and key not in seen:
            seen.add(key)
            unique_terms.append(t.strip())

    hashtags = _extract_hashtags(prompt) + preset_hashtags
    # deduplicate hashtags
    hashtags = list(dict.fromkeys(h.lower() for h in hashtags))

    time_window = _extract_time_window(prompt)
    competitors = _extract_competitors(prompt)
    executives = _extract_executives(prompt)
    source_focus = _extract_source_focus(prompt)

    # Max items: look for explicit "top N" style hint
    items_match = re.search(r"\b(top|max|limit)\s+(\d+)\b", prompt, re.IGNORECASE)
    max_items = int(items_match.group(2)) if items_match else 25

    return MonitoringConfig(
        target_name=topic.strip(),
        launch_name=topic,
        github_terms=unique_terms,
        executive_names=executives,
        hashtags=hashtags,
        competitors=competitors,
        time_window_hours=time_window,
        rss_feeds=DEFAULT_RSS_FEEDS,
        max_items_per_source=max_items,
        sources=source_focus or list(DEFAULT_SOURCES),
    )


def describe_config(config: MonitoringConfig) -> str:
    """Return a human-readable summary of what the agent will monitor."""
    lines = [
        f"  Topic          : {config.launch_name}",
        f"  Search terms   : {', '.join(config.github_terms) or '(none)'}",
        f"  Hashtags       : {', '.join(config.hashtags) or '(none)'}",
        f"  Competitors    : {', '.join(config.competitors) or '(none)'}",
        f"  Time window    : last {config.time_window_hours} hours",
        f"  Max items/src  : {config.max_items_per_source}",
        f"  Sources        : {', '.join(sorted(config.enabled_sources))}",
        f"  RSS feeds      : {len(config.rss_feeds)} feed(s)",
    ]
    return "\n".join(lines)
