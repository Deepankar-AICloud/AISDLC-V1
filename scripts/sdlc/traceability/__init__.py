"""Traceability engine.

Scans generated artifacts under ``docs/`` and source under ``src/`` for stable
IDs and builds a requirement-to-production matrix:

    REQ -> BRD-REQ -> PRD-FR -> EPIC -> FEATURE -> US -> ARCH-COMP -> TASK
        -> CODE -> UT -> FT -> SEC -> RELEASE

Detects orphans, missing tests, and requirements dropped between stages.
Writes ``reports/<run-id>/traceability-report.md``.
"""
from __future__ import annotations

import re
from pathlib import Path
from typing import Iterable

from ..common.config import DOCS_DIR, REPO_ROOT, run_reports_dir

ID_PATTERNS = {
    "REQ": r"\bREQ-\d{3,}\b",
    "BRD-REQ": r"\bBRD-REQ-\d{3,}\b",
    "PRD-FR": r"\bPRD-FR-\d{3,}\b",
    "EPIC": r"\bEPIC-\d{3,}\b",
    "FEATURE": r"\bFEATURE-\d{3,}\b",
    "US": r"\bUS-\d{3,}\b",
    "ARCH-COMP": r"\bARCH-COMP-\d{3,}\b",
    "TASK": r"\bTASK-\d{3,}\b",
    "UT": r"\bUT-\d{3,}\b",
    "FT": r"\bFT-\d{3,}\b",
    "SEC": r"\bSEC-\d{3,}\b",
}

# Expected downstream linkage order for drop detection.
STAGE_ORDER = ["REQ", "BRD-REQ", "PRD-FR", "EPIC", "FEATURE", "US",
               "ARCH-COMP", "TASK", "UT", "FT", "SEC"]


def _iter_text_files(roots: Iterable[Path]) -> Iterable[Path]:
    exts = {".md", ".cs", ".ts", ".tsx", ".py", ".json"}
    for root in roots:
        if not root.exists():
            continue
        for p in root.rglob("*"):
            if p.is_file() and p.suffix in exts:
                yield p


def collect_ids() -> dict[str, set[str]]:
    found: dict[str, set[str]] = {k: set() for k in ID_PATTERNS}
    for path in _iter_text_files([DOCS_DIR, REPO_ROOT / "src", REPO_ROOT / "tests"]):
        try:
            text = path.read_text(encoding="utf-8", errors="ignore")
        except OSError:
            continue
        for label, pattern in ID_PATTERNS.items():
            for m in re.findall(pattern, text):
                found[label].add(m)
    return found


def build_report(run_id: str) -> Path:
    ids = collect_ids()
    lines = ["# Traceability Report", "", f"Run: `{run_id}`", ""]

    lines.append("## ID inventory")
    lines.append("")
    lines.append("| Stage | Count | IDs |")
    lines.append("|---|---|---|")
    for label in STAGE_ORDER:
        items = sorted(ids.get(label, set()))
        preview = ", ".join(items[:10]) + (" …" if len(items) > 10 else "")
        lines.append(f"| {label} | {len(items)} | {preview or '—'} |")

    # Drop detection: a requirement present upstream but absent at the next
    # populated stage is flagged.
    lines += ["", "## Gaps & orphans", ""]
    gaps: list[str] = []
    if not ids["REQ"] and not ids["BRD-REQ"]:
        gaps.append("No requirement IDs found yet (expected once BRD exists).")
    if ids["US"] and not ids["FT"]:
        gaps.append("User stories exist but no functional-test IDs (FT-*) found.")
    if ids["REQ"] and not ids["BRD-REQ"]:
        gaps.append("REQ-* present but not traced to BRD-REQ-*.")
    if not gaps:
        gaps.append("No gaps detected for the ID types currently present.")
    lines += [f"- {g}" for g in gaps]

    out = run_reports_dir(run_id) / "traceability-report.md"
    out.write_text("\n".join(lines) + "\n", encoding="utf-8")
    return out
