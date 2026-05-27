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


def _display_channel(channel: str) -> str:
    return {
        "news": "News",
        "rss": "RSS",
        "reddit": "Reddit",
        "hackernews": "Hacker News",
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
    if isinstance(score, int):
        parts.append(f"score {score}")
    if isinstance(comments, int):
        parts.append(f"{comments} comments")
    if isinstance(points, int):
        parts.append(f"{points} points")
    return ", ".join(parts)


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


def _top_risks_and_actions(analysis: AggregateAnalysis) -> list[str]:
    risks = analysis.risk_narratives[:2] or analysis.criticism_patterns[:2]
    actions = analysis.opportunity_narratives[:1] + analysis.confusion_patterns[:1]
    lines: list[str] = []
    for risk in risks:
        lines.append(f"• Risk: {risk}.")
    for action in actions:
        lines.append(f"• Recommended focus: {action}.")
    if not lines:
        lines.append("• No concentrated risk pattern detected; continue monitoring for changes in tone.")
    return lines


def build_slack_summary(
    config: MonitoringConfig,
    analysis: AggregateAnalysis,
    generated_at: dt.datetime | None = None,
) -> str:
    generated_at = generated_at or dt.datetime.now(dt.timezone.utc)
    total = len(analysis.analyzed_items)
    counts = defaultdict(int, analysis.sentiment_counts)
    negative_total = counts["Negative"] + counts["Concerned"] + counts["Skeptical"]
    positive_total = counts["Positive"] + counts["Excited"]
    sorted_items = sorted(
        analysis.analyzed_items,
        key=lambda x: (x.authority_score, x.confidence),
        reverse=True,
    )

    headline = f"*{config.target_name} — Deep Sentiment Analysis*"
    timestamp = generated_at.strftime("%B %d, %Y %H:%M UTC")
    dominant_narrative = "; ".join(analysis.dominant_narratives[:2]) or "Insufficient signal"
    top_risk = "; ".join(analysis.risk_narratives[:2]) or "No concentrated risk pattern"
    top_opportunity = "; ".join(analysis.opportunity_narratives[:2]) or "No concentrated opportunity pattern"

    executive_summary = "\n".join(
        [
            "*Executive Summary*",
            (
                f"• Over the last {config.time_window_hours} hours, we collected {total} items and the overall trend is "
                f"{_trend_emoji(analysis.trend_label)} {analysis.trend_label.lower()} "
                f"(confidence {analysis.trend_confidence:.2f})."
            ),
            (
                f"• Negative pressure accounts for {_percent(negative_total, total)}% of the sample; "
                f"positive momentum accounts for {_percent(positive_total, total)}%."
            ),
            f"• Dominant narratives: {dominant_narrative}.",
            f"• Top risks: {top_risk}.",
            f"• Top opportunities: {top_opportunity}.",
        ]
    )

    channel_snapshot = "\n".join(["*Channel Snapshot*", *_channel_snapshot(analysis)])
    key_amplifiers = "\n".join(["*Key Amplifiers*", *_key_amplifiers(sorted_items)])
    deep_dive = "\n".join(
        [
            "*Deep Dive: Top Themes*",
            *[
                f"• {theme}."
                for theme in (
                    analysis.emerging_themes[:3]
                    or analysis.dominant_narratives[:3]
                    or ["No strong recurring theme identified."]
                )
            ],
        ]
    )
    risks_and_actions = "\n".join(["*Top Risks & Recommended Focus*", *_top_risks_and_actions(analysis)])
    sources = "\n".join(
        [
            "*Sources Analyzed*",
            *[
                f"• {item.item.source} — <{item.item.url}|{item.item.title}>"
                for item in sorted_items[:6]
            ],
        ]
    )
    uncertainty = ""
    if analysis.uncertainty_flags:
        uncertainty = "\n".join(["*Uncertainty Flags*", *[f"• {flag}" for flag in analysis.uncertainty_flags[:2]]])

    sections = [
        headline,
        timestamp,
        executive_summary,
        channel_snapshot,
        key_amplifiers,
        deep_dive,
        risks_and_actions,
        sources,
    ]
    if uncertainty:
        sections.append(uncertainty)
    return "\n\n".join(section for section in sections if section).strip()


def build_markdown_report(config: MonitoringConfig, analysis: AggregateAnalysis) -> str:
    total = len(analysis.analyzed_items)
    counts = defaultdict(int, analysis.sentiment_counts)
    sorted_items = sorted(
        analysis.analyzed_items,
        key=lambda x: (x.authority_score, x.confidence),
        reverse=True,
    )
    top_positive = [
        f"[{x.item.title}]({x.item.url}) ({x.item.source})"
        for x in sorted_items
        if x.sentiment_label in {"Positive", "Excited"}
    ][:5]
    top_negative = [
        f"[{x.item.title}]({x.item.url}) ({x.item.source})"
        for x in sorted_items
        if x.sentiment_label in {"Negative", "Concerned", "Skeptical", "Confused"}
    ][:5]

    media_rows = []
    for item in sorted_items:
        if item.item.channel in {"news", "rss", "hackernews"}:
            media_rows.append(
                f"| {item.item.source} | [{item.item.title}]({item.item.url}) | {item.sentiment_label} | {item.authority_score:.2f} |"
            )
        if len(media_rows) >= 10:
            break

    social_highlights = [
        f"[{x.item.title}]({x.item.url}) — {x.item.channel} ({x.sentiment_label}, confidence {x.confidence:.2f})"
        for x in sorted_items
        if x.item.channel in {"reddit", "hackernews"}
    ][:8]

    evidence_links = [f"- [{x.item.title}]({x.item.url}) — {x.item.source}" for x in sorted_items[:20]]

    return f"""# Communications Intelligence Report: {config.target_name}

## Executive Summary
- **Overall trend:** {analysis.trend_label} (confidence {analysis.trend_confidence:.2f})
- **Dominant narratives:** {', '.join(analysis.dominant_narratives[:3]) or 'Insufficient signal'}
- **Top risks:** {', '.join(analysis.risk_narratives[:2]) or 'No concentrated risk pattern'}
- **Top opportunities:** {', '.join(analysis.opportunity_narratives[:2]) or 'No concentrated opportunity pattern'}
- **Bottom line:** Reinforce strong narratives, address confusion quickly, and monitor risk narratives for acceleration.

### At a Glance
| Metric | Value |
|---|---|
| Target | {config.target_name} |
| Time window | Last {config.time_window_hours} hours |
| Total collected items | {total} |
| Trend confidence | {analysis.trend_confidence:.2f} |

### Observed Evidence vs Inferred Conclusions
**Observed evidence**
{_section_items(analysis.observed_evidence)}

**Inferred conclusions**
{_section_items(analysis.inferred_conclusions)}

**Uncertainty flags**
{_section_items(analysis.uncertainty_flags, fallback='No explicit uncertainty flags for this run.')}

## Sentiment Snapshot
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

- Momentum trend label: **{analysis.trend_label}**

## Top Positive Reactions
{_section_items(top_positive)}

## Top Negative Reactions
{_section_items(top_negative)}

## Emerging Narratives
{_section_items(analysis.emerging_themes)}

### Competitive Comparisons
{_section_items(analysis.competitive_comparisons)}

## Media Coverage Summary
| Outlet | Headline | Sentiment | Reach/importance |
|---|---|---|---|
{chr(10).join(media_rows) if media_rows else '| No media items | N/A | N/A | N/A |'}

## Social/Community Conversation Highlights
{_section_items(social_highlights)}

## Recommendations
### Immediate actions (0–24h)
- Clarify misunderstood topics highlighted in confusion patterns.
- Prepare response language for recurring criticism and risk patterns.

### Next actions (24–72h)
- Amplify positive narratives from high-authority outlets and credible community voices.
- Track competitor framing and adjust positioning where comparisons appear repeatedly.
- Re-run monitoring during the next 24-hour cycle to validate trend direction.

## Sources / Evidence
{_section_items(evidence_links)}
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
