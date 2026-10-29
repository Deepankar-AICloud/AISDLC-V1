"""CLI entrypoint for the Agentic SDLC orchestrator.

Usage (from repo root):
    python -m scripts.sdlc.run --issue 42 --context-file issue.txt --stage next

Designed to be driven by GitHub Actions. Emits a job-summary-friendly result
to stdout and persists state under .sdlc/.
"""
from __future__ import annotations

import argparse
import json
import os
import sys
from pathlib import Path

from .orchestrator import Orchestrator
from .reporting import write_reports
from .traceability import build_report as build_traceability
from .traceability.graph import build_graph as build_traceability_graph


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Agentic SDLC orchestrator")
    parser.add_argument("--issue", type=int, default=None, help="GitHub issue number")
    parser.add_argument("--context-file", type=str, default=None,
                        help="Path to a file containing the requirement/issue context")
    parser.add_argument("--context", type=str, default="",
                        help="Inline requirement context (used if --context-file absent)")
    parser.add_argument("--run-id", type=str, default=None)
    parser.add_argument("--no-llm", action="store_true",
                        help="Run deterministic pipeline only (no LLM calls)")
    parser.add_argument("--selection-mode", choices=["MANUAL", "RECOMMENDED", "AUTO"],
                        default=None, help="Override model_selection_mode for this run")
    parser.add_argument("--stage", choices=["next"], default="next")
    args = parser.parse_args(argv)

    if args.selection_mode:
        os.environ["MODEL_SELECTION_MODE"] = args.selection_mode

    context = args.context
    if args.context_file and Path(args.context_file).exists():
        context = Path(args.context_file).read_text(encoding="utf-8")

    orch = Orchestrator(issue_number=args.issue, run_id=args.run_id,
                        use_llm=not args.no_llm)
    outcome = orch.run_stage(context)

    build_traceability(orch.run_id)
    build_traceability_graph(orch.run_id)
    write_reports(orch.run_id, orch.telemetry)
    from .dashboard import build as build_dashboard
    build_dashboard(orch.run_id, args.issue)

    summary = {
        "run_id": orch.run_id,
        "issue": args.issue,
        "stage": outcome.stage_state,
        "agent": outcome.agent,
        "status": outcome.status,
        "selection_mode": outcome.selection_mode,
        "qc_score": outcome.qc.overall_score if outcome.qc else None,
        "qc_status": outcome.qc.status if outcome.qc else None,
        "artifact": outcome.artifact_path,
        "next_state": outcome.next_state,
        "human_review": outcome.human_review,
        "retries_used": outcome.retries_used,
        "recommended_model": (outcome.recommendation or {}).get("recommended_model"),
        "selected_model": (outcome.model_decision or {}).get("selected_model"),
        "selection_source": (outcome.model_decision or {}).get("selection_source"),
        "awaiting_model_confirmation": outcome.status == "AWAITING_MODEL_CONFIRMATION",
        "awaiting_required_information": outcome.status == "AWAITING_REQUIRED_INFORMATION",
        "readiness_status": (outcome.readiness or {}).get("status"),
        "readiness": outcome.readiness,
        "contract": outcome.contract,
        "diagnosis": outcome.diagnosis,
        "diagnosis_action": (outcome.diagnosis or {}).get("action"),
        "recommendation": outcome.recommendation,
    }
    print(json.dumps(summary, indent=2))
    # Non-zero exit only on hard block so CI can fail-safe. A pause for model
    # confirmation is NOT a failure.
    return 1 if outcome.status == "BLOCKED" else 0


if __name__ == "__main__":
    sys.exit(main())
