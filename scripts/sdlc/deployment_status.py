"""Persist production verification outcome and emit structured status.

The deploy workflow calls this after health/smoke verification. If an issue
state exists, transitions it to DEPLOYED_AND_VERIFIED or DEPLOYMENT_FAILED;
otherwise it still emits a machine-readable result for the release evidence.
"""
from __future__ import annotations

import argparse
import json
import sys
from typing import Optional

from .orchestrator.state_store import load_state, save_state
from .orchestrator.states import State


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Record production verification")
    parser.add_argument("--result", choices=["verified", "failed"], required=True)
    parser.add_argument("--issue", type=int, default=None)
    parser.add_argument("--run-id", default="")
    parser.add_argument("--commit-sha", default="N/A")
    parser.add_argument("--details", default="")
    args = parser.parse_args(argv)

    new_state = (State.DEPLOYED_AND_VERIFIED if args.result == "verified"
                 else State.DEPLOYMENT_FAILED)
    state = load_state(args.issue, args.run_id) if args.issue is not None else None
    if state is not None:
        state.transition(new_state, args.details or f"production verification {args.result}")
        save_state(state)

    print(json.dumps({
        "status": args.result,
        "state": new_state,
        "issue": args.issue,
        "run_id": state.run_id if state else args.run_id or None,
        "commit_sha": args.commit_sha,
        "state_persisted": state is not None,
        "details": args.details or None,
    }, indent=2))
    return 0


if __name__ == "__main__":
    sys.exit(main())
