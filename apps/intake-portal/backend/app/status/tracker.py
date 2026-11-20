"""Derives a request's AISDLC status from GitHub (issue, labels, bot comments, stage PRs, runs).

Bot comments are parsed as untrusted data and rendered as plain text by the UI.
Note: the CodeQL gate removes `sdlc:start` when it dispatches, so its absence does
not mean the request was not started.
"""

from __future__ import annotations

import re
from typing import Any

from ..github.clients import ServiceGitHubClient
from ..review.precheck import stage_of

AWAITING = "sdlc:awaiting-info"
BOTS = {"github-actions", "github-actions[bot]"}
BLOCKED_HDR = "## ⛔ Generation blocked"
MODEL_HDR = "## 🤖 AI Model Recommendation"
MODEL_OK = "✅ Model decision recorded"
PAUSED_HDR = "paused — QC"
DONE_HDR = "Agentic generation stages complete"
QUEUED = "SDLC is queued"


def _bot(c: dict[str, Any]) -> bool:
    return c.get("user", {}).get("login") in BOTS


def parse_questions(body: str) -> list[str]:
    qs: list[str] = []
    for line in body.splitlines():
        s = line.strip()
        if s.startswith("- "):
            qs.append(s[2:].strip()[:500])
    return qs[:30]


def parse_summary(body: str) -> dict[str, Any]:
    def grab(label: str) -> str:
        m = re.search(rf"\*\*{re.escape(label)}:\*\*\s*(.+)", body or "")
        return m.group(1).strip().strip("`") if m else ""

    qc = re.search(r"\*\*QC:\*\*\s*(\w+)\s+([0-9.]+|None)", body or "")
    return {
        "run_id": grab("Run ID"),
        "readiness": grab("Readiness"),
        "assumptions": grab("Assumptions"),
        "recommended_model": grab("Recommended model"),
        "selected_model": grab("Selected model"),
        "qc_status": qc.group(1) if qc else "",
        "qc_score": float(qc.group(2)) if qc and qc.group(2) != "None" else None,
        "retries": grab("Retries"),
        "diagnosis": grab("QC diagnosis"),
    }


def parse_issue_field(body: str, label: str) -> str:
    heading = re.search(rf"^## {re.escape(label)}[ \t]*$", body or "", re.MULTILINE)
    if not heading:
        return ""
    section = (body or "")[heading.end() :]
    opening = re.search(r"^(~{4,})text[ \t]*$", section, re.MULTILINE)
    if not opening:
        return ""
    content = section[opening.end() :]
    closing = re.search(rf"^{re.escape(opening.group(1))}[ \t]*$", content, re.MULTILINE)
    return content[: closing.start()].strip() if closing else ""


def latest_human_update(comments: list[dict[str, Any]]) -> dict[str, str] | None:
    for comment in reversed(comments):
        user = comment.get("user") or {}
        login = str(user.get("login") or "")
        body = str(comment.get("body") or "").strip()
        if login.lower() in BOTS or not body or body.startswith("/"):
            continue
        return {
            "author": str(user.get("name") or login or "IT team"),
            "login": login,
            "body": body[:2000],
            "created_at": str(comment.get("created_at") or ""),
        }
    return None


def build_snapshot(svc: ServiceGitHubClient, issue_number: int) -> dict[str, Any]:
    issue = svc.get_issue(issue_number)
    labels = [lb["name"] for lb in issue.get("labels", [])]
    comments = svc.list_issue_comments(issue_number)
    bot_comments = [c for c in comments if _bot(c)]

    def last(prefix: str) -> tuple[int, dict[str, Any] | None]:
        for i in range(len(comments) - 1, -1, -1):
            if _bot(comments[i]) and prefix in comments[i]["body"]:
                return i, comments[i]
        return -1, None

    awaiting = AWAITING in labels
    q_idx, q_comment = last(BLOCKED_HDR)
    questions = parse_questions(q_comment["body"]) if awaiting and q_comment else []
    m_idx, m_comment = last(MODEL_HDR)
    ok_idx, _ = last(MODEL_OK)
    model_pending = None
    if m_comment and m_idx > ok_idx:
        rec = re.search(r"\*\*Recommended model:\*\*\s*`?([^`\n]+)`?", m_comment["body"])
        model_pending = {
            "recommended_model": rec.group(1).strip() if rec else "",
            "comment_url": m_comment.get("html_url", ""),
        }
    p_idx, p_comment = last(PAUSED_HDR)
    done = last(DONE_HDR)[1] is not None
    queued = last(QUEUED)[0] > max(q_idx, p_idx)

    stages: list[dict[str, Any]] = []
    for pr in svc.list_pulls("all"):
        n, agent = stage_of(pr)
        if n != issue_number:
            continue
        state = "merged" if pr.get("merged_at") or pr.get("merged") else pr.get("state", "")
        stages.append(
            {
                "pr_number": pr["number"],
                "agent": agent,
                "state": state,
                "url": pr.get("html_url", ""),
                "title": pr.get("title", ""),
                "head_sha": pr.get("head", {}).get("sha", ""),
                "created_at": pr.get("created_at"),
                "summary": parse_summary(pr.get("body") or ""),
            }
        )
    stages.sort(key=lambda s: s["pr_number"])
    open_stage = next((s for s in reversed(stages) if s["state"] == "open"), None)

    run = None
    for r in svc.repo_runs():
        if r.get("display_title") == f"Agentic SDLC issue #{issue_number}":
            run = {
                "id": r["id"],
                "status": r.get("status"),
                "conclusion": r.get("conclusion"),
                "url": r.get("html_url"),
                "created_at": r.get("created_at"),
            }
            break

    if issue.get("state") == "closed":
        status = "closed"
    elif awaiting:
        status = "awaiting_info"
    elif model_pending:
        status = "awaiting_model"
    elif open_stage:
        status = "in_review"
    elif done:
        status = "complete"
    elif p_comment and p_idx > max(q_idx, ok_idx):
        status = "needs_attention"
    elif run and run["status"] in ("queued", "in_progress", "waiting", "pending"):
        status = "running"
    elif queued or "sdlc:start" in labels:
        status = "queued"
    else:
        status = "running" if run else "submitted"

    if open_stage:
        stage = open_stage["agent"]
    elif stages:
        stage = stages[-1]["agent"]
    else:
        stage = "brd"

    return {
        "issue": {
            "number": issue_number,
            "url": issue.get("html_url", ""),
            "state": issue.get("state"),
            "title": issue.get("title", ""),
        },
        "employee_details": {
            "problem": parse_issue_field(str(issue.get("body") or ""), "Business problem"),
            "objective": parse_issue_field(str(issue.get("body") or ""), "Objective"),
        },
        "latest_human_update": latest_human_update(comments),
        "completed": done,
        "labels": labels,
        "status": status,
        "stage": stage,
        "questions": questions,
        "questions_url": q_comment.get("html_url", "") if q_comment and awaiting else "",
        "model_pending": model_pending,
        "paused_findings": parse_questions(p_comment["body"]) if status == "needs_attention" and p_comment else [],
        "stages": stages,
        "open_stage_pr": open_stage["pr_number"] if open_stage else None,
        "latest_run": run,
        "bot_comment_count": len(bot_comments),
    }
