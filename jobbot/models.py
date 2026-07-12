from __future__ import annotations

from dataclasses import dataclass, field


@dataclass(frozen=True)
class Job:
    id: str
    title: str
    company: str
    url: str
    date_text: str = ""
    deadline: str = ""
    summary: str = ""
    description: str = ""

    @property
    def full_text(self) -> str:
        return "\n".join(
            part
            for part in [self.title, self.company, self.summary, self.description]
            if part
        )


@dataclass(frozen=True)
class Classification:
    label: str
    confidence: int
    reason: str
    matched_concepts: list[str] = field(default_factory=list)
    source: str = "heuristic"

    @property
    def should_notify(self) -> bool:
        return self.label in {"HIGH_MATCH", "MAYBE_MATCH"}
