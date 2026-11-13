"""The two GitHub identities. They are separate classes and are never mixed.

ServiceGitHubClient (GitHub App installation token)
    May only: read, create the intake issue, add `sdlc:start`, post overflow
    `[Part k/n of ...]` comments, and create an `intake/*` branch. It has no
    method to comment freely, review, approve, run `/agent` or `/model`, or
    approve deployments, and its request guard refuses those calls even if code
    tried to make them. The installation token is also requested with
    `pull_requests: read`, so GitHub itself would reject a review.

UserGitHubClient (GitHub App user access token of one signed-in user)
    Used for every comment, review, approval, command and deployment review,
    so GitHub records the real person and applies branch protection and
    CODEOWNERS normally.
"""

from __future__ import annotations

import base64
import re
from collections.abc import Callable
from typing import Any

from .commands import PART_PREFIX
from .http import GitHubError, GitHubHTTP, IdentityViolation

START_LABEL = "sdlc:start"
INTAKE_REF_PREFIX = "refs/heads/intake/"


def _repo_re(owner: str, repo: str) -> str:
    return rf"/repos/{re.escape(owner)}/{re.escape(repo)}"


class _GuardedClient:
    identity = "unknown"

    def __init__(self, http: GitHubHTTP, owner: str, repo: str) -> None:
        self.http = http
        self.owner = owner
        self.repo = repo
        self.base = f"/repos/{owner}/{repo}"
        r = _repo_re(owner, repo)
        self._rules = [(m, re.compile(p.replace("{R}", r))) for m, p in self.allowed()]

    def allowed(self) -> list[tuple[str, str]]:
        raise NotImplementedError

    def token(self) -> str:
        raise NotImplementedError

    def check(self, method: str, path: str, json: Any) -> None:
        """Deny by default; subclasses add per-endpoint payload rules."""
        if not any(m == method.upper() and rx.fullmatch(path) for m, rx in self._rules):
            raise IdentityViolation(f"{self.identity} identity may not call {method.upper()} {path}")

    def _call(
        self,
        method: str,
        path: str,
        *,
        json: Any = None,
        params: dict[str, Any] | None = None,
        accept: str | None = None,
    ) -> Any:
        self.check(method, path, json)
        resp = self.http.request(method, path, self.token(), json=json, params=params, accept=accept)
        if resp.status_code == 204 or not resp.content:
            return None
        if accept and "json" not in accept:
            return resp.text
        return resp.json()

    def _paginate(self, path: str, params: dict[str, Any] | None = None, limit: int = 1000) -> list[Any]:
        self.check("GET", path, None)
        return self.http.paginate(path, self.token(), params, limit)

    # ------------------------------------------------------------- shared reads
    def get_repo(self) -> dict[str, Any]:
        return self._call("GET", self.base)

    def get_issue(self, number: int) -> dict[str, Any]:
        return self._call("GET", f"{self.base}/issues/{number}")

    def list_issue_comments(self, number: int) -> list[dict[str, Any]]:
        return self._paginate(f"{self.base}/issues/{number}/comments")

    def get_pull(self, number: int) -> dict[str, Any]:
        return self._call("GET", f"{self.base}/pulls/{number}")

    def list_pulls(self, state: str = "all") -> list[dict[str, Any]]:
        return self._paginate(f"{self.base}/pulls", {"state": state, "sort": "created", "direction": "desc"}, 300)

    def list_pull_files(self, number: int) -> list[dict[str, Any]]:
        return self._paginate(f"{self.base}/pulls/{number}/files", limit=3000)

    def list_pull_reviews(self, number: int) -> list[dict[str, Any]]:
        return self._paginate(f"{self.base}/pulls/{number}/reviews")

    def get_file(self, path: str, ref: str) -> str | None:
        try:
            data = self._call("GET", f"{self.base}/contents/{path}", params={"ref": ref})
        except GitHubError as exc:
            if exc.status == 404:
                return None
            raise
        if not isinstance(data, dict) or data.get("encoding") != "base64":
            return None
        return base64.b64decode(data["content"]).decode("utf-8", errors="replace")


