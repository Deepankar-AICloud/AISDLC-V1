"""Report Generator.

Produces the per-run reports (model-cost, quality, workflow) and a GitHub
Actions Job Summary. Cost figures are clearly labeled actual | estimated |
unavailable and are never presented as provider billing.
"""
from __future__ import annotations

import os
from pathlib import Path

from .common.config import run_reports_dir
from .telemetry import Telemetry


def _model_cost_report(tel: Telemetry) -> str:
    lines = [
        "# Model / Token / Cost Report",
        "",
        "> Costs are **estimated** from `config/pricing.yml` and are not provider billing.",
        "",
        "| Stage | Agent | Artifact | Req Model | Actual Model | In Tok | Out Tok | "
        "Cached | In $ | Out $ | Cache $ | Total $ | QC | Retry | Status | Source |",
        "|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|",
    ]
    for r in tel.records:
        lines.append(
            f"| {r.stage} | {r.agent} | {r.artifact} | {r.requested_model} | "
            f"{r.actual_model} | {r.input_tokens if r.input_tokens is not None else 'N/A'} | "
            f"{r.output_tokens if r.output_tokens is not None else 'N/A'} | "
            f"{r.cached_input_tokens if r.cached_input_tokens is not None else 'N/A'} | "
            f"{r.input_cost if r.input_cost is not None else 'N/A'} | "
            f"{r.output_cost if r.output_cost is not None else 'N/A'} | "
            f"{r.cache_cost if r.cache_cost is not None else 'N/A'} | "
            f"{r.total_cost if r.total_cost is not None else 'N/A'} | "
            f"{r.qc_score if r.qc_score is not None else 'N/A'} | {r.retry_count} | "
            f"{r.status} | {r.usage_source} |"
        )
    totals = tel.totals()
    lines += [
        "",
        "## Totals",
        f"- Invocations: {totals['invocations']}",
        f"- Total input tokens: {totals['total_input_tokens']}",
        f"- Total output tokens: {totals['total_output_tokens']}",
        f"- Total cached tokens: {totals['total_cached_tokens']}",
        f"- Total tokens: {totals['total_tokens']}",
        f"- Total estimated cost (USD): {totals['total_estimated_cost']} "
        f"(basis: {totals['cost_basis']})",
    ]
    return "\n".join(lines) + "\n"


def _quality_report(tel: Telemetry) -> str:
    lines = ["# Quality Report", "", "| Stage | Agent | QC Score | Status | Retry |",
             "|---|---|---|---|---|"]
    for r in tel.records:
        lines.append(
            f"| {r.stage} | {r.agent} | "
            f"{r.qc_score if r.qc_score is not None else 'N/A'} | {r.status} | {r.retry_count} |"
        )
    scored = [r.qc_score for r in tel.records if r.qc_score is not None]
    avg = round(sum(scored) / len(scored), 1) if scored else "N/A"
    lines += ["", f"**Average QC score:** {avg}"]
    return "\n".join(lines) + "\n"


def _workflow_report(run_id: str, tel: Telemetry) -> str:
    lines = [
        "# Workflow Report",
        "",
        f"Run: `{run_id}`",
        "",
        "| Stage | Agent | Status | QC | Retry |",
        "|---|---|---|---|---|",
    ]
    for r in tel.records:
        lines.append(f"| {r.stage} | {r.agent} | {r.status} | "
                     f"{r.qc_score if r.qc_score is not None else 'N/A'} | {r.retry_count} |")
    return "\n".join(lines) + "\n"


def _model_decision_report(run_id: str, tel: Telemetry) -> str:
    lines = [
        "# Final Model Decision Report",
        "",
        f"Run: `{run_id}`",
        "",
        "| Stage | Artifact | Recommended | Selected | Source | Override | "
        "In Tok | Out Tok | Cost | QC | Retry | Result |",
        "|---|---|---|---|---|---|---|---|---|---|---|---|",
    ]
    overrides = 0
    for r in tel.records:
        if r.selection_source == "human_override":
            overrides += 1
        lines.append(
            f"| {r.stage} | {r.artifact} | {r.recommended_model or 'N/A'} | "
            f"{r.selected_model or r.actual_model} | {r.selection_source or 'N/A'} | "
            f"{r.override_reason or '—'} | "
            f"{r.input_tokens if r.input_tokens is not None else 'N/A'} | "
            f"{r.output_tokens if r.output_tokens is not None else 'N/A'} | "
            f"{r.total_cost if r.total_cost is not None else 'N/A'} | "
            f"{r.qc_score if r.qc_score is not None else 'N/A'} | {r.retry_count} | {r.status} |"
        )

    # Summaries only where comparable data exists (no invented rankings).
    models = [r.selected_model or r.actual_model for r in tel.records]
    most_used = max(set(models), key=models.count) if models else "N/A"
    escalations = sum(1 for r in tel.records if r.retry_count and r.retry_count > 0)
    lines += [
        "",
        "## Summary",
        f"- Most used model: {most_used}",
        f"- Model overrides: {overrides}",
        f"- Stages with retries/escalation: {escalations}",
        "- Highest quality / most cost-efficient model: "
        "Not enough comparable data" if len(set(models)) <= 1 else
        f"- Models used: {', '.join(sorted(set(models)))}",
        "",
        "> Token/cost figures are ESTIMATED or N/A where the provider does not "
        "report usage (Copilot CLI). Never presented as actual billing.",
    ]
    return "\n".join(lines) + "\n"


def write_reports(run_id: str, tel: Telemetry) -> dict[str, Path]:
    out = run_reports_dir(run_id)
    paths = {
        "model_cost": out / "model-cost-report.md",
        "quality": out / "quality-report.md",
        "workflow": out / "workflow-report.md",
        "model_decision": out / "model-decision-report.md",
    }
    paths["model_cost"].write_text(_model_cost_report(tel), encoding="utf-8")
    paths["quality"].write_text(_quality_report(tel), encoding="utf-8")
    paths["workflow"].write_text(_workflow_report(run_id, tel), encoding="utf-8")
    paths["model_decision"].write_text(_model_decision_report(run_id, tel), encoding="utf-8")

    # GitHub Actions Job Summary.
    summary_file = os.environ.get("GITHUB_STEP_SUMMARY")
    if summary_file:
        with open(summary_file, "a", encoding="utf-8") as fh:
            fh.write(f"## Agentic SDLC — run `{run_id}`\n\n")
            fh.write(_model_cost_report(tel))
    return paths
