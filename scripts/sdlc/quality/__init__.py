"""Quality Control / Evaluator.

Combines DETERMINISTIC checks (section presence, ID prefixes, build/test
signals) with optional SEMANTIC LLM scoring. A generator never scores its own
output as PASS — this module is invoked independently by the orchestrator.

Produces the structured scorecard from prompt section 16.
"""
from __future__ import annotations

import json
import re
from dataclasses import dataclass, field
from typing import Any, Optional

from ..common.config import models_config, quality_gates_config
from ..common.llm import run_llm
from ..model_router import select_model


@dataclass
class QCResult:
    artifact: str
    overall_score: float
    threshold: float
    status: str  # PASS | FAIL
    dimensions: dict[str, float] = field(default_factory=dict)
    critical_issues: list[str] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)
    recommendations: list[str] = field(default_factory=list)

    def to_json(self) -> str:
        return json.dumps(self.__dict__, indent=2)


def _gate(artifact: str) -> dict[str, Any]:
    gates = quality_gates_config().get("gates", {})
    defaults = quality_gates_config().get("defaults", {})
    gate = dict(gates.get(artifact, {}))
    gate.setdefault("threshold", defaults.get("threshold", 90))
    gate.setdefault("dimensions", ["completeness", "clarity", "consistency"])
    return gate


def _deterministic(content: str, gate: dict[str, Any]) -> tuple[list[str], list[str]]:
    """Return (critical_issues, warnings) from deterministic checks."""
    critical: list[str] = []
    warnings: list[str] = []
    for check in gate.get("deterministic_checks", []):
        if "requires_sections" in check:
            for section in check["requires_sections"]:
                if section.lower() not in content.lower():
                    critical.append(f"Missing required section: '{section}'")
        if "requires_ids_prefixed" in check:
            for prefix in check["requires_ids_prefixed"]:
                if not re.search(rf"\b{re.escape(prefix)}\d", content):
                    critical.append(f"No IDs with required prefix '{prefix}'")
        if check.get("requires_mermaid") and "```mermaid" not in content:
            critical.append("Expected at least one Mermaid diagram")
        if "requires_traceability_to" in check:
            target = check["requires_traceability_to"]
            if target.lower() not in content.lower():
                warnings.append(f"No visible traceability reference to {target}")
    return critical, warnings


_SEMANTIC_PROMPT = """You are a strict QC evaluator. Score the artifact below.
Return ONLY compact JSON: {{"dimensions": {{<dim>: <0-100>, ...}},
"warnings": [...], "recommendations": [...]}}.
Dimensions to score: {dims}.
Do not invent content. Penalize fabricated/unsupported requirements.

--- ARTIFACT ({artifact}) ---
{content}
--- END ---"""


def _evaluator_choice(generator_model: Optional[str]):
    """Pick an evaluator model that DIFFERS from the generator when possible."""
    choice = select_model({"task_type": "qc", "complexity": "medium",
                           "reasoning": "high", "coding": "none"})
    if not generator_model or choice.model != generator_model:
        return choice.provider, choice.model
    # Same as generator -> use the tier fallback, else a stronger tier.
    if choice.fallback_model and choice.fallback_model != generator_model:
        return choice.fallback_provider or choice.provider, choice.fallback_model
    tier3 = models_config().get("tiers", {}).get("tier3_high", {}).get("preferred", {})
    alt = tier3.get("model")
    if alt and alt != generator_model:
        return tier3.get("provider", choice.provider), alt
    return choice.provider, choice.model  # could not differ; proceed honestly


def _semantic(content: str, artifact: str, gate: dict[str, Any],
              use_llm: bool, generator_model: Optional[str] = None,
              ) -> tuple[dict[str, float], list[str], list[str]]:
    dims: list[str] = gate.get("dimensions", [])
    if not use_llm:
        # Deterministic-only fallback: neutral baseline score.
        return ({d: 85.0 for d in dims}, [], ["LLM scoring skipped (no runner)."])

    provider, model = _evaluator_choice(generator_model)
    prompt = _SEMANTIC_PROMPT.format(
        dims=", ".join(dims), artifact=artifact, content=content[:12000]
    )
    result = run_llm(
        prompt,
        provider=provider,
        requested_model=model,
        actual_model=model,
    )
    if not result.ok:
        return ({d: 85.0 for d in dims}, [], ["LLM scoring unavailable; used baseline."])
    try:
        match = re.search(r"\{.*\}", result.text, re.DOTALL)
        data = json.loads(match.group(0)) if match else {}
        scored = {d: float(data.get("dimensions", {}).get(d, 85.0)) for d in dims}
        return scored, list(data.get("warnings", [])), list(data.get("recommendations", []))
    except (json.JSONDecodeError, ValueError, AttributeError):
        return ({d: 85.0 for d in dims}, ["QC output was not valid JSON."], [])


def evaluate(artifact: str, content: str, *, use_llm: bool = True,
             generator_model: Optional[str] = None) -> QCResult:
    gate = _gate(artifact)
    threshold = float(gate["threshold"])

    critical, det_warnings = _deterministic(content, gate)
    dims, sem_warnings, recs = _semantic(content, artifact, gate, use_llm, generator_model)

    # Deterministic failures force a FAIL regardless of semantic score.
    base = sum(dims.values()) / len(dims) if dims else 0.0
    overall = 0.0 if critical else round(base, 1)
    status = "PASS" if (not critical and overall >= threshold) else "FAIL"

    return QCResult(
        artifact=artifact,
        overall_score=overall,
        threshold=threshold,
        status=status,
        dimensions=dims,
        critical_issues=critical,
        warnings=det_warnings + sem_warnings,
        recommendations=recs,
    )
