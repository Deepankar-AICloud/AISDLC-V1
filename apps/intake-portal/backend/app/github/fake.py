"""In-memory fake of the GitHub REST API plus a simulation of the AISDLC workflows.

Used by the test suite and by local development (GITHUB_MODE=fake, development
only). It is plugged in as an `httpx.MockTransport`, so the real clients, guards
and retry logic are exercised end to end. It records which login made each
request, which lets tests prove that comments and reviews were made by the user
and never by the service identity.

It models the behaviour that matters for the portal:
- the CodeQL gate removes `sdlc:start` and starts a run; readiness is the same
  keyword check as `config/readiness.yml`; missing items add `sdlc:awaiting-info`
  and a "Generation blocked" comment; a human comment resumes the run;
- each stage opens a `sdlc/issue-<n>/<agent>` PR authored by github-actions[bot];
- any approving review merges the PR and opens the next stage (like
  artifact-review.yml, which does not check the approver);
- `/agent` and `/model` comments get acknowledgements like feedback-handler.yml;
- GitHub's own refusals: approving your own PR, reviewing a closed PR, no access
  to a private repo, bad credentials, rate limits, deployment reviews by
  non-reviewers.
"""

from __future__ import annotations

import base64
import hashlib
import itertools
import json
import re
import secrets
import threading
from dataclasses import dataclass, field
from datetime import UTC, datetime
from typing import Any
from urllib.parse import parse_qs

import httpx

BOT = "aisdlc-portal[bot]"
ACTIONS = "github-actions[bot]"
STAGES = ["brd", "prd", "epic", "architecture", "nfr", "task", "code"]
READINESS = {
    "business_problem": [
        "problem",
        "pain",
        "need",
        "request",
        "require",
        "cannot",
        "unable",
        "lack",
        "want",
        "missing",
    ],
    "business_objective": [
        "objective",
        "goal",
        "outcome",
        "so that",
        "enable",
        "provide",
        "allow",
        "improve",
        "reduce",
        "access",
        "support",
        "automate",
    ],
    "stakeholders": [
        "employee",
        "manager",
        "user",
        "stakeholder",
        "customer",
        "admin",
        "reviewer",
        "role",
        "team",
        "security",
        "auditor",
    ],
}
DEFAULT_CODEOWNERS = """# fake repository owners
*                 @bob-gh
/docs/            @acme/architects @dave-gh
/reports/         @dave-gh
"""


def now() -> str:
    return datetime.now(UTC).strftime("%Y-%m-%dT%H:%M:%SZ")


def sha(*parts: Any) -> str:
    return hashlib.sha1(("|".join(map(str, parts)) + secrets.token_hex(4)).encode()).hexdigest()  # noqa: S324


@dataclass
class Failure:
    method: str
    pattern: re.Pattern[str]
    status: int
    body: dict[str, Any]
    headers: dict[str, str]
    times: int


@dataclass
class FakeState:
    issues: dict[int, dict[str, Any]] = field(default_factory=dict)
    comments: dict[int, list[dict[str, Any]]] = field(default_factory=dict)
    pulls: dict[int, dict[str, Any]] = field(default_factory=dict)
    pull_files: dict[int, list[dict[str, Any]]] = field(default_factory=dict)
    reviews: dict[int, list[dict[str, Any]]] = field(default_factory=dict)
    files: dict[str, dict[str, bytes]] = field(default_factory=dict)  # branch -> path -> bytes
    refs: dict[str, str] = field(default_factory=dict)
    commits: dict[str, dict[str, Any]] = field(default_factory=dict)
    blobs: dict[str, bytes] = field(default_factory=dict)
    trees: dict[str, dict[str, Any]] = field(default_factory=dict)
    runs: list[dict[str, Any]] = field(default_factory=list)
    label_log: list[tuple[int, str, str, str]] = field(default_factory=list)  # issue, action, label, login
    request_log: list[tuple[str, str, str]] = field(default_factory=list)  # method, path, login


