from __future__ import annotations

import datetime as dt
import json
from collections import Counter, defaultdict
from dataclasses import asdict
from pathlib import Path

from .analysis import AggregateAnalysis
from .config import MonitoringConfig


def _percent(part: int, total: int) -> float:
    if total == 0:
        return 0.0
    return round((part / total) * 100, 1)


def _section_items(items: list[str], fallback: str = "No strong signal in this run.") -> str:
    if not items:
        return f"- {fallback}"
    return "\n".join(f"- {item}" for item in items)


def _sentiment_row(label: str, count: int, total: int) -> str:
    return f"| {label} | {count} | {_percent(count, total)}% |"


def _markdown_bullets(items: list[str], fallback: str = "No strong signal in this run.") -> str:
    return _section_items(items, fallback=fallback)


def _clean_signal_label(text: str) -> str:
    prefixes = (
        "Observed discussion cluster: ",
        "Emerging: ",
        "Observed praise: ",
        "Observed criticism: ",
        "Observed confusion: ",
        "Risk narrative: ",
        "Opportunity narrative: ",
        "Observed competitor comparison: ",
    )
    for prefix in prefixes:
        if text.startswith(prefix):
            return text[len(prefix) :]
    return text


def _display_channel(channel: str) -> str:
    return {
        "news": "News",
        "rss": "RSS",
        "reddit": "Reddit",
        "hackernews": "Hacker News",
        "linkedin": "LinkedIn",
        "x": "X",
    }.get(channel, channel.replace("_", " ").title())


def _trend_emoji(trend_label: str) -> str:
    lowered = trend_label.lower()
    if "concern" in lowered or "negative" in lowered:
        return "🔴"
    if "polarized" in lowered or "mixed" in lowered:
        return "🟠"
    return "🟢"


def _top_theme(themes: list[str]) -> str:
    if not themes:
        return "general discussion"
    counts = Counter(themes)
    return counts.most_common(1)[0][0].lower()


def _format_engagement(item) -> str:
    parts: list[str] = []
    score = item.item.engagement.get("score")
    comments = item.item.engagement.get("num_comments")
    points = item.item.engagement.get("points")
    reactions = item.item.engagement.get("reactions")
    likes = item.item.engagement.get("likes")
    reposts = item.item.engagement.get("reposts")
    replies = item.item.engagement.get("replies")
    if isinstance(score, int):
        parts.append(f"score {score}")
    if isinstance(comments, int):
        parts.append(f"{comments} comments")
    if isinstance(points, int):
        parts.append(f"{points} points")
    if isinstance(reactions, int):
        parts.append(f"{reactions} reactions")
    if isinstance(likes, int):
        parts.append(f"{likes} likes")
    if isinstance(reposts, int):
        parts.append(f"{reposts} reposts")
    if isinstance(replies, int):
        parts.append(f"{replies} replies")
    return ", ".join(parts)


def _engagement_score(item) -> int:
    keys = ("score", "num_comments", "points", "reactions", "likes", "reposts", "replies")
    return sum(value for key in keys if isinstance((value := item.item.engagement.get(key)), int))


def _published_timestamp(item) -> float:
    published_at = item.item.published_at
    if not published_at:
        return 0.0
    try:
        normalized = published_at.replace("Z", "+00:00")
        parsed = dt.datetime.fromisoformat(normalized)
        if parsed.tzinfo is None:
            parsed = parsed.replace(tzinfo=dt.timezone.utc)
        return parsed.timestamp()
    except ValueError:
        return 0.0


def _headline_priority_key(item) -> tuple[int, int, float, float]:
    engagement = _engagement_score(item)
    published_ts = _published_timestamp(item)
    return (
        int(engagement > 0),
        engagement,
        published_ts,
        item.confidence,
    )


def _majority_sentiment(sentiment_counts: dict[str, int]) -> str:
    if not sentiment_counts:
        return "No dominant sentiment (no items)"
    label, count = max(sentiment_counts.items(), key=lambda pair: pair[1])
    return f"{label} ({count})"


