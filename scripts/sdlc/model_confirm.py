"""Apply a human model confirmation/override, then clear the pause.

Invoked by the feedback handler when a human runs `/model approve` or
`/model select <model> [reason]`. Sets the selected model for the paused stage
and records the override reason; the orchestrator resumes on the next dispatch.
"""
from __future__ import annotations

import argparse
import json
import sys
from typing import Optional

from .model_router import confirmation_required  # noqa: F401 (kept for parity)
from .orchestrator.state_store import load_state, save_state


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Confirm/override the stage model")
    parser.add_argument("--issue", type=int, required=True)
    parser.add_argument("--model", type=str, default=None,
                        help="Model to use; omit to accept the recommended model")
    parser.add_argument("--reason", type=str, default=None,
                        help="Override reason (required when choosing a non-recommended model)")
    parser.add_argument("--run-id", type=str, default="")
    args = parser.parse_args(argv)

    st = load_state(args.issue, args.run_id)
    if st is None or not st.pending_model_confirmation:
        print(json.dumps({"ok": False, "error": "no pending model confirmation"}))
        return 0

    pending = st.pending_model_confirmation
    agent = pending.get("agent")
    recommended = pending.get("recommended_model")
    chosen = args.model or recommended

    st.selected_models[agent] = chosen
    if chosen != recommended and args.reason:
        st.model_overrides[agent] = args.reason
    # The orchestrator clears pending_model_confirmation when it resumes.
    save_state(st)

    print(json.dumps({
        "ok": True, "agent": agent, "recommended": recommended,
        "selected": chosen,
        "source": "human_override" if chosen != recommended else "router_recommendation",
        "reason": args.reason,
    }))
    return 0


if __name__ == "__main__":
    sys.exit(main())
