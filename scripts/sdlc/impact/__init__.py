"""Change Impact Analysis + targeted regeneration planning (Priority 4).

When a change or material human feedback arrives, this maps it (deterministically
via config/impact-rules.yml) to the impacted artifacts and sections, so the
orchestrator regenerates ONLY what changed and preserves approved content.
Writes a machine-readable change-impact report.
"""
from __future__ import annotations

import json
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Iterable

from ..common.config import load_config, run_reports_dir

UPDATE = "UPDATE"
NO_CHANGE = "NO_CHANGE"


@dataclass
class ImpactReport:
    change_text: str
    impacts: dict[str, str] = field(default_factory=dict)      # artifact -> UPDATE/NO_CHANGE
    sections: list[str] = field(default_factory=list)
    matched_rules: list[str] = field(default_factory=list)
    rationale: list[str] = field(default_factory=list)

    @property
    def impacted_artifacts(self) -> list[str]:
        return [a for a, v in self.impacts.items() if v == UPDATE]

    def to_dict(self) -> dict[str, Any]:
        return {
            "change_text": self.change_text,
            "impacts": self.impacts,
            "impacted_artifacts": self.impacted_artifacts,
            "sections": self.sections,
            "matched_rules": self.matched_rules,
            "rationale": self.rationale,
        }


def analyze(change_text: str, present: Iterable[str] | None = None) -> ImpactReport:
    cfg = load_config("impact-rules")
    all_artifacts: list[str] = cfg.get("all_artifacts", [])
    text = (change_text or "").lower()
    report = ImpactReport(change_text=change_text or "")

    impacts: dict[str, str] = {a: NO_CHANGE for a in all_artifacts}
    sections: set[str] = set()
    matched_any = False

    for idx, rule in enumerate(cfg.get("rules", [])):
        if any(str(m).lower() in text for m in rule.get("match", [])):
            matched_any = True
            report.matched_rules.append(", ".join(rule.get("match", [])[:3]))
            for art, verdict in rule.get("impacts", {}).items():
                if art in impacts and verdict == UPDATE:
                    impacts[art] = UPDATE
            sections.update(rule.get("sections", []))

    if not matched_any:
        for art, verdict in cfg.get("defaults", {}).get("unknown_change_impacts", {}).items():
            if art in impacts:
                impacts[art] = verdict
        report.rationale.append("No specific rule matched; applied default impact.")

    report.impacts = impacts
    report.sections = sorted(sections)
    for art in report.impacted_artifacts:
        exists = present is None or art in set(present)
        report.rationale.append(
            f"{art}: UPDATE" + ("" if exists else " (not yet generated — will be created)")
        )
    return report


def write_report(run_id: str, report: ImpactReport) -> dict[str, Path]:
    out = run_reports_dir(run_id)
    md = out / "change-impact-report.md"
    js = out / "change-impact-report.json"

    lines = [
        "# Change Impact Report",
        "",
        f"**Change:** {report.change_text or '(none)'}",
        "",
        "| Artifact | Impact |",
        "|---|---|",
    ]
    for art, verdict in report.impacts.items():
        lines.append(f"| {art} | {verdict} |")
    rationale_lines = [f"- {r}" for r in report.rationale] or ["- (none)"]
    lines += [
        "",
        f"**Impacted sections:** {', '.join(report.sections) or '—'}",
        f"**Matched rules:** {'; '.join(report.matched_rules) or 'none (default applied)'}",
        "",
        "## Rationale",
        *rationale_lines,
        "",
        "> Only impacted artifacts/sections are regenerated; approved content is preserved.",
    ]
    md.write_text("\n".join(lines) + "\n", encoding="utf-8")
    js.write_text(json.dumps(report.to_dict(), indent=2), encoding="utf-8")
    return {"md": md, "json": js}


def regeneration_plan(report: ImpactReport) -> str:
    """Human/LLM-readable instruction for targeted regeneration."""
    if not report.impacted_artifacts:
        return "No artifacts impacted; no regeneration required."
    secs = ", ".join(report.sections) or "the affected sections"
    return (
        "TARGETED UPDATE PLAN (preserve all unaffected approved content):\n"
        f"- Update ONLY these sections: {secs}.\n"
        f"- Impacted artifacts: {', '.join(report.impacted_artifacts)}.\n"
        "- Do not rewrite unchanged sections; keep their existing IDs stable."
    )
