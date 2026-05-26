from __future__ import annotations

import json
from collections import defaultdict
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
- Overall sentiment trend: **{analysis.trend_label}** (confidence {analysis.trend_confidence:.2f}).
- Dominant narratives: {', '.join(analysis.dominant_narratives[:3]) or 'Insufficient signal'}.
- Key risks: {', '.join(analysis.risk_narratives[:2]) or 'No concentrated risk pattern'}.
- Key opportunities: {', '.join(analysis.opportunity_narratives[:2]) or 'No concentrated opportunity pattern'}.
- Most influential reactions came from higher-authority sources and high-confidence items.
- Recommendation summary: reinforce high-performing narratives, address confusion quickly, and monitor risk narratives for acceleration.

### Observed Evidence vs Inferred Conclusions
**Observed evidence**
{_section_items(analysis.observed_evidence)}

**Inferred conclusions**
{_section_items(analysis.inferred_conclusions)}

**Uncertainty flags**
{_section_items(analysis.uncertainty_flags, fallback='No explicit uncertainty flags for this run.')}

## Sentiment Snapshot
- Total collected items: {total}
- Positive: {counts['Positive']} ({_percent(counts['Positive'], total)}%)
- Excited: {counts['Excited']} ({_percent(counts['Excited'], total)}%)
- Neutral: {counts['Neutral']} ({_percent(counts['Neutral'], total)}%)
- Negative: {counts['Negative']} ({_percent(counts['Negative'], total)}%)
- Concerned: {counts['Concerned']} ({_percent(counts['Concerned'], total)}%)
- Skeptical: {counts['Skeptical']} ({_percent(counts['Skeptical'], total)}%)
- Confused: {counts['Confused']} ({_percent(counts['Confused'], total)}%)
- Mixed: {counts['Mixed']} ({_percent(counts['Mixed'], total)}%)
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
- Clarify misunderstood topics highlighted in confusion patterns.
- Amplify positive narratives from high-authority outlets and credible community voices.
- Prepare response language for recurring criticism/risk patterns.
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


def write_outputs(output_dir: Path, markdown: str, json_payload: dict) -> None:
    output_dir.mkdir(parents=True, exist_ok=True)
    (output_dir / "report.md").write_text(markdown, encoding="utf-8")
    (output_dir / "report.json").write_text(json.dumps(json_payload, indent=2), encoding="utf-8")