class FakeGitHub:
    def __init__(
        self, owner: str = "acme", repo: str = "aisdlc-test", *, private: bool = True, simulate_pipeline: bool = True
    ) -> None:
        self.owner, self.repo, self.private = owner, repo, private
        self.simulate_pipeline = simulate_pipeline
        self.lock = threading.RLock()
        self.s = FakeState()
        self._numbers = itertools.count(1)
        self._ids = itertools.count(1000)
        self.users: dict[str, dict[str, Any]] = {}
        self.tokens: dict[str, str] = {}
        self.refresh_tokens: dict[str, str] = {}
        self.oauth_codes: dict[str, str] = {}
        self.permissions: dict[str, str] = {}
        self.teams: dict[str, set[str]] = {"acme/architects": {"bob-gh"}}
        self.protection: dict[str, Any] | None = {
            "required_pull_request_reviews": {
                "required_approving_review_count": 1,
                "require_code_owner_reviews": True,
                "require_last_push_approval": False,
            },
            "enforce_admins": {"enabled": True},
        }
        self.protection_readable = True
        self.environments: dict[str, dict[str, Any]] = {}
        self.pending: dict[int, list[dict[str, Any]]] = {}
        self.failures: list[Failure] = []
        self.model_gate = False
        self.installation_token = "ghs_fakeinstallation" + secrets.token_hex(8)
        for login, perm in [
            ("alice-gh", "triage"),
            ("bob-gh", "write"),
            ("carol-gh", "write"),
            ("dave-gh", "write"),
            ("erin-gh", "write"),
            ("admin-gh", "write"),
            ("mallory-gh", "none"),
        ]:
            self.add_user(login, perm)
        self.users[ACTIONS] = {"login": ACTIONS, "id": 41898282, "type": "Bot"}
        self.users[BOT] = {"login": BOT, "id": 99999999, "type": "Bot"}
        self.tokens[self.installation_token] = BOT
        main = sha("main")
        self.s.refs["main"] = main
        self.s.commits[main] = {"sha": main, "tree": {"sha": "tree-main"}, "parents": []}
        self.s.files["main"] = {
            ".github/CODEOWNERS": DEFAULT_CODEOWNERS.encode(),
            "README.md": b"# fake repo\n",
        }
        self.set_production_reviewers(["erin-gh"])

    # ------------------------------------------------------------- setup helpers
    def add_user(self, login: str, permission: str) -> None:
        self.users[login] = {"login": login, "id": 5000 + len(self.users), "type": "User"}
        self.permissions[login] = permission

    def token_for(self, login: str) -> str:
        tok = "ghu_fake" + secrets.token_hex(12)
        self.tokens[tok] = login
        return tok

    def issue_oauth_code(self, login: str) -> str:
        code = "code_" + secrets.token_hex(8)
        self.oauth_codes[code] = login
        return code

    def revoke(self, token: str) -> None:
        self.tokens.pop(token, None)

    def revoke_login(self, login: str) -> None:
        for t, lg in list(self.tokens.items()):
            if lg == login:
                self.tokens.pop(t)

    def fail_next(
        self,
        method: str,
        path_regex: str,
        status: int,
        body: dict[str, Any] | None = None,
        headers: dict[str, str] | None = None,
        times: int = 1,
    ) -> None:
        self.failures.append(
            Failure(
                method.upper(),
                re.compile(path_regex),
                status,
                body or {"message": "Injected failure"},
                headers or {},
                times,
            )
        )

    def set_production_reviewers(self, logins: list[str] | None) -> None:
        if logins is None:
            self.environments.pop("production", None)
            return
        self.environments["production"] = {
            "id": 777,
            "name": "production",
            "protection_rules": [
                {
                    "type": "required_reviewers",
                    "reviewers": [
                        {"type": "User", "reviewer": {"login": lg, "id": self.users[lg]["id"]}} for lg in logins
                    ],
                }
            ],
        }

    # ------------------------------------------------------------- transport
    def transport(self) -> httpx.MockTransport:
        return httpx.MockTransport(self.handle)

    def handle(self, request: httpx.Request) -> httpx.Response:
        with self.lock:
            return self._handle(request)

    def _json(self, status: int, data: Any, headers: dict[str, str] | None = None) -> httpx.Response:
        return httpx.Response(status, json=data, headers=headers or {})

    def _err(self, status: int, message: str, errors: list[str] | None = None) -> httpx.Response:
        body: dict[str, Any] = {"message": message, "documentation_url": "https://docs.github.com/rest"}
        if errors:
            body["errors"] = errors
        return self._json(status, body)

    def _handle(self, req: httpx.Request) -> httpx.Response:
        path = req.url.path
        method = req.method.upper()
        payload: Any = None
        if req.content:
            ctype = req.headers.get("content-type", "")
            payload = (
                json.loads(req.content)
                if "json" in ctype
                else {k: v[0] for k, v in parse_qs(req.content.decode()).items()}
            )
        params = {k: v for k, v in req.url.params.items()}
        if path == "/login/oauth/access_token":
            return self._oauth(payload or {})
        auth = req.headers.get("authorization", "")
        token = auth.split(" ", 1)[1] if " " in auth else ""
        login = self.tokens.get(token)
        self.s.request_log.append((method, path, login or "anonymous"))
        for f in list(self.failures):
            if f.method == method and f.pattern.search(path):
                f.times -= 1
                if f.times <= 0:
                    self.failures.remove(f)
                return self._json(f.status, f.body, f.headers)
        if token and login is None:
            return self._err(401, "Bad credentials")
        if not token:
            return self._err(401, "Requires authentication")
        if path == "/user":
            if login == BOT:
                return self._err(403, "Resource not accessible by integration")
            return self._json(200, self.users[login or ""])
        if path == "/search/issues":
            return self._search(params.get("q", ""))
        m = re.fullmatch(r"/orgs/([^/]+)/teams/([^/]+)/memberships/([^/]+)", path)
        if m:
            members = self.teams.get(f"{m.group(1)}/{m.group(2)}", set())
            return (
                self._json(200, {"state": "active", "role": "member"})
                if m.group(3) in members
                else self._err(404, "Not Found")
            )
        base = f"/repos/{self.owner}/{self.repo}"
        if not path.startswith(base):
            return self._err(404, "Not Found")
        if self.private and login != BOT and self.permissions.get(login or "", "none") == "none":
            return self._err(404, "Not Found")
        rest = path[len(base) :]
        return self._route(method, rest, payload or {}, params, login or "")

    # ------------------------------------------------------------- routing
    def _route(self, method: str, rest: str, p: dict[str, Any], q: dict[str, str], login: str) -> httpx.Response:
        routes: list[tuple[str, str, Any]] = [
            ("GET", r"", lambda: self._json(200, self._repo())),
            ("POST", r"/issues", lambda: self._create_issue(p, login)),
            ("GET", r"/issues/(\d+)", lambda n: self._get_issue(int(n))),
            ("POST", r"/issues/(\d+)/labels", lambda n: self._add_labels(int(n), p, login)),
            ("GET", r"/issues/(\d+)/comments", lambda n: self._list_comments(int(n), q)),
            ("POST", r"/issues/(\d+)/comments", lambda n: self._create_comment(int(n), p, login)),
            ("GET", r"/pulls", lambda: self._list_pulls(q)),
            ("GET", r"/pulls/(\d+)", lambda n: self._get_pull(int(n))),
            ("GET", r"/pulls/(\d+)/files", lambda n: self._page(self.s.pull_files.get(int(n), []), q)),
            ("GET", r"/pulls/(\d+)/reviews", lambda n: self._page(self.s.reviews.get(int(n), []), q)),
            ("POST", r"/pulls/(\d+)/reviews", lambda n: self._create_review(int(n), p, login)),
            ("GET", r"/collaborators/([^/]+)/permission", lambda u: self._permission(u)),
            ("GET", r"/contents/(.+)", lambda fp: self._contents(fp, q.get("ref", "main"))),
            ("GET", r"/branches/([^/]+)/protection", lambda b: self._protection(b)),
            ("GET", r"/rules/branches/([^/]+)", lambda b: self._json(200, [])),
            ("GET", r"/codeowners/errors", lambda: self._json(200, {"errors": []})),
            ("GET", r"/git/ref/heads/(.+)", lambda b: self._get_ref(b)),
            ("GET", r"/git/commits/([0-9a-f]+)", lambda c: self._json(200, self.s.commits[c])),
            ("POST", r"/git/blobs", lambda: self._blob(p)),
            ("POST", r"/git/trees", lambda: self._tree(p)),
            ("POST", r"/git/commits", lambda: self._commit(p)),
            ("POST", r"/git/refs", lambda: self._create_ref(p, login)),
            ("GET", r"/actions/runs", lambda: self._runs(q, None)),
            ("GET", r"/actions/workflows/([^/]+)/runs", lambda wf: self._runs(q, wf)),
            ("GET", r"/actions/runs/(\d+)/pending_deployments", lambda r: self._get_pending(int(r), login)),
            ("POST", r"/actions/runs/(\d+)/pending_deployments", lambda r: self._review_deploy(int(r), p, login)),
            ("GET", r"/environments/([^/]+)", lambda e: self._environment(e)),
        ]
        for m, pattern, fn in routes:
            if m == method:
                mt = re.fullmatch(pattern, rest)
                if mt:
                    return fn(*mt.groups())
        return self._err(404, "Not Found")

    def _page(self, items: list[Any], q: dict[str, str]) -> httpx.Response:
        per = int(q.get("per_page", 30))
        page = int(q.get("page", 1))
        return self._json(200, items[(page - 1) * per : page * per])

    def _repo(self) -> dict[str, Any]:
        return {
            "full_name": f"{self.owner}/{self.repo}",
            "private": self.private,
            "default_branch": "main",
            "html_url": f"https://github.test/{self.owner}/{self.repo}",
        }

    # ------------------------------------------------------------- issues
    def _issue_url(self, n: int) -> str:
        return f"https://github.test/{self.owner}/{self.repo}/issues/{n}"

    def _create_issue(self, p: dict[str, Any], login: str) -> httpx.Response:
        n = next(self._numbers)
        issue = {
            "number": n,
            "title": p.get("title", ""),
            "body": p.get("body", ""),
            "state": "open",
            "labels": [],
            "user": self.users[login],
            "html_url": self._issue_url(n),
            "created_at": now(),
            "updated_at": now(),
        }
        if len(issue["body"]) > 65536:
            return self._err(422, "Validation Failed", ["body is too long (maximum is 65536 characters)"])
        self.s.issues[n] = issue
        self.s.comments[n] = []
        for lbl in p.get("labels", []) or []:
            self._label(n, lbl, "add", login)
        return self._json(201, issue)

    def _get_issue(self, n: int) -> httpx.Response:
        if n in self.s.issues:
            return self._json(200, self.s.issues[n])
        if n in self.s.pulls:
            pr = self.s.pulls[n]
            return self._json(200, {**pr, "pull_request": {"url": pr["url"]}})
        return self._err(404, "Not Found")

    def _label(self, n: int, label: str, action: str, login: str) -> None:
        target = self.s.issues.get(n) or self.s.pulls.get(n)
        if target is None:
            return
        names = [lb["name"] for lb in target["labels"]]
        if action == "add" and label not in names:
            target["labels"].append({"name": label})
        if action == "remove":
            target["labels"] = [lb for lb in target["labels"] if lb["name"] != label]
        self.s.label_log.append((n, action, label, login))

    def labels(self, n: int) -> list[str]:
        return [lb["name"] for lb in (self.s.issues.get(n) or self.s.pulls[n])["labels"]]

    def _add_labels(self, n: int, p: dict[str, Any], login: str) -> httpx.Response:
        if n not in self.s.issues:
            return self._err(404, "Not Found")
        for lbl in p.get("labels", []):
            self._label(n, lbl, "add", login)
            if lbl == "sdlc:start" and self.simulate_pipeline:
                self._gate_dispatch(n)
        return self._json(200, self.s.issues[n]["labels"])

    def _list_comments(self, n: int, q: dict[str, str]) -> httpx.Response:
        if n not in self.s.comments:
            return self._err(404, "Not Found")
        return self._page(self.s.comments[n], q)

    def _add_comment(self, n: int, body: str, login: str) -> dict[str, Any]:
        c = {
            "id": next(self._ids),
            "body": body,
            "user": self.users[login],
            "created_at": now(),
            "html_url": f"{self._issue_url(n)}#issuecomment-{len(self.s.comments.get(n, []))}",
            "author_association": "OWNER"
            if login.endswith("[bot]")
            else ("COLLABORATOR" if self.permissions.get(login) in ("write", "admin", "maintain") else "CONTRIBUTOR"),
        }
        self.s.comments.setdefault(n, []).append(c)
        return c

    def _create_comment(self, n: int, p: dict[str, Any], login: str) -> httpx.Response:
        if n not in self.s.issues and n not in self.s.pulls:
            return self._err(404, "Not Found")
        body = str(p.get("body", ""))
        if len(body) > 65536:
            return self._err(422, "Validation Failed", ["body is too long (maximum is 65536 characters)"])
        if self.private and login != BOT and self.permissions.get(login) in (None, "none"):
            return self._err(404, "Not Found")
        c = self._add_comment(n, body, login)
        if self.simulate_pipeline:
            self._on_comment(n, body, login)
        return self._json(201, c)

    def _search(self, q: str) -> httpx.Response:
        terms = re.findall(r'"([^"]+)"', q)
        items = [i for i in self.s.issues.values() if all(t in i["body"] for t in terms)]
        return self._json(200, {"total_count": len(items), "items": items})

    # ------------------------------------------------------------- pulls & reviews
    def _list_pulls(self, q: dict[str, str]) -> httpx.Response:
        prs = sorted(self.s.pulls.values(), key=lambda pr: -pr["number"])
        state = q.get("state", "open")
        if state != "all":
            prs = [pr for pr in prs if pr["state"] == state]
        return self._page(prs, q)

    def _get_pull(self, n: int) -> httpx.Response:
        return self._json(200, self.s.pulls[n]) if n in self.s.pulls else self._err(404, "Not Found")

    def _create_review(self, n: int, p: dict[str, Any], login: str) -> httpx.Response:
        pr = self.s.pulls.get(n)
        if pr is None:
            return self._err(404, "Not Found")
        if login == BOT:
            return self._err(403, "Resource not accessible by integration")
        event = p.get("event")
        if pr["state"] != "open":
            return self._err(
                422,
                "Unprocessable Entity",
                [f"Can not {'approve' if event == 'APPROVE' else 'review'} a closed pull request"],
            )
        if pr["user"]["login"] == login and event in ("APPROVE", "REQUEST_CHANGES"):
            verb = "approve" if event == "APPROVE" else "request changes on"
            return self._err(422, "Unprocessable Entity", [f"Can not {verb} your own pull request"])
        if self.permissions.get(login) in (None, "none") and self.private:
            return self._err(404, "Not Found")
        review = {
            "id": next(self._ids),
            "user": self.users[login],
            "state": {"APPROVE": "APPROVED", "REQUEST_CHANGES": "CHANGES_REQUESTED"}.get(str(event), "COMMENTED"),
            "body": p.get("body", ""),
            "commit_id": p.get("commit_id") or pr["head"]["sha"],
            "submitted_at": now(),
        }
        self.s.reviews.setdefault(n, []).append(review)
        if event == "APPROVE" and self.simulate_pipeline and pr["head"]["ref"].startswith("sdlc/issue-"):
            self._artifact_review(pr, login)
        return self._json(200, review)

    def _permission(self, user: str) -> httpx.Response:
        perm = self.permissions.get(user, "read" if not self.private else "none")
        return self._json(
            200,
            {
                "permission": {"triage": "read"}.get(perm, perm),
                "role_name": perm,
                "user": self.users.get(user, {"login": user}),
            },
        )

    def _contents(self, fp: str, ref: str) -> httpx.Response:
        if ref not in self.s.files:  # a commit sha: resolve to the branch (or PR head) that points at it
            branches = [b for b, h in self.s.refs.items() if h == ref]
            heads = [pr["head"]["ref"] for pr in self.s.pulls.values() if pr["head"]["sha"] == ref]
            ref = (branches or heads or [ref])[0]
        data = self.s.files.get(ref, {}).get(fp)
        if data is None:
            return self._err(404, "Not Found")
        return self._json(
            200,
            {
                "path": fp,
                "encoding": "base64",
                "content": base64.b64encode(data).decode(),
                "sha": hashlib.sha1(data).hexdigest(),
            },
        )  # noqa: S324

    def _protection(self, branch: str) -> httpx.Response:
        if not self.protection_readable:
            return self._err(403, "Resource not accessible by integration")
        if branch != "main" or self.protection is None:
            return self._err(404, "Branch not protected")
        return self._json(200, self.protection)

    # ------------------------------------------------------------- git data
    def _get_ref(self, branch: str) -> httpx.Response:
        if branch not in self.s.refs:
            return self._err(404, "Not Found")
        return self._json(200, {"ref": f"refs/heads/{branch}", "object": {"sha": self.s.refs[branch]}})

    def _blob(self, p: dict[str, Any]) -> httpx.Response:
        data = base64.b64decode(p["content"]) if p.get("encoding") == "base64" else str(p["content"]).encode()
        h = hashlib.sha1(data).hexdigest()  # noqa: S324
        self.s.blobs[h] = data
        return self._json(201, {"sha": h})

    def _tree(self, p: dict[str, Any]) -> httpx.Response:
        h = sha("tree")
        self.s.trees[h] = p
        return self._json(201, {"sha": h})

    def _commit(self, p: dict[str, Any]) -> httpx.Response:
        h = sha("commit")
        self.s.commits[h] = {
            "sha": h,
            "tree": {"sha": p["tree"]},
            "parents": [{"sha": x} for x in p["parents"]],
            "message": p["message"],
        }
        return self._json(201, self.s.commits[h])

    def _create_ref(self, p: dict[str, Any], login: str) -> httpx.Response:
        branch = p["ref"].removeprefix("refs/heads/")
        if branch in self.s.refs:
            return self._err(422, "Reference already exists")
        self.s.refs[branch] = p["sha"]
        tree = self.s.trees[self.s.commits[p["sha"]]["tree"]["sha"]]
        files = dict(self.s.files["main"])
        for entry in tree["tree"]:
            files[entry["path"]] = self.s.blobs[entry["sha"]]
        self.s.files[branch] = files
        return self._json(201, {"ref": p["ref"], "object": {"sha": p["sha"]}})

    # ------------------------------------------------------------- actions
    def _runs(self, q: dict[str, str], workflow: str | None) -> httpx.Response:
        runs = [r for r in self.s.runs if workflow is None or r["path"].endswith(workflow)]
        if "status" in q:
            runs = [r for r in runs if r["status"] == q["status"]]
        if "head_sha" in q:
            runs = [r for r in runs if r["head_sha"] == q["head_sha"]]
        runs = sorted(runs, key=lambda r: -r["id"])
        return self._json(200, {"total_count": len(runs), "workflow_runs": runs})

    def add_run(
        self,
        workflow_file: str,
        name: str,
        display_title: str,
        status: str = "completed",
        conclusion: str | None = "success",
        head_sha: str | None = None,
    ) -> dict[str, Any]:
        rid = next(self._ids)
        run = {
            "id": rid,
            "name": name,
            "path": f".github/workflows/{workflow_file}",
            "display_title": display_title,
            "status": status,
            "conclusion": conclusion if status == "completed" else None,
            "head_sha": head_sha or self.s.refs["main"],
            "event": "workflow_dispatch",
            "html_url": f"https://github.test/{self.owner}/{self.repo}/actions/runs/{rid}",
            "created_at": now(),
            "updated_at": now(),
        }
        self.s.runs.append(run)
        return run

    def _environment(self, name: str) -> httpx.Response:
        env = self.environments.get(name)
        return self._json(200, env) if env else self._err(404, "Not Found")

    def _env_reviewers(self, env: dict[str, Any]) -> set[str]:
        out: set[str] = set()
        for rule in env.get("protection_rules", []):
            if rule.get("type") == "required_reviewers":
                out |= {r["reviewer"]["login"] for r in rule.get("reviewers", []) if r["type"] == "User"}
        return out

    def _get_pending(self, run_id: int, login: str) -> httpx.Response:
        envs = self.pending.get(run_id, [])
        out = []
        for env in envs:
            reviewers = self._env_reviewers(env)
            out.append(
                {
                    "environment": {"id": env["id"], "name": env["name"]},
                    "wait_timer": 0,
                    "current_user_can_approve": login in reviewers,
                    "reviewers": [{"type": "User", "reviewer": self.users[r]} for r in sorted(reviewers)],
                }
            )
        return self._json(200, out)

    def _review_deploy(self, run_id: int, p: dict[str, Any], login: str) -> httpx.Response:
        if login == BOT:
            return self._err(403, "Resource not accessible by integration")
        envs = self.pending.get(run_id, [])
        if not envs:
            return self._err(422, "Unprocessable Entity", ["No pending deployments for this run"])
        for env in envs:
            if env["id"] in p.get("environment_ids", []) and login not in self._env_reviewers(env):
                return self._err(
                    422, "Unprocessable Entity", [f"{login} is not a required reviewer for environment {env['name']}"]
                )
        run = next(r for r in self.s.runs if r["id"] == run_id)
        run["status"] = "in_progress" if p.get("state") == "approved" else "completed"
        if p.get("state") == "rejected":
            run["conclusion"] = "failure"
        self.pending.pop(run_id, None)
        return self._json(
            200,
            [
                {
                    "id": next(self._ids),
                    "environment": envs[0]["name"],
                    "state": p.get("state"),
                    "creator": self.users[login],
                }
            ],
        )

    def start_production_run(self) -> dict[str, Any]:
        head = self.s.refs["main"]
        for wf, name in [
            ("ci.yml", "CI — SmartServe Build & Test"),
            ("codeql.yml", "CodeQL"),
            ("security.yml", "Security — Secret Scan"),
            ("deploy-dev.yml", "Deploy — DEV"),
            ("deploy-staging.yml", "Deploy — STAGING"),
        ]:
            self.add_run(wf, name, name, head_sha=head)
        run = self.add_run(
            "deploy-production.yml", "Deploy — PRODUCTION", "Deploy — PRODUCTION", status="waiting", head_sha=head
        )
        if "production" in self.environments:
            self.pending[run["id"]] = [self.environments["production"]]
        return run

    # ------------------------------------------------------------- oauth
    def _oauth(self, p: dict[str, Any]) -> httpx.Response:
        if p.get("grant_type") == "refresh_token":
            login = self.refresh_tokens.pop(p.get("refresh_token", ""), None)
            if login is None:
                return self._json(
                    200, {"error": "bad_refresh_token", "error_description": "The refresh token is invalid"}
                )
        else:
            login = self.oauth_codes.pop(p.get("code", ""), None)
            if login is None:
                return self._json(
                    200,
                    {"error": "bad_verification_code", "error_description": "The code passed is incorrect or expired."},
                )
        access = self.token_for(login)
        refresh = "ghr_fake" + secrets.token_hex(12)
        self.refresh_tokens[refresh] = login
        return self._json(
            200,
            {
                "access_token": access,
                "expires_in": 28800,
                "refresh_token": refresh,
                "refresh_token_expires_in": 15897600,
                "token_type": "bearer",
                "scope": "",
            },
        )

    # ------------------------------------------------------------- AISDLC simulation
    def _gate_dispatch(self, n: int) -> None:
        """agentic-sdlc-codeql-gate.yml: remove sdlc:start, dispatch the orchestrator."""
        self._label(n, "sdlc:start", "remove", ACTIONS)
        self._orchestrate(n)

    def _context(self, n: int) -> str:
        issue = self.s.issues[n]
        # Mirrors agentic-sdlc.yml: comments from triage-or-higher users, plus the trusted portal
        # bot's "[Part k/n" continuation comments (SDLC_TRUSTED_CONTEXT_BOTS).
        human = [
            c["body"]
            for c in self.s.comments[n]
            if (
                self.permissions.get(c["user"]["login"]) in ("triage", "write", "maintain", "admin")
                and not c["body"].startswith(("/model ", "/agent "))
            )
            or (c["user"]["login"] == BOT and c["body"].startswith("[Part "))
        ]
        return f"TITLE: {issue['title']}\n\nBODY:\n{issue['body']}\n\nHUMAN COMMENTS:\n" + "\n---\n".join(human)

    def _orchestrate(self, n: int) -> None:
        self.add_run("agentic-sdlc.yml", "Agentic SDLC Orchestrator", f"Agentic SDLC issue #{n}")
        ctx = self._context(n).lower()
        missing = [k for k, kws in READINESS.items() if not any(w in ctx for w in kws)]
        if missing:
            qs = "\n".join(f"- Please provide: {m.replace('_', ' ')}." for m in missing)
            self._add_comment(
                n,
                "## ⛔ Generation blocked — required information missing (BRD_GENERATION)\n\n"
                "Status: **BLOCKED_MISSING_INFORMATION**\n\nPlease provide the following so "
                f"generation can proceed (the agent will\n**not** invent these):\n\n{qs}\n\n"
                "Add the details to this issue and re-run, or dispatch `agentic-sdlc.yml`.",
                ACTIONS,
            )
            self._label(n, "sdlc:awaiting-info", "add", ACTIONS)
            return
        self._label(n, "sdlc:awaiting-info", "remove", ACTIONS)
        if self.model_gate and not self.s.issues[n].get("_model_ok"):
            self._add_comment(
                n,
                "## 🤖 AI Model Recommendation — BRD_GENERATION\n\n**Recommended model:** "
                "`gpt-5`\n**Selection mode:** RECOMMENDED\n\n- `/model approve`",
                ACTIONS,
            )
            return
        self.open_stage_pr(n, self.s.issues[n].get("_stage_idx", 0))

    def _on_comment(self, n: int, body: str, login: str) -> None:
        if login in (ACTIONS, "github-actions"):
            return
        target_issue = n
        pr = self.s.pulls.get(n)
        if pr:
            target_issue = int(re.match(r"sdlc/issue-(\d+)/", pr["head"]["ref"]).group(1))  # type: ignore[union-attr]
        if body.startswith("/agent "):
            cmd = body.split()[1] if len(body.split()) > 1 else ""
            if cmd not in ("revise", "regenerate", "rerun-qc", "explain", "status", "impact"):
                self._add_comment(n, "❌ Unknown or disallowed command.", ACTIONS)
                return
            self._add_comment(n, f"🔁 `/agent {cmd}` accepted for #{n} (requested by @{login}).", ACTIONS)
            if cmd in ("revise", "regenerate") and pr:
                pr["head"]["sha"] = sha("rev")
                pr["body"] += f"\n\n_Revised after feedback from @{login}._"
            return
        if body.startswith("/model "):
            self._add_comment(
                n, f"✅ Model decision recorded (`{body.strip()}`) by @{login}. Resuming the stage…", ACTIONS
            )
            if target_issue in self.s.issues:
                self.s.issues[target_issue]["_model_ok"] = True
                self._orchestrate(target_issue)
            return
        if pr is None and "sdlc:awaiting-info" in self.labels(n):
            # agentic-sdlc-codeql-gate.yml resume path: users with triage access or more (never bots).
            if login.endswith("[bot]") or self.permissions.get(login) not in ("triage", "write", "maintain", "admin"):
                return
            self._label(n, "sdlc:awaiting-info", "remove", ACTIONS)
            self._orchestrate(n)

    def open_stage_pr(self, issue: int, idx: int) -> dict[str, Any]:
        agent = STAGES[idx]
        n = next(self._numbers)
        branch = f"sdlc/issue-{issue}/{agent}"
        head = sha(branch)
        run_id = f"run-{issue}-{agent}"
        artifact = f"docs/sdlc/issue-{issue}/{agent}.md"
        report = f"reports/{run_id}/quality-report.md"
        doc = (
            f"# {agent.upper()} for issue #{issue}\n\n## Summary\n\nGenerated {agent} artifact.\n\n"
            "```mermaid\nflowchart LR\n  A[Requester] --> B[Portal] --> C[AISDLC]\n```\n\n"
            "| ID | Requirement |\n|---|---|\n| BRD-REQ-1 | Track access requests |\n"
        )
        qc = (
            "# Quality Report\n\n| Stage | Agent | QC Score | Status | Retry |\n|---|---|---|---|---|\n"
            f"| {agent.upper()}_GENERATION | {agent} | 0.86 | PASS | 0 |\n\n**Average QC score:** 0.86\n\n"
            "## Findings\n\n- Assumption recorded: scope boundaries inferred.\n"
        )
        files = dict(self.s.files["main"])
        files[artifact] = doc.encode()
        files[report] = qc.encode()
        self.s.files[branch] = files
        self.s.refs[branch] = head
        body = (
            "## AI Generation Summary\n\n"
            f"- **Run ID:** `{run_id}`\n- **Agent / Artifact:** {agent} — {agent.upper()}_GENERATION\n"
            f"- **Source:** issue #{issue}\n- **Readiness:** READY_WITH_ASSUMPTIONS\n- **Assumptions:** scope\n"
            "- **Recommended model:** gpt-5\n- **Selected model:** gpt-5 (recommended, mode RECOMMENDED)\n"
            "- **QC:** PASS 0.86 (threshold per `config/quality-gates.yml`)\n- **Retries:** 0\n"
            "- **Tokens / Cost:** N/A (provider does not report usage via Copilot CLI)\n\n"
            "Review and **approve** to advance, or comment `/agent revise <notes>` to request a targeted change."
        )
        pr = {
            "number": n,
            "title": f"[SDLC] {agent} artifact — issue #{issue}",
            "body": body,
            "state": "open",
            "merged": False,
            "draft": False,
            "user": self.users[ACTIONS],
            "labels": [{"name": "sdlc:review"}],
            "head": {"ref": branch, "sha": head},
            "base": {"ref": "main", "sha": self.s.refs["main"]},
            "html_url": f"https://github.test/{self.owner}/{self.repo}/pull/{n}",
            "url": f"https://api.github.test/repos/{self.owner}/{self.repo}/pulls/{n}",
            "created_at": now(),
            "updated_at": now(),
            "merged_at": None,
        }
        self.s.pulls[n] = pr
        self.s.comments[n] = []
        self.s.pull_files[n] = [
            {
                "filename": artifact,
                "status": "added",
                "additions": doc.count("\n"),
                "deletions": 0,
                "patch": "@@ -0,0 +1 @@\n" + "\n".join("+" + ln for ln in doc.splitlines()),
            },
            {
                "filename": report,
                "status": "added",
                "additions": qc.count("\n"),
                "deletions": 0,
                "patch": "@@ -0,0 +1 @@\n" + "\n".join("+" + ln for ln in qc.splitlines()),
            },
        ]
        self.s.issues[issue]["_stage_idx"] = idx
        return pr

    def _artifact_review(self, pr: dict[str, Any], approver: str) -> None:
        """artifact-review.yml: any approval merges the PR and starts the next stage."""
        pr["state"] = "closed"
        pr["merged"] = True
        pr["merged_at"] = now()
        issue = int(re.match(r"sdlc/issue-(\d+)/", pr["head"]["ref"]).group(1))  # type: ignore[union-attr]
        new_main = sha("merge")
        self.s.commits[new_main] = {"sha": new_main, "tree": {"sha": "t"}, "parents": []}
        self.s.files["main"] = dict(self.s.files[pr["head"]["ref"]])
        self.s.refs["main"] = new_main
        self.add_run("artifact-review.yml", "Agentic SDLC — Artifact Review & Resume", "Artifact Review")
        idx = STAGES.index(pr["head"]["ref"].rsplit("/", 1)[1]) + 1
        if idx < len(STAGES):
            self.open_stage_pr(issue, idx)
        else:
            self._add_comment(issue, "## ✅ Agentic generation stages complete", ACTIONS)
