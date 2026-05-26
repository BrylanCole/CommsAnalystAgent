from __future__ import annotations

from dataclasses import asdict, dataclass, field
from typing import Any


@dataclass
class ContentItem:
    title: str
    url: str
    source: str
    author: str | None
    published_at: str | None
    snippet: str
    content: str
    channel: str
    engagement: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass
class AnalysisResult:
    item: ContentItem
    sentiment_label: str
    confidence: float
    themes: list[str]
    authority_score: float

    def to_dict(self) -> dict[str, Any]:
        data = asdict(self)
        data["item"] = self.item.to_dict()
        return data