def _channel_snapshot(analysis: AggregateAnalysis) -> list[str]:
    total = len(analysis.analyzed_items)
    grouped: dict[str, list] = defaultdict(list)
    for result in analysis.analyzed_items:
        grouped[result.item.channel].append(result)

    lines: list[str] = []
    for channel, items in sorted(grouped.items(), key=lambda pair: len(pair[1]), reverse=True):
        sentiment_counter = Counter(item.sentiment_label for item in items)
        dominant_sentiment = sentiment_counter.most_common(1)[0][0]
        theme = _top_theme([theme for item in items for theme in item.themes])
        lines.append(
            f"• {_display_channel(channel)} — {len(items)} items ({_percent(len(items), total)}%), "
            f"mostly {dominant_sentiment.lower()}; strongest signal: {theme}."
        )
    return lines


def _channel_table_rows(analysis: AggregateAnalysis) -> list[str]:
    total = len(analysis.analyzed_items)
    grouped: dict[str, list] = defaultdict(list)
    for result in analysis.analyzed_items:
        grouped[result.item.channel].append(result)

    rows: list[str] = []
    for channel, items in sorted(grouped.items(), key=lambda pair: len(pair[1]), reverse=True):
        sentiment_counter = Counter(item.sentiment_label for item in items)
        dominant_sentiment = sentiment_counter.most_common(1)[0][0]
        theme = _top_theme([theme for item in items for theme in item.themes])
        rows.append(
            f"| {_display_channel(channel)} | {len(items)} | {_percent(len(items), total)}% | "
            f"{dominant_sentiment} | {theme.title()} |"
        )
    return rows or ["| No channel data | 0 | 0.0% | N/A | N/A |"]


def _key_amplifiers(sorted_items: list, limit: int = 4) -> list[str]:
    lines: list[str] = []
    for item in sorted_items[:limit]:
        engagement = _format_engagement(item)
        suffix = f"; {engagement}" if engagement else ""
        lines.append(
            f"• {item.item.source} — <{item.item.url}|{item.item.title}> "
            f"({item.sentiment_label.lower()}, importance {item.authority_score:.2f}{suffix})"
        )
    return lines


def _key_amplifier_rows(sorted_items: list, limit: int = 5) -> list[str]:
    rows: list[str] = []
    for item in sorted_items[:limit]:
        engagement = _format_engagement(item) or "N/A"
        rows.append(
            f"| {item.item.source} | [{item.item.title}]({item.item.url}) | "
            f"{_display_channel(item.item.channel)} | {item.sentiment_label} | {engagement} |"
        )
    return rows or ["| No amplifier data | N/A | N/A | N/A | N/A |"]


def _top_risks_and_actions(analysis: AggregateAnalysis) -> list[str]:
    risks = analysis.risk_narratives[:2] or analysis.criticism_patterns[:2]
    actions = analysis.opportunity_narratives[:1] + analysis.confusion_patterns[:1]
    lines: list[str] = []
    for risk in risks:
        lines.append(f"• Risk: {_clean_signal_label(risk)}.")
    for action in actions:
        lines.append(f"• Recommended focus: {_clean_signal_label(action)}.")
    if not lines:
        lines.append("• No concentrated risk pattern detected; continue monitoring for changes in tone.")
    return lines


def _recommended_actions(analysis: AggregateAnalysis) -> tuple[list[str], list[str]]:
    immediate = [
        "Clarify the most repeated confusion or criticism points in outbound messaging.",
        "Prepare response language for the highest-salience risk narratives and likely follow-up questions.",
    ]
    next_actions = [
        "Amplify credible positive narratives from high-authority or high-engagement sources.",
        "Track competitor framing and shifts in channel mix during the next monitoring cycle.",
    ]
    if analysis.confusion_patterns:
        immediate.insert(0, f"Address confusion pattern first: {_clean_signal_label(analysis.confusion_patterns[0])}.")
    if analysis.risk_narratives:
        immediate.insert(0, f"Mitigate leading risk narrative: {_clean_signal_label(analysis.risk_narratives[0])}.")
    if analysis.opportunity_narratives:
        next_actions.insert(0, f"Lean into strongest opportunity narrative: {_clean_signal_label(analysis.opportunity_narratives[0])}.")
    if analysis.competitive_comparisons:
        next_actions.append(f"Watch competitor framing: {_clean_signal_label(analysis.competitive_comparisons[0])}.")
    return immediate[:3], next_actions[:3]


