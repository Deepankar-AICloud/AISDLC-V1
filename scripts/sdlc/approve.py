"""Mark the current SDLC stage approved and advance state.

Invoked by the artifact-review workflow when a human approves a stage PR.
"""
from __future__ import annotations

import argparse
import sys

from .orchestrator.state_store import load_state, save_state
from .orchestrator.states import STAGE_FLOW, State

# Generation state -> approved state.
_APPROVED = {
    State.BRD_GENERATION: State.BRD_APPROVED,
    State.PRD_GENERATION: State.PRD_APPROVED,
    State.EPIC_GENERATION: State.EPIC_APPROVED,
    State.ARCHITECTURE_GENERATION: State.ARCHITECTURE_APPROVED,
    State.NFR_GENERATION: State.NFR_APPROVED,
    State.TASK_GENERATION: State.TASK_APPROVED,
    State.CODE_GENERATION: State.CODE_APPROVED,
}


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Approve current SDLC stage")
    parser.add_argument("--issue", type=int, required=True)
    parser.add_argument("--reviewer", type=str, default="unknown")
    parser.add_argument("--run-id", type=str, default="")
    args = parser.parse_args(argv)

    state = load_state(args.issue, args.run_id)
    if state is None:
        print(f"No state found for issue {args.issue}; nothing to approve.")
        return 0

    current = state.current_state
    approved = _APPROVED.get(current)
    if approved is None:
        print(f"State {current} is not an approvable generation stage.")
        return 0

    state.transition(approved, f"approved by {args.reviewer}")
    state.human_reviews[current] = state.human_reviews.get(current, 0) + 1

    next_state = STAGE_FLOW.get(approved)
    if next_state:
        state.transition(next_state, "advance after approval")
    save_state(state)
    print(f"Issue {args.issue}: {current} -> {approved} -> {next_state or 'end'}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