class ServiceGitHubClient(_GuardedClient):
    identity = "service"

    def __init__(self, http: GitHubHTTP, token_provider: Callable[[], str], owner: str, repo: str) -> None:
        self._token_provider = token_provider
        super().__init__(http, owner, repo)

    def token(self) -> str:
        return self._token_provider()

    def allowed(self) -> list[tuple[str, str]]:
        return [
            ("GET", r"{R}"),
            (
                "GET",
                r"{R}/(issues|pulls|contents|branches|rules|codeowners|collaborators|actions|environments|"
                r"git/ref|git/commits|commits|deployments)(/.*)?",
            ),
            ("GET", r"/orgs/[^/]+/teams/[^/]+/memberships/[^/]+"),
            ("GET", r"/search/issues"),
            ("POST", r"{R}/issues"),
            ("POST", r"{R}/issues/\d+/labels"),
            ("POST", r"{R}/issues/\d+/comments"),
            ("POST", r"{R}/git/(blobs|trees|commits|refs)"),
        ]

    def check(self, method: str, path: str, json: Any) -> None:
        super().check(method, path, json)
        if method.upper() != "POST":
            return
        if path.endswith("/labels"):
            if json != {"labels": [START_LABEL]}:
                raise IdentityViolation("service identity may only add the sdlc:start label")
        elif path.endswith("/comments"):
            body = (json or {}).get("body", "")
            if not PART_PREFIX.match(body):
                raise IdentityViolation(
                    "service identity may only post '[Part k/n of ...]' overflow comments; answers, reviews and "
                    "commands must use the signed-in user's own GitHub token"
                )
        elif path.endswith("/issues"):
            if (json or {}).get("labels"):
                raise IdentityViolation("labels must be added in a separate final call after the content")
        elif path.endswith("/git/refs"):
            if not str((json or {}).get("ref", "")).startswith(INTAKE_REF_PREFIX):
                raise IdentityViolation("service identity may only create intake/* branches")
        body_text = str((json or {}).get("body", ""))
        if body_text.lstrip().startswith(("/agent", "/model")):
            raise IdentityViolation("service identity may never issue /agent or /model commands")

    # ------------------------------------------------------------ writes
    def create_issue(self, title: str, body: str) -> dict[str, Any]:
        return self._call("POST", f"{self.base}/issues", json={"title": title, "body": body})

    def post_overflow_part(self, number: int, body: str) -> dict[str, Any]:
        return self._call("POST", f"{self.base}/issues/{number}/comments", json={"body": body})

    def add_start_label(self, number: int) -> Any:
        return self._call("POST", f"{self.base}/issues/{number}/labels", json={"labels": [START_LABEL]})

    def create_intake_branch(self, branch: str, base_branch: str, files: dict[str, bytes], message: str) -> str:
        if not branch.startswith("intake/"):
            raise IdentityViolation("intake branches must start with intake/")
        base_sha = self._call("GET", f"{self.base}/git/ref/heads/{base_branch}")["object"]["sha"]
        base_commit = self._call("GET", f"{self.base}/git/commits/{base_sha}")
        tree = []
        for path, data in files.items():
            blob = self._call(
                "POST",
                f"{self.base}/git/blobs",
                json={"content": base64.b64encode(data).decode(), "encoding": "base64"},
            )
            tree.append({"path": path, "mode": "100644", "type": "blob", "sha": blob["sha"]})
        new_tree = self._call(
            "POST", f"{self.base}/git/trees", json={"base_tree": base_commit["tree"]["sha"], "tree": tree}
        )
        commit = self._call(
            "POST",
            f"{self.base}/git/commits",
            json={"message": message, "tree": new_tree["sha"], "parents": [base_sha]},
        )
        try:
            self._call("POST", f"{self.base}/git/refs", json={"ref": f"refs/heads/{branch}", "sha": commit["sha"]})
        except GitHubError as exc:
            if exc.status != 422:  # 422 = already exists from an earlier attempt of the same request
                raise
        return str(commit["sha"])

    # ------------------------------------------------------------ reads
    def find_issue_by_ref(self, ref: str) -> dict[str, Any] | None:
        q = f'repo:{self.owner}/{self.repo} in:body "aisdlc-portal ref: {ref}"'
        data = self._call("GET", "/search/issues", params={"q": q})
        items = data.get("items", []) if isinstance(data, dict) else []
        return items[0] if items else None

    def collaborator_permission(self, login: str) -> str:
        try:
            data = self._call("GET", f"{self.base}/collaborators/{login}/permission")
        except GitHubError as exc:
            if exc.status == 404:
                return "none"
            raise
        return str(data.get("permission", "none"))

    def collaborator_role(self, login: str) -> str:
        """Repository role (admin, maintain, write, triage, read or none)."""
        try:
            data = self._call("GET", f"{self.base}/collaborators/{login}/permission")
        except GitHubError as exc:
            if exc.status == 404:
                return "none"
            raise
        return str(data.get("role_name") or data.get("permission") or "none")

    def branch_protection(self, branch: str) -> dict[str, Any] | None:
        """None = not protected. Raises GitHubError(403) if the App cannot read it."""
        try:
            return self._call("GET", f"{self.base}/branches/{branch}/protection")
        except GitHubError as exc:
            if exc.status == 404:
                return None
            raise

    def branch_rules(self, branch: str) -> list[dict[str, Any]]:
        try:
            return self._call("GET", f"{self.base}/rules/branches/{branch}") or []
        except GitHubError as exc:
            if exc.status == 404:
                return []
            raise

    def codeowners_errors(self) -> list[dict[str, Any]]:
        try:
            return list((self._call("GET", f"{self.base}/codeowners/errors") or {}).get("errors", []))
        except GitHubError:
            return []

    def team_member(self, org: str, slug: str, login: str) -> bool:
        try:
            data = self._call("GET", f"/orgs/{org}/teams/{slug}/memberships/{login}")
        except GitHubError as exc:
            if exc.status in (403, 404):
                return False
            raise
        return bool(data and data.get("state") == "active")

    def workflow_runs(self, workflow_file: str, **params: Any) -> list[dict[str, Any]]:
        data = self._call(
            "GET", f"{self.base}/actions/workflows/{workflow_file}/runs", params={"per_page": 30, **params}
        )
        return list((data or {}).get("workflow_runs", []))

    def repo_runs(self, **params: Any) -> list[dict[str, Any]]:
        data = self._call("GET", f"{self.base}/actions/runs", params={"per_page": 50, **params})
        return list((data or {}).get("workflow_runs", []))

    def get_environment(self, name: str) -> dict[str, Any] | None:
        try:
            return self._call("GET", f"{self.base}/environments/{name}")
        except GitHubError as exc:
            if exc.status == 404:
                return None
            raise


