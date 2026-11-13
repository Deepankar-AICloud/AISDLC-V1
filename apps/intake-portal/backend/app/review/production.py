"""Production release approval (deploy-production.yml waits on the `production` environment).

Only GitHub decides who is a required reviewer: `current_user_can_approve` comes
from the deployment-review API called with the user's own token, and the approval
is sent with that token. The service identity cannot approve deployments.
"""

from __future__ import annotations

from typing import Any

from sqlalchemy.orm import Session

from ..audit import record
from ..container import Container
from ..db import User
from ..errors import ApiError
from ..github.http import GitHubError
from ..github.identity import get_link, user_client
from .service import github_failure


class ProductionService:
    def __init__(self, c: Container) -> None:
        self.c = c
        self.s = c.settings

    def environment_status(self) -> dict[str, Any]:
        env = self.c.service.get_environment(self.s.production_environment)
        if env is None:
            return {
                "exists": False,
                "reviewers": [],
                "problem": f"The '{self.s.production_environment}' environment does not exist in GitHub, so production "
                "deployments run without approval. Create it with required reviewers.",
            }
        reviewers = []
        for rule in env.get("protection_rules", []):
            if rule.get("type") == "required_reviewers":
                for r in rule.get("reviewers", []):
                    rv = r.get("reviewer", {})
                    reviewers.append(rv.get("login") or rv.get("slug") or rv.get("name"))
        problem = (
            None
            if reviewers
            else (
                f"The '{self.s.production_environment}' environment has no required "
                "reviewers, so production deployments run without approval."
            )
        )
        return {"exists": True, "id": env.get("id"), "reviewers": reviewers, "problem": problem}

    def evidence(self, head_sha: str) -> list[dict[str, Any]]:
        out = []
        runs = self.c.service.repo_runs(head_sha=head_sha)
        for name in self.s.production_evidence_workflows:
            run = next((r for r in runs if r.get("name") == name), None)
            out.append(
                {
                    "name": name,
                    "status": run.get("status") if run else "not_run",
                    "conclusion": run.get("conclusion") if run else None,
                    "url": run.get("html_url") if run else None,
                    "note": "Includes OWASP ZAP DAST" if name == "Deploy — STAGING" else "",
                }
            )
        return out

    def list_pending(self, db: Session, user: User) -> dict[str, Any]:
        env = self.environment_status()
        runs = self.c.service.workflow_runs(self.s.production_workflow_file, status="waiting")
        link = get_link(db, user)
        client = None
        if link and not link.revoked:
            try:
                client = user_client(self.c, db, user)
            except ApiError:
                client = None
        items = []
        for run in runs:
            pending: list[dict[str, Any]] = []
            can_approve = False
            reason = "Connect GitHub to see whether you are a required reviewer."
            if client is not None:
                try:
                    pending = client.pending_deployments(run["id"])
                except GitHubError as exc:
                    reason = f"GitHub: {exc.message}"
                prod = [p for p in pending if p.get("environment", {}).get("name") == self.s.production_environment]
                can_approve = bool(prod) and all(p.get("current_user_can_approve") for p in prod)
                reason = (
                    ""
                    if can_approve
                    else "GitHub says you are not a required reviewer of the production environment."
                    if prod
                    else "This run is not waiting for production approval."
                )
            items.append(
                {
                    "run_id": run["id"],
                    "url": run.get("html_url"),
                    "head_sha": run.get("head_sha"),
                    "created_at": run.get("created_at"),
                    "can_approve": can_approve and env["exists"],
                    "reason": reason if env["exists"] else env["problem"],
                    "evidence": self.evidence(run.get("head_sha", "")),
                }
            )
        return {"environment": env, "runs": items, "confirmation_word": self.s.production_confirmation_word}

    def approve(self, db: Session, user: User, run_id: int, confirmation: str, comment: str) -> dict[str, Any]:
        if self.s.entra_reviewer_role not in (user.roles or []):
            raise ApiError(403, "reviewer_role_required", "This action needs the Reviewer role in the portal.")
        if confirmation != self.s.production_confirmation_word:
            raise ApiError(
                400,
                "confirmation_mismatch",
                f"Type '{self.s.production_confirmation_word}' exactly to approve the production release.",
            )
        env = self.environment_status()
        if not env["exists"] or env["problem"]:
            raise ApiError(409, "environment_unprotected", env["problem"] or "Production environment missing.")
        client = user_client(self.c, db, user, verify_identity=True)
        try:
            pending = client.pending_deployments(run_id)
        except GitHubError as exc:
            raise github_failure(exc) from exc
        prod = [p for p in pending if p.get("environment", {}).get("name") == self.s.production_environment]
        if not prod:
            raise ApiError(409, "not_pending", "This run is not waiting for production approval.")
        if not all(p.get("current_user_can_approve") for p in prod):
            record(
                db,
                user=user,
                github_login=client.login,
                identity="user",
                action="production_approve",
                target_type="deployment",
                target_ref=f"run {run_id}",
                outcome="blocked_precheck",
                detail="not a required reviewer",
            )
            raise ApiError(
                403,
                "not_required_reviewer",
                "GitHub says you are not a required reviewer of the production environment.",
            )
        env_ids = [int(p["environment"]["id"]) for p in prod]
        text = (comment or "").strip()[:1000] or "Approved in the AISDLC Portal after reviewing release evidence."
        try:
            client.review_deployment(run_id, env_ids, "approved", text)
        except GitHubError as exc:
            record(
                db,
                user=user,
                github_login=client.login,
                identity="user",
                action="production_approve",
                target_type="deployment",
                target_ref=f"run {run_id}",
                outcome="rejected",
                github_status=exc.status,
                detail=exc.message,
            )
            raise github_failure(exc) from exc
        record(
            db,
            user=user,
            github_login=client.login,
            identity="user",
            action="production_approve",
            target_type="deployment",
            target_ref=f"run {run_id}",
            outcome="ok",
            github_status=200,
        )
        return {"run_id": run_id, "github_login": client.login, "state": "approved"}
