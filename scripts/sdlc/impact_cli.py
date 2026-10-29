"""Standalone Change Impact Analysis CLI (Priority 4).

Used by the feedback handler for `/agent impact <change>` and callable locally.
Writes reports/<run-id>/change-impact-report.(md|json) and prints the summary.
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from . import impact as impact_mod
from .common.logging_util import new_run_id
from .orchestrator.state_store import load_state


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Change Impact Analysis")
    parser.add_argument("--issue", type=int, default=None)
    parser.add_argument("--change", type=str, default="")
    parser.add_argument("--change-file", type=str, default=None)
    parser.add_argument("--run-id", type=str, default=None)
    args = parser.parse_args(argv)

    change = args.change
    if args.change_file and Path(args.change_file).exists():
        change = Path(args.change_file).read_text(encoding="utf-8")

    present = None
    if args.issue is not None:
        st = load_state(args.issue, "")
        if st is not None:
            present = list(st.artifacts.keys())

    run_id = args.run_id or new_run_id("impact")
    report = impact_mod.analyze(change, present)
    paths = impact_mod.write_report(run_id, report)

    print(json.dumps({
        "run_id": run_id,
        "impacted_artifacts": report.impacted_artifacts,
        "sections": report.sections,
        "report_md": str(paths["md"]),
        **report.to_dict(),
    }, indent=2))
    return 0


if __name__ == "__main__":
    sys.exit(main())
