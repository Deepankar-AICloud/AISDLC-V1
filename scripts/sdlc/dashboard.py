"""Dashboard data model (Priority 10 / section 26).

Consolidates per-run metrics into a single reports/<run-id>/dashboard.json that
a future dashboard can render. Builds only from real run data; missing values
are 'N/A', never fabricated.
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any, Optional

from .common.config import run_reports_dir
from .orchestrator.state_store import load_state


def _read_json(path: Path) -> Any:
    if path.exists():
        try:
            return json.loads(path.read_text(encoding="utf-8"))
        except (json.JSONDecodeError, OSError):
            return None
    return None


def build(run_id: str, issue: Optional[int] = None) -> Path:
    out = run_reports_dir(run_id)
    usage = _read_json(out / "usage.json") or []
    graph = _read_json(out / "traceability-graph.json") or {}
    state = load_state(issue, run_id) if issue is not None else None

    qc_scores = [r.get("qc_score") for r in usage if r.get("qc_score") is not None]
    avg_qc = round(sum(qc_scores) / len(qc_scores), 1) if qc_scores else "N/A"
    retries = sum((r.get("retry_count") or 0) for r in usage)
    overrides = sum(1 for r in usage if r.get("selection_source") == "human_override")
    models = sorted({r.get("selected_model") or r.get("actual_model") for r in usage if r.get("actual_model")})

    # Highest token/cost stage.
    def _stage_key(k: str):
        best, val = "N/A", -1
        for r in usage:
            v = r.get(k) or 0
            if v > val:
                best, val = r.get("stage"), v
        return best if val > 0 else "N/A"

    dashboard: dict[str, Any] = {
        "run_id": run_id,
        "issue": issue,
        "overall_status": state.current_state if state else "N/A",
        "current_stage": state.current_state if state else "N/A",
        "artifact_quality_avg": avg_qc,
        "requirement_coverage": graph.get("queries", {}),
        "human_approvals": state.human_reviews if state else {},
        "human_review_cycles": sum((state.human_reviews or {}).values()) if state else 0,
        "ai_retries": retries,
        "model_overrides": overrides,
        "models_used": models,
        "token_usage_total": sum((r.get("total_tokens") or 0) for r in usage) or "N/A",
        "llm_cost_total_estimated": round(sum((r.get("total_cost") or 0) for r in usage), 6) or "N/A",
        "highest_token_stage": _stage_key("total_tokens"),
        "highest_cost_stage": _stage_key("total_cost"),
        "readiness": state.readiness if state else {},
        "assumptions": state.assumptions if state else {},
    }
    path = out / "dashboard.json"
    path.write_text(json.dumps(dashboard, indent=2), encoding="utf-8")
    return path


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(description="Build the dashboard data model")
    p.add_argument("--run-id", required=True)
    p.add_argument("--issue", type=int, default=None)
    args = p.parse_args(argv)
    path = build(args.run_id, args.issue)
    print(json.dumps({"dashboard_json": str(path)}, indent=2))
    return 0


if __name__ == "__main__":
    sys.exit(main())
