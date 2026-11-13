"""Human actions on a request. Every GitHub write here uses the signed-in user's own token."""

from __future__ import annotations

from typing import Any

from sqlalchemy.orm import Session

from ..audit import record
from ..container import Container
from ..db import IntakeRequest, User
from ..errors import ApiError
from ..github import commands
from ..github.clients import UserGitHubClient
from ..github.http import GitHubError
from ..github.identity import get_link, mark_revoked, reconnect_required, user_client
from ..status.sync import sync_request
from .precheck import WRITE_LEVELS, Precheck, approval_precheck, stage_of


def github_failure(exc: GitHubError) -> ApiError:
    """Relay GitHub's reason verbatim. Never retried with another identity."""
    if exc.kind == "auth":
        return reconnect_required()
    if exc.kind == "rate_limited":
        return ApiError(429, "github_rate_limited", exc.message, github_status=exc.status)
    if exc.status == 422 and "closed" in exc.message.lower():
        return ApiError(
            409, "github_conflict", f"GitHub: {exc.message}. The PR may already be merged.", github_status=exc.status
        )
    return ApiError(
        502 if exc.status >= 500 or exc.status == 0 else 409,
        "github_rejected",
        f"GitHub rejected the action: {exc.message}",
        github_status=exc.status,
    )


