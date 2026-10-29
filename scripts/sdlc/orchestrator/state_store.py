"""Durable state store.

Persists workflow state to ``.sdlc/state.json`` so GitHub Actions jobs can stop
while awaiting human approval and resume later. One state document per run,
keyed by the originating issue number.
"""
from __future__ import annotations

import json
from dataclasses import asdict, dataclass, field
from typing import Any, Optional

from ..common.config import STATE_DIR
from ..common.logging_util import now_iso


@dataclass
class WorkflowState:
    run_id: str
    issue_number: Optional[int]
    current_state: str
    retries: dict[str, int] = field(default_factory=dict)
    artifacts: dict[str, str] = field(default_factory=dict)  # stage -> path
    prs: dict[str, int] = field(default_factory=dict)        # stage -> PR number
    human_reviews: dict[str, int] = field(default_factory=dict)
    # Model recommendation / confirmation (separate from artifact approval).
    selected_models: dict[str, str] = field(default_factory=dict)   # agent -> model
    model_overrides: dict[str, str] = field(default_factory=dict)   # agent -> reason
    pending_model_confirmation: Optional[dict[str, Any]] = None
    model_decisions: list[dict[str, Any]] = field(default_factory=list)
    # Readiness gate (Priority 1).
    pending_information: Optional[dict[str, Any]] = None
    readiness: dict[str, str] = field(default_factory=dict)       # agent -> status
    assumptions: dict[str, list[str]] = field(default_factory=dict)  # agent -> items
    history: list[dict[str, Any]] = field(default_factory=list)
    updated_at: str = field(default_factory=now_iso)

    def transition(self, new_state: str, note: str = "") -> None:
        self.history.append(
            {"from": self.current_state, "to": new_state,
             "at": now_iso(), "note": note}
        )
        self.current_state = new_state
        self.updated_at = now_iso()


def _path(issue_number: Optional[int], run_id: str) -> "Any":
    STATE_DIR.mkdir(parents=True, exist_ok=True)
    key = f"issue-{issue_number}" if issue_number is not None else run_id
    return STATE_DIR / f"{key}.json"


def load_state(issue_number: Optional[int], run_id: str) -> Optional[WorkflowState]:
    path = _path(issue_number, run_id)
    if not path.exists():
        return None
    data = json.loads(path.read_text(encoding="utf-8"))
    return WorkflowState(**data)


def save_state(state: WorkflowState) -> None:
    path = _path(state.issue_number, state.run_id)
    path.write_text(json.dumps(asdict(state), indent=2), encoding="utf-8")
