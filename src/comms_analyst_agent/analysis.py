from __future__ import annotations

from collections import Counter, defaultdict
from dataclasses import dataclass
from typing import Iterable
from urllib.parse import urlparse

from .config import MonitoringConfig
from .models import AnalysisResult, ContentItem

SENTIMENT_KEYWORDS: dict[str, set[str]] = {
    "Positive": {"good", "great", "strong", "improved", "helpful", "win", "success", "love", "solid"},
    "Neutral": {"announced", "released", "available", "update", "information", "details", "news"},
    "Negative": {"bad", "worse", "failure", "problem", "bug", "broken", "angry", "hate", "disappoint"},
    "Mixed": {"but", "however", "mixed", "tradeoff", "both"},
    "Skeptical": {"skeptical", "doubt", "question", "unclear", "not sure", "prove"},
    "Confused": {"confused", "what", "how", "unclear", "don\u2019t understand", "dont understand"},
    "Excited": {"excited", "awesome", "amazing", "huge", "finally", "can\u2019t wait", "cant wait"},
    "Concerned": {"concern", "risk", "worry", "privacy", "security", "cost", "pricing", "lock-in"},
}

THEME_KEYWORDS: dict[str, set[str]] = {
    "Pricing and value": {"pricing", "price", "cost", "value", "expensive", "cheap"},
    "Product capability": {"feature", "workflow", "quality", "performance", "integration", "developer"},
    "Security and trust": {"security", "privacy", "compliance", "trust", "policy", "incident"},
    "Adoption and usability": {"adoption", "onboarding", "learn", "easy", "hard", "migration"},
    "Competitive comparison": {"vs", "versus", "compared", "alternative", "competitor"},
}

DOMAIN_AUTHORITY: dict[str, float] = {
    "github.blog": 0.95,
    "news.ycombinator.com": 0.75,
    "reddit.com": 0.65,
    "techcrunch.com": 0.85,
    "theverge.com": 0.8,
    "arstechnica.com": 0.8,
}


@dataclass
class AggregateAnalysis:
    analyzed_items: list[AnalysisResult]
    sentiment_counts: dict[str, int]
    trend_label: str
    trend_confidence: float
    dominant_narratives: list[str]
    emerging_themes: list[str]
    praise_patterns: list[str]
    criticism_patterns: list[str]
    confusion_patterns: list[str]
    risk_narratives: list[str]
    opportunity_narratives: list[str]
    competitive_comparisons: list[str]
    observed_evidence: list[str]
    inferred_conclusions: list[str]
    uncertainty_flags: list[str]


def _normalize_text(item: ContentItem) -> str:
    return " ".join(
        part.strip().lower() for part in [item.title, item.snippet, item.content] if part
    )


def _authority_score(url: str, channel: str) -> float:
    domain = urlparse(url).netloc.lower().removeprefix("www.")
    if domain in DOMAIN_AUTHORITY:
        return DOMAIN_AUTHORITY[domain]
    if channel in {"news", "rss"}:
        return 0.7
    if channel == "hackernews":
        return 0.72
    if channel == "reddit":
        return 0.62
    return 0.55


def classify_item(item: ContentItem) -> tuple[str, float, list[str]]:
    text = _normalize_text(item)
    scores: dict[str, int] = {}
    for label, words in SENTIMENT_KEYWORDS.items():
        scores[label] = sum(1 for word in words if word in text)
    chosen = max(scores, key=scores.get)
    max_score = scores[chosen]
    if max_score == 0:
        return "Neutral", 0.45, []

    tied = [label for label, score in scores.items() if score == max_score]
    if len(tied) > 1 and "Mixed" not in tied:
        chosen = "Mixed"
    confidence = min(0.95, 0.5 + (max_score * 0.08))
    themes = [name for name, keywords in THEME_KEYWORDS.items() if any(k in text for k in keywords)]
    return chosen, confidence, themes


