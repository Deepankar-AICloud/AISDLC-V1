"""Keeps request records in sync with GitHub (webhooks first, polling as a fallback)."""

from __future__ import annotations

import logging
import re
import threading
from datetime import timedelta
from typing import Any

from sqlalchemy import delete, select
from sqlalchemy.orm import Session

from ..container import Container
from ..db import Assignment, GitHubLink, IntakeRequest, User, utcnow
from ..github import codeowners
from ..github.http import GitHubError
from .tracker import build_snapshot

log = logging.getLogger(__name__)
FINAL = {"complete", "closed"}


def _assign(c: Container, db: Session, req: IntakeRequest, snapshot: dict[str, Any]) -> None:
    """Reviewers = code owners of the open stage PR's files + requested reviewers + DEFAULT_REVIEWERS."""
    logins: dict[str, str] = {lg.lower(): "default" for lg in c.settings.default_reviewers}
    pr_number = snapshot.get("open_stage_pr")
    if pr_number:
        svc = c.service
        pr = svc.get_pull(pr_number)
        for r in pr.get("requested_reviewers", []) or []:
            logins[r["login"].lower()] = "requested"
        text = next(
            (t for loc in codeowners.LOCATIONS if (t := svc.get_file(loc, c.settings.github_base_branch)) is not None),
            None,
        )
        if text:
            rules = codeowners.parse(text)
            owners: set[str] = set()
            for f in svc.list_pull_files(pr_number):
                owners |= set(codeowners.owners_for(rules, f["filename"]))
            for o in owners:
                if o.startswith("@") and "/" in o:
                    # Team owners are stored as teams; membership is checked when a reviewer looks,
                    # so people who connect GitHub later are still covered.
                    logins[o.lower()] = "codeowner_team"
                elif o.startswith("@"):
                    logins[o[1:].lower()] = "codeowner"
    db.execute(delete(Assignment).where(Assignment.request_id == req.id))
    for login, source in logins.items():
        db.add(Assignment(request_id=req.id, github_login=login, source=source))


def sync_request(c: Container, db: Session, req: IntakeRequest) -> IntakeRequest:
    if req.issue_number is None:
        return req
    try:
        snap = build_snapshot(c.service, req.issue_number)
    except GitHubError as exc:
        log.warning("status sync failed", extra={"fields": {"request_id": req.id, "status": exc.status}})
        snap = {**(req.status_snapshot or {}), "sync_error": f"GitHub returned {exc.status}: {exc.message}"}
        req.status_snapshot = snap
        req.last_synced_at = utcnow()
        db.commit()
        return req
    req.status_snapshot = snap
    if req.status not in ("submitting", "submit_failed"):
        req.status = snap["status"]
    req.stage = snap["stage"]
    req.last_synced_at = utcnow()
    req.updated_at = utcnow()
    try:
        _assign(c, db, req, snap)
    except GitHubError as exc:
        log.warning("assignment sync failed", extra={"fields": {"request_id": req.id, "status": exc.status}})
    db.commit()
    return req


def requests_for_event(db: Session, event: str, payload: dict[str, Any]) -> list[IntakeRequest]:
    issue_no: int | None = None
    pr_no: int | None = None
    if event in ("issues", "issue_comment"):
        issue = payload.get("issue") or {}
        if issue.get("pull_request"):
            pr_no = issue.get("number")
        else:
            issue_no = issue.get("number")
    elif event in ("pull_request", "pull_request_review", "pull_request_review_comment"):
        ref = (payload.get("pull_request") or {}).get("head", {}).get("ref", "")
        m = re.match(r"sdlc/issue-(\d+)/", ref)
        issue_no = int(m.group(1)) if m else None
    elif event == "workflow_run":
        m = re.search(r"issue #(\d+)", (payload.get("workflow_run") or {}).get("display_title", ""))
        issue_no = int(m.group(1)) if m else None
    if issue_no is not None:
        return list(db.scalars(select(IntakeRequest).where(IntakeRequest.issue_number == issue_no)))
    if pr_no is not None:
        out = []
        for r in db.scalars(select(IntakeRequest).where(IntakeRequest.status.not_in(FINAL))):
            if any(s.get("pr_number") == pr_no for s in (r.status_snapshot or {}).get("stages", [])):
                out.append(r)
        return out
    return []


class Poller:
    """Fallback for missed webhooks: re-syncs active requests on an interval."""

    def __init__(self, c: Container) -> None:
        self.c = c
        self._stop = threading.Event()
        self._thread: threading.Thread | None = None

    def start(self) -> None:
        if self._thread is None:
            self._thread = threading.Thread(target=self._run, name="status-poller", daemon=True)
            self._thread.start()

    def stop(self) -> None:
        self._stop.set()

    def tick(self) -> int:
        n = 0
        cutoff = utcnow() - timedelta(seconds=self.c.settings.poll_interval_seconds)
        with self.c.db.sessionmaker() as db:
            due = db.scalars(
                select(IntakeRequest).where(
                    IntakeRequest.status.not_in([*FINAL, "submitting"]), IntakeRequest.issue_number.is_not(None)
                )
            ).all()
            for req in due:
                if req.last_synced_at and req.last_synced_at > cutoff:
                    continue
                sync_request(self.c, db, req)
                n += 1
            from ..intake.service import IntakeService

            IntakeService(self.c).purge_expired_drafts(db)
        return n

    def _run(self) -> None:
        while not self._stop.wait(self.c.settings.poll_interval_seconds):
            try:
                self.tick()
            except Exception:  # noqa: BLE001 - the poller must keep running
                log.exception("poller tick failed")


def _is_team_member(c: Container, team: str, login: str) -> bool:
    org, _, slug = team.lstrip("@").partition("/")
    return bool(c.cached(f"team:{team}:{login}", 300, lambda: c.service.team_member(org, slug, login)))


def assigned_request_ids(c: Container, db: Session, user: User, request_ids: list[str] | None = None) -> set[str]:
    """Requests assigned to this reviewer: direct login match, or membership of an owning team."""
    if c.settings.entra_reviewer_role not in (user.roles or []):
        return set()
    link = db.scalar(select(GitHubLink).where(GitHubLink.user_id == user.id))
    if link is None or link.revoked:
        return set()
    login = link.github_login.lower()
    q = select(Assignment)
    if request_ids is not None:
        q = q.where(Assignment.request_id.in_(request_ids))
    out: set[str] = set()
    for a in db.scalars(q):
        if a.request_id in out:
            continue
        if a.github_login == login:
            out.add(a.request_id)
        elif a.github_login.startswith("@") and "/" in a.github_login:
            try:
                if _is_team_member(c, a.github_login, login):
                    out.add(a.request_id)
            except GitHubError:
                continue
    return out


def can_view(c: Container, db: Session, user: User, req: IntakeRequest) -> bool:
    if req.requester_id == user.id:
        return True
    return req.id in assigned_request_ids(c, db, user, [req.id])
