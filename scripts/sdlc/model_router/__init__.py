"""Model Router — resolves an agent capability request to a concrete model.

Reads ``config/models.yml``. Agents pass a capability dict
(``task_type``/``complexity``/``reasoning``/``coding``); the router picks a
tier via ordered routing rules, returning preferred + fallback models and the
selection reason. Supports escalation on repeated QC failure.

It also produces a human-facing RECOMMENDATION (``recommend``) with
alternatives, estimates (clearly labeled ESTIMATE / N/A), and historical
signal — never fabricating cost, token, quality, or latency values.
"""
from __future__ import annotations

import os
from dataclasses import dataclass, field
from typing import Any, Optional

from ..common.config import load_config, models_config, pricing_config
from . import history as model_history

_LEVEL = {"none": 0, "low": 1, "medium": 2, "high": 3}


@dataclass
class ModelChoice:
    provider: str
    model: str
    tier: str
    selection_reason: str
    fallback_provider: Optional[str] = None
    fallback_model: Optional[str] = None


@dataclass
class ModelAlternative:
    provider: str
    model: str
    tier: str
    profile: str
    history: Optional[dict[str, Any]] = None


@dataclass
class ModelRecommendation:
    artifact: str
    capability: dict[str, Any]
    recommended: ModelChoice
    alternatives: list[ModelAlternative]
    reason: str
    quality_target: Optional[int]
    estimates: dict[str, Any]
    confirmation_required: bool
    selection_mode: str
    history: Optional[dict[str, Any]] = None

    def to_dict(self) -> dict[str, Any]:
        return {
            "artifact": self.artifact,
            "capability": self.capability,
            "recommended_model": self.recommended.model,
            "recommended_provider": self.recommended.provider,
            "tier": self.recommended.tier,
            "reason": self.reason,
            "quality_target": self.quality_target,
            "estimates": self.estimates,
            "confirmation_required": self.confirmation_required,
            "selection_mode": self.selection_mode,
            "history": self.history,
            "alternatives": [
                {"model": a.model, "provider": a.provider, "tier": a.tier,
                 "profile": a.profile, "history": a.history}
                for a in self.alternatives
            ],
        }


def selection_mode(agent_key: Optional[str] = None) -> str:
    """Current model-selection mode.

    Precedence: MODEL_SELECTION_MODE env (testing) > per-artifact
    `selection_modes` > global `model_selection_mode`.
    """
    env = os.environ.get("MODEL_SELECTION_MODE")
    if env:
        return env.strip().upper()
    cfg = models_config()
    if agent_key:
        per = cfg.get("selection_modes", {}).get(agent_key)
        if per:
            return str(per).upper()
    return str(cfg.get("model_selection_mode", "RECOMMENDED")).upper()


def confirmation_required(agent_key: str) -> bool:
    return bool(models_config().get("confirmation_gates", {}).get(agent_key, False))


def _level(value: str | None) -> int:
    return _LEVEL.get((value or "none").lower(), 0)



def _rule_matches(match: dict[str, Any], capability: dict[str, Any]) -> bool:
    for key, required in match.items():
        if _level(capability.get(key)) < _level(required):
            return False
    return True


def select_model(
    capability: dict[str, Any],
    *,
    qc_fail_count: int = 0,
) -> ModelChoice:
    cfg = models_config()
    tiers: dict[str, Any] = cfg.get("tiers", {})
    routing: list[dict[str, Any]] = cfg.get("routing", [])

    chosen_tier = "tier1_low"
    reason = "default tier"
    for rule in routing:
        if _rule_matches(rule.get("match", {}), capability):
            chosen_tier = rule["tier"]
            reason = f"matched routing rule {rule.get('match')}"
            break

    # Escalation on repeated QC failure.
    esc = cfg.get("escalation", {})
    if esc.get("enabled") and qc_fail_count >= esc.get("on_qc_fail_count", 1):
        order: list[str] = esc.get("order", [])
        if chosen_tier in order:
            idx = min(order.index(chosen_tier) + qc_fail_count, len(order) - 1)
            if order[idx] != chosen_tier:
                reason = (
                    f"escalated {chosen_tier} -> {order[idx]} "
                    f"after {qc_fail_count} QC failure(s)"
                )
                chosen_tier = order[idx]

    tier = tiers.get(chosen_tier, {})
    preferred = tier.get("preferred", {})
    fallback = tier.get("fallback", {})
    return ModelChoice(
        provider=preferred.get("provider", "copilot"),
        model=preferred.get("model", "gpt-4o"),
        tier=chosen_tier,
        selection_reason=reason,
        fallback_provider=fallback.get("provider"),
        fallback_model=fallback.get("model"),
    )