def _trend_label(counts: Counter[str]) -> tuple[str, float]:
    total = sum(counts.values()) or 1
    positive = counts["Positive"] + counts["Excited"]
    negative = counts["Negative"] + counts["Concerned"] + counts["Skeptical"]
    mixed = counts["Mixed"] + counts["Confused"]

    positive_ratio = positive / total
    negative_ratio = negative / total
    mixed_ratio = mixed / total

    if negative_ratio >= 0.55 and counts["Concerned"] >= max(2, counts["Positive"]):
        return "Escalating concern", min(0.95, 0.6 + negative_ratio / 2)
    if positive_ratio >= 0.65:
        return "Strongly positive", min(0.95, 0.6 + positive_ratio / 3)
    if positive_ratio > negative_ratio and positive_ratio >= 0.45:
        return "Moderately positive", min(0.9, 0.55 + positive_ratio / 3)
    if mixed_ratio >= 0.35 and positive_ratio >= 0.2 and negative_ratio >= 0.2:
        return "Polarized", min(0.9, 0.5 + mixed_ratio / 2)
    if negative_ratio >= 0.45:
        return "Negative", min(0.9, 0.5 + negative_ratio / 2)
    return "Mixed", 0.55


def _top_labels(counter: Counter[str], prefix: str, n: int = 3) -> list[str]:
    return [f"{prefix}: {label} ({count})" for label, count in counter.most_common(n) if count > 0]


def analyze_items(items: Iterable[ContentItem], config: MonitoringConfig) -> AggregateAnalysis:
    analyzed: list[AnalysisResult] = []
    theme_counter: Counter[str] = Counter()
    sentiment_counter: Counter[str] = Counter()
    risk_counter: Counter[str] = Counter()
    opportunity_counter: Counter[str] = Counter()
    confusion_counter: Counter[str] = Counter()
    comparison_mentions: defaultdict[str, int] = defaultdict(int)

    for item in items:
        label, confidence, themes = classify_item(item)
        authority = _authority_score(item.url, item.channel)
        analyzed.append(
            AnalysisResult(
                item=item,
                sentiment_label=label,
                confidence=confidence,
                themes=themes,
                authority_score=authority,
            )
        )
        sentiment_counter[label] += 1
        for theme in themes:
            theme_counter[theme] += 1
        for competitor in config.competitors:
            if competitor.lower() in _normalize_text(item):
                comparison_mentions[competitor] += 1
        if label in {"Concerned", "Negative", "Skeptical"}:
            for theme in themes or ["General concern"]:
                risk_counter[theme] += 1
        if label in {"Positive", "Excited"}:
            for theme in themes or ["General enthusiasm"]:
                opportunity_counter[theme] += 1
        if label == "Confused":
            for theme in themes or ["General confusion"]:
                confusion_counter[theme] += 1

    trend_label, trend_confidence = _trend_label(sentiment_counter)

    dominant_narratives = _top_labels(theme_counter, "Observed discussion cluster")
    emerging_themes = _top_labels(theme_counter, "Emerging")
    praise_patterns = _top_labels(opportunity_counter, "Observed praise")
    criticism_patterns = _top_labels(risk_counter, "Observed criticism")
    confusion_patterns = _top_labels(confusion_counter, "Observed confusion")
    risk_narratives = _top_labels(risk_counter, "Risk narrative")
    opportunity_narratives = _top_labels(opportunity_counter, "Opportunity narrative")
    competitive_comparisons = [
        f"Observed competitor comparison: {name} ({count} mentions)"
        for name, count in sorted(comparison_mentions.items(), key=lambda x: x[1], reverse=True)
        if count > 0
    ]

    observed_evidence = [
        f"Collected {len(analyzed)} unique items across channels.",
        f"Top sentiment labels: {', '.join(f'{k}={v}' for k, v in sentiment_counter.items() if v > 0) or 'none'}.",
    ]
    inferred_conclusions = [
        f"Overall trend is {trend_label.lower()} (confidence {trend_confidence:.2f}).",
        "High-authority sources were weighted more heavily in prioritization and summary ordering.",
    ]

    uncertainty_flags: list[str] = []
    if len(analyzed) < 10:
        uncertainty_flags.append("Low sample size; treat directional conclusions as preliminary.")
    if not competitive_comparisons:
        uncertainty_flags.append("No strong competitor-comparison signal detected in collected sample.")

    return AggregateAnalysis(
        analyzed_items=analyzed,
        sentiment_counts=dict(sentiment_counter),
        trend_label=trend_label,
        trend_confidence=trend_confidence,
        dominant_narratives=dominant_narratives,
        emerging_themes=emerging_themes,
        praise_patterns=praise_patterns,
        criticism_patterns=criticism_patterns,
        confusion_patterns=confusion_patterns,
        risk_narratives=risk_narratives,
        opportunity_narratives=opportunity_narratives,
        competitive_comparisons=competitive_comparisons,
        observed_evidence=observed_evidence,
        inferred_conclusions=inferred_conclusions,
        uncertainty_flags=uncertainty_flags,
    )