class ReviewService:
    def __init__(self, c: Container) -> None:
        self.c = c
        self.s = c.settings

    # -------------------------------------------------------------- helpers
    def _requester_login(self, db: Session, req: IntakeRequest) -> str | None:
        requester = db.get(User, req.requester_id)
        link = get_link(db, requester) if requester else None
        return link.github_login if link else None

    def _act(
        self,
        db: Session,
        user: User,
        client: UserGitHubClient,
        req: IntakeRequest,
        action: str,
        target_type: str,
        target: str,
        fn: Any,
        detail: str = "",
    ) -> Any:
        try:
            result = fn()
        except GitHubError as exc:
            if exc.kind == "auth":
                link = get_link(db, user)
                if link:
                    mark_revoked(db, link)
            record(
                db,
                user=user,
                github_login=client.login,
                identity="user",
                action=action,
                target_type=target_type,
                target_ref=target,
                outcome="rejected",
                github_status=exc.status,
                request_id=req.id,
                detail=exc.message,
            )
            raise github_failure(exc) from exc
        record(
            db,
            user=user,
            github_login=client.login,
            identity="user",
            action=action,
            target_type=target_type,
            target_ref=target,
            outcome="ok",
            github_status=200,
            request_id=req.id,
            detail=detail,
        )
        return result

    def _require_reviewer(self, user: User) -> None:
        if self.s.entra_reviewer_role not in (user.roles or []):
            raise ApiError(403, "reviewer_role_required", "This action needs the Reviewer role in the portal.")

    def _require_write(self, client: UserGitHubClient) -> None:
        perm = self.c.service.collaborator_permission(client.login)
        if perm not in WRITE_LEVELS:
            raise ApiError(
                403,
                "github_write_required",
                f"Your GitHub account '{client.login}' has '{perm}' access; AISDLC commands need write "
                "access to the repository.",
            )

    def _stage_pr(self, req: IntakeRequest, pr_number: int) -> dict[str, Any]:
        pr = self.c.service.get_pull(pr_number)
        n, _ = stage_of(pr)
        if n is None or n != req.issue_number:
            raise ApiError(404, "not_found", "Stage PR not found for this request.")
        return pr

    # -------------------------------------------------------------- reads
    def stage_view(self, db: Session, user: User, req: IntakeRequest, pr_number: int) -> dict[str, Any]:
        svc = self.c.service
        pr = self._stage_pr(req, pr_number)
        files = svc.list_pull_files(pr_number)
        reviews = svc.list_pull_reviews(pr_number)
        head = pr["head"]["sha"]
        artifact_path = next(
            (
                f["filename"]
                for f in files
                if f["filename"].startswith("docs/") and f["filename"].endswith(".md") and f.get("status") != "removed"
            ),
            None,
        )
        qc_path = next((f["filename"] for f in files if f["filename"].endswith("quality-report.md")), None)
        from ..status.tracker import parse_summary

        view: dict[str, Any] = {
            "pr": {
                "number": pr["number"],
                "title": pr.get("title"),
                "url": pr.get("html_url"),
                "state": "merged" if pr.get("merged") or pr.get("merged_at") else pr.get("state"),
                "author": pr.get("user", {}).get("login"),
                "head_sha": head,
                "head_ref": pr["head"]["ref"],
                "body": pr.get("body") or "",
            },
            "stage": stage_of(pr)[1],
            "summary": parse_summary(pr.get("body") or ""),
            "artifact": {
                "path": artifact_path,
                "markdown": svc.get_file(artifact_path, head) if artifact_path else None,
            },
            "quality_report": {"path": qc_path, "markdown": svc.get_file(qc_path, head) if qc_path else None},
            "files": [
                {
                    "filename": f["filename"],
                    "status": f.get("status"),
                    "additions": f.get("additions"),
                    "deletions": f.get("deletions"),
                    "patch": (f.get("patch") or "")[:200_000],
                }
                for f in files
            ],
            "reviews": [
                {
                    "user": r.get("user", {}).get("login"),
                    "state": r.get("state"),
                    "submitted_at": r.get("submitted_at"),
                    "commit_id": r.get("commit_id"),
                }
                for r in reviews
            ],
            "precheck": None,
            "github_link": None,
            "approve_confirmation": "Approving submits your GitHub review. AISDLC then merges this pull request "
            "and starts the next stage. This cannot be undone from the portal.",
        }
        link = get_link(db, user)
        if link is None or link.revoked:
            view["github_link"] = {
                "connected": False,
                "reason": "Connect GitHub to review: approvals are made with your own GitHub account.",
            }
            return view
        view["github_link"] = {"connected": True, "login": link.github_login}
        if self.s.entra_reviewer_role not in (user.roles or []):
            view["precheck"] = Precheck(False, [], head, view["stage"]).to_dict()
            view["precheck"]["reasons"] = ["You do not have the Reviewer role in the portal."]
            return view
        view["precheck"] = self._precheck(db, req, pr, files, reviews, link.github_login).to_dict()
        return view

    def _precheck(
        self,
        db: Session,
        req: IntakeRequest,
        pr: dict[str, Any],
        files: list[dict[str, Any]],
        reviews: list[dict[str, Any]],
        login: str,
    ) -> Precheck:
        return approval_precheck(
            self.c.service,
            pr=pr,
            files=files,
            reviews=reviews,
            login=login,
            issue_number=req.issue_number or -1,
            base_branch=self.s.github_base_branch,
            codeowners_policy=self.s.codeowners_policy,
            separation_of_duties=self.s.separation_of_duties,
            sod_stages=self.s.sod_stages,
            requester_login=self._requester_login(db, req),
        )

    # -------------------------------------------------------------- writes
    def approve(
        self, db: Session, user: User, req: IntakeRequest, pr_number: int, head_sha: str, confirmed: bool
    ) -> dict[str, Any]:
        self._require_reviewer(user)
        if confirmed is not True:
            raise ApiError(
                400, "confirmation_required", "Confirm that approving merges the PR and starts the next stage."
            )
        client = user_client(self.c, db, user, verify_identity=True)
        svc = self.c.service
        pr = self._stage_pr(req, pr_number)
        if pr["head"]["sha"] != head_sha:
            raise ApiError(
                409,
                "pr_changed",
                "The pull request changed since you opened it. Review the new version before approving.",
            )
        check = self._precheck(
            db, req, pr, svc.list_pull_files(pr_number), svc.list_pull_reviews(pr_number), client.login
        )
        if not check.can_approve:
            record(
                db,
                user=user,
                github_login=client.login,
                identity="user",
                action="approve",
                target_type="pull_request",
                target_ref=f"#{pr_number}",
                outcome="blocked_precheck",
                request_id=req.id,
                detail="; ".join(check.reasons),
            )
            raise ApiError(403, "approval_not_allowed", "You cannot approve this pull request.", reasons=check.reasons)
        body = f"Approved in the AISDLC Portal after reviewing the artifact, diff and QC scorecard. Ref {req.id}."
        review = self._act(
            db,
            user,
            client,
            req,
            "approve",
            "pull_request",
            f"#{pr_number}",
            lambda: client.submit_review(pr_number, "APPROVE", body, head_sha),
            detail=f"stage={check.stage} head={head_sha[:12]}",
        )
        sync_request(self.c, db, req)
        return {"review_id": review.get("id"), "github_login": client.login, "state": review.get("state")}

    def request_changes(
        self, db: Session, user: User, req: IntakeRequest, pr_number: int, notes: str
    ) -> dict[str, Any]:
        return self.agent_command(db, user, req, commands.AgentCommand.revise.value, notes, pr_number)

    def agent_command(
        self, db: Session, user: User, req: IntakeRequest, command: str, notes: str, pr_number: int | None
    ) -> dict[str, Any]:
        self._require_reviewer(user)
        try:
            cmd = commands.AgentCommand(command)
            text = commands.agent_command(cmd, notes, block_shell=self.s.block_shell_metacharacters)
        except ValueError as exc:
            raise ApiError(
                422,
                "invalid_command",
                str(exc)
                if isinstance(exc, commands.CommandError)
                else "Unknown command. Allowed: " + ", ".join(c.value for c in commands.AgentCommand),
            ) from exc
        client = user_client(self.c, db, user)
        self._require_write(client)
        target = pr_number if pr_number else req.issue_number
        if pr_number:
            self._stage_pr(req, pr_number)
        assert target is not None
        c = self._act(
            db,
            user,
            client,
            req,
            f"agent_{cmd.value}",
            "pull_request" if pr_number else "issue",
            f"#{target}",
            lambda: client.post_comment(target, text),
        )
        sync_request(self.c, db, req)
        return {"comment_url": c.get("html_url"), "github_login": client.login, "command": text.split("\n")[0][:80]}

    def model_command(
        self, db: Session, user: User, req: IntakeRequest, command: str, model: str, reason: str
    ) -> dict[str, Any]:
        self._require_reviewer(user)
        try:
            cmd = commands.ModelCommand(command)
            text = commands.model_command(
                cmd,
                model,
                reason,
                allowed_models=set(self.c.allowed_models()),
                block_shell=self.s.block_shell_metacharacters,
            )
        except ValueError as exc:
            raise ApiError(
                422, "invalid_command", str(exc) if isinstance(exc, commands.CommandError) else "Unknown model command."
            ) from exc
        client = user_client(self.c, db, user)
        self._require_write(client)
        assert req.issue_number is not None
        c = self._act(
            db,
            user,
            client,
            req,
            f"model_{cmd.value}",
            "issue",
            f"#{req.issue_number}",
            lambda: client.post_comment(req.issue_number, text),
        )
        sync_request(self.c, db, req)
        return {"comment_url": c.get("html_url"), "github_login": client.login, "command": text}

    def answer(self, db: Session, user: User, req: IntakeRequest, answer: str) -> dict[str, Any]:
        try:
            text = commands.answer_text(answer)
        except commands.CommandError as exc:
            raise ApiError(422, "invalid_answer", str(exc)) from exc
        if req.issue_number is None:
            raise ApiError(409, "not_submitted", "This request has not been submitted to GitHub yet.")
        sync_request(self.c, db, req)
        if (req.status_snapshot or {}).get("status") != "awaiting_info":
            raise ApiError(409, "not_awaiting_info", "AISDLC is not waiting for information on this request.")
        client = user_client(self.c, db, user)
        c = self._act(
            db,
            user,
            client,
            req,
            "answer_questions",
            "issue",
            f"#{req.issue_number}",
            lambda: client.post_comment(req.issue_number, text),
        )
        sync_request(self.c, db, req)
        return {"comment_url": c.get("html_url"), "github_login": client.login}