def _estimate_usage(model: str, context_len: Optional[int]) -> dict[str, Any]:
    """Rough pre-generation ESTIMATE. Never presented as actual usage."""
    rate = pricing_config().get("models", {}).get(model)
    # ~4 chars/token heuristic for the prompt; output size is not knowable.
    in_tokens = int(context_len / 4) if context_len else None
    in_cost = None
    if in_tokens is not None and rate and rate.get("input") is not None:
        in_cost = round(in_tokens / 1_000_000 * rate["input"], 6)
    return {
        "estimated_input_tokens": in_tokens if in_tokens is not None else "N/A",
        "estimated_output_tokens": "Unknown",
        "estimated_cached_tokens": "N/A",
        "estimated_input_cost": in_cost if in_cost is not None else "N/A",
        "estimated_output_cost": "Unknown",
        "estimated_total_cost": "N/A (partial — output unknown)",
        "cost_type": "ESTIMATED",
        "pricing_basis": "config/pricing.yml" if rate else "unavailable",
    }


def recommend(
    capability: dict[str, Any],
    *,
    artifact: str,
    agent_key: str,
    quality_target: Optional[int] = None,
    qc_fail_count: int = 0,
    context_len: Optional[int] = None,
) -> ModelRecommendation:
    """Produce a human-facing model recommendation for an artifact."""
    cfg = models_config()
    tiers: dict[str, Any] = cfg.get("tiers", {})
    weights = load_config("model-routing").get("weights", {})

    choice = select_model(capability, qc_fail_count=qc_fail_count)
    hist = model_history.get(artifact, choice.model)

    # Build alternatives from the other tiers.
    alternatives: list[ModelAlternative] = []
    for tier_name, tier in tiers.items():
        pref = tier.get("preferred", {})
        if pref.get("model") and pref["model"] != choice.model:
            alternatives.append(ModelAlternative(
                provider=pref.get("provider", "copilot"),
                model=pref["model"],
                tier=tier_name,
                profile=tier.get("profile", "Unknown profile"),
                history=model_history.get(artifact, pref["model"]),
            ))

    qw = weights.get("quality_weight", "?")
    cw = weights.get("cost_weight", "?")
    reason = (
        f"{choice.tier} ({choice.model}) best fits '{artifact}' capability "
        f"(reasoning={capability.get('reasoning', 'none')}, "
        f"coding={capability.get('coding', 'none')}, "
        f"complexity={capability.get('complexity', 'none')}); "
        f"optimizing quality(w={qw}) vs cost(w={cw})."
    )
    if hist:
        reason += (f" Historical {artifact} on {choice.model}: "
                   f"avg QC {hist.get('avg_qc')}, retry rate {hist.get('retry_rate')} "
                   f"over {hist.get('runs')} run(s).")
    else:
        reason += " No sufficient historical data yet."

    return ModelRecommendation(
        artifact=artifact,
        capability=capability,
        recommended=choice,
        alternatives=alternatives,
        reason=reason,
        quality_target=quality_target,
        estimates=_estimate_usage(choice.model, context_len),
        confirmation_required=confirmation_required(agent_key),
        selection_mode=selection_mode(),
        history=hist,
    )

