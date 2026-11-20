"""Maps the technical workflow snapshot to a simple employee-facing request view."""

from __future__ import annotations

from typing import Any

STEPS = (
    ("submitted", "Request submitted"),
    ("initial_review", "Initial review"),
    ("it_review", "IT review"),
    ("approval", "Approval"),
    ("implementation", "Implementation"),
    ("completed", "Completed"),
)

ACTIVE_RUN_STATES = {"queued", "in_progress", "waiting", "pending"}


def employee_status(status: str, snapshot: dict[str, Any]) -> str:
    if status == "submit_failed":
        return "submitted"
    if status == "awaiting_info":
        return "more_information_required"
    if status == "complete" or snapshot.get("completed"):
        return "completed"
    if status == "closed":
        return "rejected"
    if status == "running":
        stages = snapshot.get("stages") or []
        latest_run = snapshot.get("latest_run") or {}
        if (
            stages
            and all(stage.get("state") == "merged" for stage in stages)
            and latest_run.get("status") == "completed"
            and latest_run.get("conclusion") == "success"
        ):
            return "approved"
        return "in_progress"
    if status in {"in_review", "awaiting_model", "needs_attention"}:
        return "under_review"
    return "submitted"


def employee_progress(status: str) -> list[dict[str, str]]:
    if status == "submitted":
        current = 1
    elif status in {"under_review", "more_information_required"}:
        current = 2
    elif status in {"approved", "in_progress"}:
        current = 4
    elif status == "completed":
        current = len(STEPS)
    else:
        current = 3

    progress: list[dict[str, str]] = []
    for index, (step_id, label) in enumerate(STEPS):
        if status == "completed":
            state = "completed"
        elif status == "rejected" and index == current:
            state = "rejected"
        elif index < current:
            state = "completed"
        elif index == current:
            state = "delayed" if status == "more_information_required" else "current"
        else:
            state = "pending"
        progress.append({"id": step_id, "label": label, "state": state})
    return progress


def default_employee_update(status: str) -> str:
    return {
        "submitted": "We received your request. The IT team will review it next.",
        "under_review": "Your request is being reviewed by the IT team. We will update you if we need anything else.",
        "more_information_required": "The IT team needs more information to continue reviewing your request.",
        "approved": "Your request has been approved and is moving to implementation.",
        "in_progress": "Your request is in progress. No action is needed from you right now.",
        "completed": "Your request has been completed.",
        "rejected": "Your request has been closed. Contact the IT team if you have questions.",
    }.get(status, "The IT team is reviewing your request.")
