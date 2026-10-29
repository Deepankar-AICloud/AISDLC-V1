"""Model decision resolution and audit.

Turns a ModelRecommendation + selection mode (+ optional human choice) into a
concrete ModelDecision, and records a traceable audit entry. Keeps MODEL
CONFIRMATION (before generation) separate from ARTIFACT APPROVAL (after QC).
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Optional

from ..common.logging_util import now_iso
from . import ModelRecommendation


@dataclass
class ModelDecision:
    artifact: str
    agent: str
    recommended_model: str
    selected_model: str
    selected_provider: str
    selection_source: str          # router_recommendation | human_override | automatic | manual_selection
    override_reason: Optional[str] = None
    timestamp: str = field(default_factory=now_iso)

    def to_dict(self) -> dict[str, Any]:
        return self.__dict__.copy()


def resolve(
    recommendation: ModelRecommendation,
    *,
    agent: str,
    mode: str,
    human_selected: Optional[str] = None,
    override_reason: Optional[str] = None,
) -> tuple[Optional[ModelDecision], bool]:
    """Resolve the model to use.

    Returns (decision, proceed). proceed=False means the workflow must PAUSE
    and wait for a human model confirmation/selection.
    """
    rec_model = recommendation.recommended.model
    rec_provider = recommendation.recommended.provider
    mode = (mode or "RECOMMENDED").upper()

    def _decide(model: str, source: str) -> ModelDecision:
        prov = rec_provider  # provider stays within the configured provider
        return ModelDecision(
            artifact=recommendation.artifact,
            agent=agent,
            recommended_model=rec_model,
            selected_model=model,
            selected_provider=prov,
            selection_source=source,
            override_reason=override_reason if model != rec_model else None,
        )

    if mode == "AUTO":
        return _decide(rec_model, "automatic"), True

    if mode == "MANUAL":
        if human_selected:
            src = "human_override" if human_selected != rec_model else "manual_selection"
            return _decide(human_selected, src), True
        return None, False  # must wait for an explicit human pick

    # RECOMMENDED (default)
    if not recommendation.confirmation_required:
        return _decide(rec_model, "router_recommendation"), True
    if human_selected is not None:
        src = "human_override" if human_selected != rec_model else "router_recommendation"
        return _decide(human_selected, src), True
    return None, False  # pause for confirmation