def build_slack_summary(
    config: MonitoringConfig,
    analysis: AggregateAnalysis,
    generated_at: dt.datetime | None = None,
) -> str:
    generated_at = generated_at or dt.datetime.now(dt.timezone.utc)
    total = len(analysis.analyzed_items)
    counts = defaultdict(int, analysis.sentiment_counts)
    sorted_items = sorted(
        analysis.analyzed_items,
        key=lambda x: (x.authority_score, x.confidence),
        reverse=True,
    )
    article_items = [item for item in sorted_items if item.item.channel in {"news", "rss"}]
    social_items = [item for item in sorted_items if item.item.channel in {"reddit", "linkedin", "x", "hackernews"}]

    headline = f"*{config.target_name} — Deep Sentiment Analysis*"
    timestamp = generated_at.strftime("%B %d, %Y %H:%M UTC")
    totals = "\n".join(
        [
            "*Coverage Totals*",
            f"• Total # of articles: {len(article_items)}",
            f"• Total # of posts: {len(social_items)}",
            f"• Total analyzed items: {total}",
            f"• Majority sentiment: {_majority_sentiment(dict(counts))}",
            f"• Overall trend: {_trend_emoji(analysis.trend_label)} {analysis.trend_label} ({analysis.trend_confidence:.2f})",
        ]
    )

    top_headlines = "\n".join(
        [
            "*Top Headlines*",
            *[
                f"• {_display_channel(item.item.channel)} — <{item.item.url}|{item.item.title}>"
                for item in sorted((article_items or sorted_items), key=_headline_priority_key, reverse=True)[:5]
            ],
        ]
    )

    key_themes = "\n".join(
        [
            "*Key Themes / Messages*",
            *[
                f"• {_clean_signal_label(theme)}"
                for theme in (
                    analysis.emerging_themes[:4]
                    or analysis.dominant_narratives[:4]
                    or ["No strong recurring theme identified."]
                )
            ],
        ]
    )

    top_news = "\n".join(
        [
            "*Top News Mentioned*",
            *[
                f"• {item.item.source} — <{item.item.url}|{item.item.title}>"
                for item in article_items[:4]
            ],
        ]
        if article_items
        else ["*Top News Mentioned*", "• No article links were collected in this run."]
    )

    competitor_mentions = "\n".join(
        [
            "*Competitor Mentions / Comparisons*",
            *[
                f"• {_clean_signal_label(item)}"
                for item in analysis.competitive_comparisons[:4]
            ],
        ]
        if analysis.competitive_comparisons
        else ["*Competitor Mentions / Comparisons*", "• No strong competitor-comparison signal detected in collected sample."]
    )

    social_links = "\n".join(
        [
            "*Direct Social Post Links*",
            *[
                f"• {_display_channel(item.item.channel)} — <{item.item.url}|{item.item.title}>"
                for item in social_items[:6]
            ],
        ]
        if social_items
        else ["*Direct Social Post Links*", "• No social post links were collected in this run."]
    )

    sections = [
        headline,
        timestamp,
        totals,
        top_headlines,
        key_themes,
        top_news,
        competitor_mentions,
        social_links,
    ]
    return "\n\n".join(section for section in sections if section).strip()


