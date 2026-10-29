"""Generation Readiness Gate (Priority 1).

Before a major artifact is generated the orchestrator checks that the required
inputs are present. Detection is deterministic: keyword presence in the supplied
context plus presence of approved upstream artifacts. Missing MANDATORY info or
upstream => BLOCKED (never invent it). Missing OPTIONAL info => proceed but mark
ASSUMPTIONS.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Iterable

from ..common.config import load_config

READY = "READY"
READY_WITH_ASSUMPTIONS = "READY_WITH_ASSUMPTIONS"
BLOCKED = "BLOCKED_MISSING_INFORMATION"


@dataclass
class ReadinessResult:
    agent: str
    status: str
    present: list[str] = field(default_factory=list)
    missing_mandatory: list[str] = field(default_factory=list)
    missing_upstream: list[str] = field(default_factory=list)
    assumptions: list[str] = field(default_factory=list)
    questions: list[str] = field(default_factory=list)

    @property
    def blocked(self) -> bool:
        return self.status == BLOCKED

    def to_dict(self) -> dict[str, Any]:
        return self.__dict__.copy()


def _config() -> dict[str, Any]:
    return load_config("readiness")


def evaluate(agent_key: str, context: str, artifacts_present: Iterable[str]) -> ReadinessResult:
    cfg = _config()
    present_set = set(artifacts_present)
    res = ReadinessResult(agent=agent_key, status=READY)

    if not cfg.get("enabled", True):
        return res

    art = cfg.get("artifacts", {}).get(agent_key)
    if not art:
        return res  # no requirements configured => ready

    ctx = (context or "").lower()
    defaults = cfg.get("defaults", {})

    # Trivially short requirements block (only applies where mandatory items exist).
    min_chars = int(defaults.get("min_context_chars", 0))
    mandatory: dict[str, list[str]] = art.get("mandatory") or {}
    if mandatory and min_chars and len((context or "").strip()) < min_chars:
        res.missing_mandatory.append("sufficient_requirement_detail")
        res.questions.append("The requirement is too short — add more detail.")

    for item, kws in mandatory.items():
        if any(k in ctx for k in kws):
            res.present.append(item)
        else:
            res.missing_mandatory.append(item)
            res.questions.append(f"Please provide: {item.replace('_', ' ')}.")

    for item, kws in (art.get("optional") or {}).items():
        if any(k in ctx for k in kws):
            res.present.append(item)
        else:
            res.assumptions.append(item)

    for upstream in art.get("upstream", []) or []:
        if upstream in present_set:
            res.present.append(f"approved_{upstream}")
        else:
            res.missing_upstream.append(upstream)
            res.questions.append(f"Upstream artifact '{upstream}' is not yet approved.")

    if res.missing_mandatory or res.missing_upstream:
        res.status = BLOCKED
    elif res.assumptions:
        res.status = READY_WITH_ASSUMPTIONS
    else:
        res.status = READY
    return res
