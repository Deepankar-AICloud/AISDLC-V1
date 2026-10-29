"""QC failure diagnosis (Priority 3).

On a QC FAIL the orchestrator diagnoses the likely cause and chooses an action,
rather than assuming every failure needs a stronger model.

Causes:   validation | ambiguous_requirement | prompt_context | model_capability
Actions:  RETRY_CURRENT_MODEL | IMPROVE_CONTEXT | REQUEST_HUMAN_INFO
          | ESCALATE_MODEL | HUMAN_INTERVENTION
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

RETRY_CURRENT = "RETRY_CURRENT_MODEL"
IMPROVE_CONTEXT = "IMPROVE_CONTEXT"
REQUEST_HUMAN_INFO = "REQUEST_HUMAN_INFO"
ESCALATE_MODEL = "ESCALATE_MODEL"
HUMAN = "HUMAN_INTERVENTION"

_FABRICATION = ("fabricat", "unsupported", "hallucinat", "invented", "not in the source")
_VALIDATION = ("missing required", "no ids", "duplicate id", "mermaid",
               "traceability", "section", "required output", "prefix")


@dataclass
class Diagnosis:
    cause: str
    action: str
    rationale: str
    questions: list[str] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return self.__dict__.copy()


def diagnose(qc: Any, *, retries: int, gated: bool,
             escalate_after: int = 1) -> Diagnosis:
    """Decide what to do after a QC failure. `gated` = model is fixed (can't escalate)."""
    issues = " ".join(list(getattr(qc, "critical_issues", []))
                      + list(getattr(qc, "warnings", []))).lower()

    # Possible fabricated / unsupported content -> ask a human, do not auto-retry.
    if any(k in issues for k in _FABRICATION):
        return Diagnosis(
            "ambiguous_requirement", REQUEST_HUMAN_INFO,
            "Artifact may contain fabricated/unsupported content.",
            questions=["Confirm the disputed requirements — the artifact may "
                       "contain unsupported or invented content."],
        )

    # Structural/validation failures: fixable by regenerating with feedback.
    if any(k in issues for k in _VALIDATION):
        if retries < escalate_after:
            return Diagnosis("validation", IMPROVE_CONTEXT,
                             "Structural gaps; regenerate with QC feedback.")
        return Diagnosis("validation", HUMAN if gated else ESCALATE_MODEL,
                         "Repeated structural failures." if not gated else
                         "Repeated structural failures and the model is fixed.")

    # Unknown cause.
    if retries >= escalate_after:
        return Diagnosis("model_capability", HUMAN if gated else ESCALATE_MODEL,
                         "Repeated failure of unclear cause.")
    return Diagnosis("prompt_context", RETRY_CURRENT,
                     "Retry with the same model and refined context.")
