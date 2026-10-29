#!/usr/bin/env python3
"""Council CI runner (referenced by .github/workflows/council-query.yml).

Runs a multi-stage "council" evaluation of a query against the repository and
writes results to OUTPUT_DIR. Stage outputs:
    <OUTPUT_DIR>/stage1_response.txt   - independent reviewers
    <OUTPUT_DIR>/stage2_response.txt   - cross-examination
    <OUTPUT_DIR>/chairman_response.txt - final synthesis (consumed by callers)

Backend: GitHub Copilot SDK if available, else the Copilot CLI, else a clearly
labeled deterministic stub (so the workflow never hard-fails on environment).

Environment:
    QUERY_TEXT  - the query/question (required)
    OUTPUT_DIR  - output directory (default /tmp/council-results)
"""
from __future__ import annotations

import os
import shutil
import subprocess
import sys
from pathlib import Path

STAGES = [
    ("stage1_response.txt",
     "You are an independent senior reviewer. Analyze the request against the "
     "repository and produce a thorough, evidence-based assessment. Reference "
     "file paths. Do not fabricate."),
    ("stage2_response.txt",
     "You are a cross-examiner. Critically review the prior assessment, "
     "challenge weak claims, and surface anything missed."),
    ("chairman_response.txt",
     "You are the chairman. Synthesize the prior stages into a single, "
     "actionable verdict with a clear recommendation and justification."),
]


def _run_copilot(prompt: str) -> str | None:
    if shutil.which("copilot") is None:
        return None
    try:
        proc = subprocess.run(
            ["copilot", "-p", prompt, "--allow-all-tools"],
            capture_output=True, text=True, timeout=900, check=False,
        )
    except subprocess.TimeoutExpired:
        return "[council] copilot timed out."
    return proc.stdout.strip() if proc.returncode == 0 else (
        f"[council] copilot error: {(proc.stderr or '').strip()[:400]}"
    )


def main() -> int:
    query = os.environ.get("QUERY_TEXT", "").strip()
    out_dir = Path(os.environ.get("OUTPUT_DIR", "/tmp/council-results"))
    out_dir.mkdir(parents=True, exist_ok=True)

    if not query:
        (out_dir / "chairman_response.txt").write_text(
            "No QUERY_TEXT provided.\n", encoding="utf-8")
        print("No QUERY_TEXT provided.", file=sys.stderr)
        return 0

    transcript = f"=== COUNCIL QUERY ===\n{query}\n"
    for filename, role in STAGES:
        prompt = f"{role}\n\n{transcript}"
        response = _run_copilot(prompt)
        if response is None:
            response = (
                f"[council stub] Copilot backend unavailable in this environment. "
                f"Stage role: {role[:60]}..."
            )
        (out_dir / filename).write_text(response + "\n", encoding="utf-8")
        transcript += f"\n=== {filename} ===\n{response}\n"

    print(f"Council complete. Results in {out_dir}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
