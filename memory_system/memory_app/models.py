from __future__ import annotations

from dataclasses import asdict, dataclass, field
from typing import Any


@dataclass(slots=True)
class Fact:
    source_type: str
    source_name: str
    relation: str
    target_type: str
    target_name: str
    evidence: str = ""

    def to_dict(self) -> dict[str, str]:
        return asdict(self)


@dataclass(slots=True)
class ContentAnalysis:
    keep: bool
    importance: float
    summary: str
    facts: list[Fact] = field(default_factory=list)
    reason: str = ""


@dataclass(slots=True)
class RecallItem:
    id: str
    content: str
    score: float
    importance: float
    created_at: str
    layer: str

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(slots=True)
class ChatResult:
    answer: str
    session_id: str
    short_recall: list[RecallItem]
    long_recall: list[dict[str, Any]]
    encoded: bool
    importance: float

    def to_dict(self) -> dict[str, Any]:
        return {
            "answer": self.answer,
            "session_id": self.session_id,
            "memory": {
                "encoded": self.encoded,
                "importance": round(self.importance, 3),
                "short_recall": [item.to_dict() for item in self.short_recall],
                "long_recall": self.long_recall,
            },
        }