def build_markdown_report(config: MonitoringConfig, analysis: AggregateAnalysis) -> str:
    total = len(analysis.analyzed_items)
    counts = defaultdict(int, analysis.sentiment_counts)
    negative_total = counts["Negative"] + counts["Concerned"] + counts["Skeptical"]
    positive_total = counts["Positive"] + counts["Excited"]
    sorted_items = sorted(
        analysis.analyzed_items,
        key=lambda x: (x.authority_score, x.confidence),
        reverse=True,
    )
    timestamp = dt.datetime.now(dt.timezone.utc).strftime("%B %d, %Y %H:%M UTC")
    immediate_actions, next_actions = _recommended_actions(analysis)
    source_lines = [f"[{x.item.title}]({x.item.url}) — {x.item.source}" for x in sorted_items[:12]]
    theme_lines = [_clean_signal_label(item) for item in (analysis.emerging_themes[:4] or analysis.dominant_narratives[:4])]
    risk_lines = [_clean_signal_label(item) for item in (analysis.risk_narratives[:3] or analysis.criticism_patterns[:3])]
    opportunity_lines = [
        _clean_signal_label(item) for item in (analysis.opportunity_narratives[:3] or analysis.praise_patterns[:3])
    ]

    return f"""# {config.target_name} — Deep Sentiment Analysis

_{timestamp}_

## Executive Summary
Over the last {config.time_window_hours} hours, we collected **{total} items** and the overall trend is **{analysis.trend_label}** ({analysis.trend_confidence:.2f} confidence).

Negative pressure accounts for **{_percent(negative_total, total)}%** of the sample, while positive momentum accounts for **{_percent(positive_total, total)}%**.

- **Dominant narratives:** {', '.join(_clean_signal_label(item) for item in analysis.dominant_narratives[:3]) or 'Insufficient signal'}
- **Top risks:** {', '.join(_clean_signal_label(item) for item in analysis.risk_narratives[:2]) or 'No concentrated risk pattern'}
- **Top opportunities:** {', '.join(_clean_signal_label(item) for item in analysis.opportunity_narratives[:2]) or 'No concentrated opportunity pattern'}

## Social Performance
| Channel | Volume | Share | Dominant sentiment | Key character |
|---|---:|---:|---|---|
{chr(10).join(_channel_table_rows(analysis))}

## Overall Sentiment: {_trend_emoji(analysis.trend_label)} {analysis.trend_label}
| Sentiment | Count | Share |
|---|---:|---:|
{_sentiment_row('Positive', counts['Positive'], total)}
{_sentiment_row('Excited', counts['Excited'], total)}
{_sentiment_row('Neutral', counts['Neutral'], total)}
{_sentiment_row('Negative', counts['Negative'], total)}
{_sentiment_row('Concerned', counts['Concerned'], total)}
{_sentiment_row('Skeptical', counts['Skeptical'], total)}
{_sentiment_row('Confused', counts['Confused'], total)}
{_sentiment_row('Mixed', counts['Mixed'], total)}

## Key Amplifiers
| Source | Item | Channel | Sentiment | Signal |
|---|---|---|---|---|
{chr(10).join(_key_amplifier_rows(sorted_items))}

## Deep Dive: Top Themes
{_markdown_bullets(theme_lines, fallback='No strong recurring theme identified.')}

### Competitive Comparisons
{_markdown_bullets([_clean_signal_label(item) for item in analysis.competitive_comparisons], fallback='No strong competitor-comparison signal detected in collected sample.')}

## Top Risks & Mitigations
### Risk signals
{_markdown_bullets(risk_lines, fallback='No concentrated risk pattern detected in this run.')}

### Opportunity signals
{_markdown_bullets(opportunity_lines, fallback='No concentrated opportunity pattern detected in this run.')}

### Immediate actions (0–24h)
{_markdown_bullets(immediate_actions)}

### Next actions (24–72h)
{_markdown_bullets(next_actions)}

## Observed Evidence vs Inferred Conclusions
### Observed evidence
{_markdown_bullets(analysis.observed_evidence)}

### Inferred conclusions
{_markdown_bullets(analysis.inferred_conclusions)}

### Uncertainty flags
{_markdown_bullets(analysis.uncertainty_flags, fallback='No explicit uncertainty flags for this run.')}

## Sources Analyzed
{_markdown_bullets(source_lines)}
"""


def build_json_output(config: MonitoringConfig, analysis: AggregateAnalysis) -> dict:
    return {
        "target": asdict(config),
        "sentiment_snapshot": {
            "counts": analysis.sentiment_counts,
            "trend_label": analysis.trend_label,
            "trend_confidence": round(analysis.trend_confidence, 3),
        },
        "narratives": {
            "dominant": analysis.dominant_narratives,
            "emerging": analysis.emerging_themes,
            "praise_patterns": analysis.praise_patterns,
            "criticism_patterns": analysis.criticism_patterns,
            "confusion_patterns": analysis.confusion_patterns,
            "risk_narratives": analysis.risk_narratives,
            "opportunity_narratives": analysis.opportunity_narratives,
            "competitive_comparisons": analysis.competitive_comparisons,
        },
        "evidence": {
            "observed": analysis.observed_evidence,
            "inferred": analysis.inferred_conclusions,
            "uncertainty": analysis.uncertainty_flags,
        },
        "items": [result.to_dict() for result in analysis.analyzed_items],
    }


def write_outputs(output_dir: Path, markdown: str, json_payload: dict, slack_summary: str) -> None:
    output_dir.mkdir(parents=True, exist_ok=True)
    (output_dir / "report.md").write_text(markdown, encoding="utf-8")
    (output_dir / "report.json").write_text(json.dumps(json_payload, indent=2), encoding="utf-8")
    (output_dir / "report_slack.txt").write_text(slack_summary, encoding="utf-8")
