"""Release Evidence Pack generator (Priority 10).

Assembles a per-release evidence pack from the run's reports, workflow state,
and deployment inputs. Produces reports/<run-id>/release-evidence.(md|json).
Values that are not available are shown as N/A — never fabricated.
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any, Optional

from .common.config import run_reports_dir
from .orchestrator.state_store import load_state


def _read_json(path: Path) -> Optional[Any]:
    if path.exists():
        try:
            return json.loads(path.read_text(encoding="utf-8"))
        except (json.JSONDecodeError, OSError):
            return None
    return None


def build(run_id: str, *, issue: Optional[int] = None, commit_sha: str = "N/A",
          deployment_result: str = "N/A", health_result: str = "N/A") -> dict[str, Path]:
    out = run_reports_dir(run_id)
    usage = _read_json(out / "usage.json") or []
    graph = _read_json(out / "traceability-graph.json") or {}
    state = load_state(issue, run_id) if issue is not None else None

    artifacts = state.artifacts if state else {}
    approvals = state.human_reviews if state else {}
    model_decisions = state.model_decisions if state else []
    overrides = [d for d in model_decisions if d.get("selection_source") == "human_override"]

    qc_scores = {r.get("artifact"): r.get("qc_score") for r in usage if r.get("qc_score") is not None}
    models_used = sorted({r.get("selected_model") or r.get("actual_model") for r in usage if r.get("actual_model")})
    totals_tokens = sum((r.get("total_tokens") or 0) for r in usage)
    totals_cost = round(sum((r.get("total_cost") or 0) for r in usage), 6)

    evidence: dict[str, Any] = {
        "run_id": run_id,
        "issue": issue,
        "commit_sha": commit_sha,
        "requirement_coverage": graph.get("queries", {}),
        "approved_artifacts": artifacts,
        "human_approvals": approvals,
        "qc_scores": qc_scores,
        "models_used": models_used,
        "model_overrides": overrides,
        "token_usage_total": totals_tokens or "N/A",
        "llm_cost_total_estimated": totals_cost or "N/A",
        "tests": {"unit": "N/A", "integration": "N/A", "functional": "N/A",
                  "performance": "N/A"},
        "security": {"sast": "N/A", "dast": "N/A", "dependencies": "N/A",
                     "secret_scan": "N/A"},
        "deployment_result": deployment_result,
        "production_health_result": health_result,
        "overall": ("DEPLOYED_AND_VERIFIED"
                    if deployment_result == "success" and health_result == "healthy"
                    else "NOT_VERIFIED"),
    }

    js = out / "release-evidence.json"
    js.write_text(json.dumps(evidence, indent=2), encoding="utf-8")

    md = out / "release-evidence.md"
    lines = [
        "# Release Evidence Pack",
        "",
        f"- **Run ID:** `{run_id}`",
        f"- **Issue:** {issue}",
        f"- **Commit SHA:** {commit_sha}",
        f"- **Overall:** **{evidence['overall']}**",
        "",
        "## Requirement coverage",
        f"- Requirements: {graph.get('queries', {}).get('requirement_count', 'N/A')}",
        f"- Requirements without tests: "
        f"{graph.get('queries', {}).get('requirements_without_tests', 'N/A')}",
        f"- Stories without requirements: "
        f"{graph.get('queries', {}).get('stories_without_requirements', 'N/A')}",
        "",
        "## Approved artifacts",
        *([f"- {k}: {v}" for k, v in artifacts.items()] or ["- (none)"]),
        "",
        "## Models & QC",
        f"- Models used: {', '.join(models_used) or 'N/A'}",
        f"- Model overrides: {len(overrides)}",
        f"- QC scores: {qc_scores or 'N/A'}",
        "",
        "## Tests & Security",
        "- Unit / Integration / Functional / Performance: N/A (link CI runs)",
        "- SAST / DAST / Dependencies / Secret scan: N/A (link security runs)",
        "",
        "## Deployment",
        f"- Deployment result: {deployment_result}",
        f"- Production health: {health_result}",
        "",
        "> Token/cost figures are estimated or N/A where unavailable; tests and "
        "security results should be linked from their CI/CD runs.",
    ]
    md.write_text("\n".join(lines) + "\n", encoding="utf-8")
    return {"md": md, "json": js}


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(description="Build the Release Evidence Pack")
    p.add_argument("--run-id", required=True)
    p.add_argument("--issue", type=int, default=None)
    p.add_argument("--commit-sha", default="N/A")
    p.add_argument("--deployment-result", default="N/A")
    p.add_argument("--health-result", default="N/A")
    args = p.parse_args(argv)
    paths = build(args.run_id, issue=args.issue, commit_sha=args.commit_sha,
                  deployment_result=args.deployment_result, health_result=args.health_result)
    print(json.dumps({"release_evidence_md": str(paths["md"]),
                      "release_evidence_json": str(paths["json"])}, indent=2))
    return 0


if __name__ == "__main__":
    sys.exit(main())
