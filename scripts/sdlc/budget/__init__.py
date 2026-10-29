"""Budget control (Priority 7).

Checks a pre-generation ESTIMATE and the cumulative run spend against the
configured budgets. Hard budgets are never silently exceeded; unknown/N·A
estimates cannot be evaluated and are allowed through (tracked, not blocked).
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Optional

from ..common.config import load_config


@dataclass
class BudgetDecision:
    ok: bool
    over: list[str]          # which budgets exceeded
    action: str              # proceed | try_cheaper_model | human_decision | block
    rationale: str


def _num(value: Any) -> Optional[float]:
    try:
        return float(value)
    except (TypeError, ValueError):
        return None   # N/A / Unknown -> not evaluable


def check(estimate: dict[str, Any], run_totals: dict[str, Any]) -> BudgetDecision:
    cfg = load_config("budgets")
    if not cfg.get("enabled", True):
        return BudgetDecision(True, [], "proceed", "Budgets disabled.")

    over: list[str] = []
    art = cfg.get("artifact", {})
    wf = cfg.get("workflow", {})

    est_tokens = _num(estimate.get("estimated_input_tokens"))
    est_cost = _num(estimate.get("estimated_total_cost"))

    if art.get("max_tokens") is not None and est_tokens is not None and est_tokens > art["max_tokens"]:
        over.append("artifact.max_tokens")
    if art.get("max_cost_usd") is not None and est_cost is not None and est_cost > art["max_cost_usd"]:
        over.append("artifact.max_cost_usd")

    tot_tokens = _num(run_totals.get("total_tokens"))
    tot_cost = _num(run_totals.get("total_estimated_cost"))
    if wf.get("max_total_tokens") is not None and tot_tokens is not None and tot_tokens > wf["max_total_tokens"]:
        over.append("workflow.max_total_tokens")
    if wf.get("max_total_cost_usd") is not None and tot_cost is not None and tot_cost > wf["max_total_cost_usd"]:
        over.append("workflow.max_total_cost_usd")

    if not over:
        return BudgetDecision(True, [], "proceed", "Within budget (or not evaluable).")

    policy = cfg.get("on_over_budget", {})
    if policy.get("try_cheaper_model", True):
        return BudgetDecision(False, over, "try_cheaper_model",
                              f"Estimated spend exceeds {', '.join(over)}; try a cheaper model.")
    return BudgetDecision(False, over, policy.get("else", "human_decision"),
                          f"Estimated spend exceeds {', '.join(over)}.")
