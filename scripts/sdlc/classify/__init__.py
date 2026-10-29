"""Fact / Assumption / Inference classification (Priority 1 support).

Deterministic, lightweight classification so agents never silently promote an
assumption into an approved customer requirement. Used to annotate readiness
output and the PR AI-generation summary.

Classes: FACT | ASSUMPTION | INFERENCE | MISSING_INFORMATION.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Optional

FACT = "FACT"
ASSUMPTION = "ASSUMPTION"
INFERENCE = "INFERENCE"
MISSING = "MISSING_INFORMATION"

_ASSUMPTION_HINTS = ("assume", "probably", "likely", "should be", "expected", "default", "typical")
_INFERENCE_HINTS = ("therefore", "implies", "so ", "hence", "because", "based on")


@dataclass
class Classification:
    statement: str
    classification: str
    source: Optional[str] = None
    confidence: str = "LOW"
    requires_human_confirmation: bool = False

    def to_dict(self) -> dict[str, Any]:
        return self.__dict__.copy()


def classify_statement(statement: str, *, present_in_source: bool,
                       source: Optional[str] = None) -> Classification:
    s = statement.lower()
    if present_in_source:
        return Classification(statement, FACT, source=source, confidence="HIGH")
    if any(h in s for h in _ASSUMPTION_HINTS):
        return Classification(statement, ASSUMPTION, confidence="LOW",
                              requires_human_confirmation=True)
    if any(h in s for h in _INFERENCE_HINTS):
        return Classification(statement, INFERENCE, confidence="MEDIUM",
                              requires_human_confirmation=True)
    return Classification(statement, MISSING, confidence="LOW",
                          requires_human_confirmation=True)


def from_readiness(readiness: Any) -> list[dict[str, Any]]:
    """Build a classification list from a ReadinessResult."""
    items: list[Classification] = []
    for p in getattr(readiness, "present", []):
        items.append(Classification(p, FACT, source="context", confidence="HIGH"))
    for a in getattr(readiness, "assumptions", []):
        items.append(Classification(a, ASSUMPTION, confidence="LOW",
                                    requires_human_confirmation=True))
    for m in getattr(readiness, "missing_mandatory", []):
        items.append(Classification(m, MISSING, confidence="LOW",
                                    requires_human_confirmation=True))
    return [c.to_dict() for c in items]