class UserGitHubClient(_GuardedClient):
    identity = "user"

    def __init__(self, http: GitHubHTTP, token: str, login: str, github_id: int, owner: str, repo: str) -> None:
        self._token = token
        self.login = login
        self.github_id = github_id
        super().__init__(http, owner, repo)

    def token(self) -> str:
        return self._token

    def __repr__(self) -> str:  # never expose the token
        return f"UserGitHubClient(login={self.login!r})"

    def allowed(self) -> list[tuple[str, str]]:
        return [
            ("GET", r"/user"),
            ("GET", r"{R}(/.*)?"),
            ("POST", r"{R}/issues/\d+/comments"),
            ("POST", r"{R}/pulls/\d+/reviews"),
            ("POST", r"{R}/actions/runs/\d+/pending_deployments"),
        ]

    def check(self, method: str, path: str, json: Any) -> None:
        super().check(method, path, json)
        if method.upper() == "POST" and path.endswith("/reviews"):
            if (json or {}).get("event") not in ("APPROVE", "REQUEST_CHANGES", "COMMENT"):
                raise IdentityViolation("invalid review event")

    def whoami(self) -> dict[str, Any]:
        return self._call("GET", "/user")

    def post_comment(self, number: int, body: str) -> dict[str, Any]:
        return self._call("POST", f"{self.base}/issues/{number}/comments", json={"body": body})

    def submit_review(self, pr: int, event: str, body: str, commit_id: str) -> dict[str, Any]:
        payload = {"event": event, "body": body, "commit_id": commit_id}
        return self._call("POST", f"{self.base}/pulls/{pr}/reviews", json=payload)

    def pending_deployments(self, run_id: int) -> list[dict[str, Any]]:
        return self._call("GET", f"{self.base}/actions/runs/{run_id}/pending_deployments") or []

    def review_deployment(self, run_id: int, environment_ids: list[int], state: str, comment: str) -> Any:
        if state not in ("approved", "rejected"):
            raise IdentityViolation("invalid deployment review state")
        return self._call(
            "POST",
            f"{self.base}/actions/runs/{run_id}/pending_deployments",
            json={"environment_ids": environment_ids, "state": state, "comment": comment},
        )
