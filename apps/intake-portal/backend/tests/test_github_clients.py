from __future__ import annotations

import ast
import inspect
from pathlib import Path

import pytest

from app.github import clients as clients_mod
from app.github.clients import ServiceGitHubClient, UserGitHubClient
from app.github.fake import BOT, FakeGitHub
from app.github.http import GitHubError, GitHubHTTP, IdentityViolation

APP_DIR = Path(__file__).resolve().parents[1] / "app"


@pytest.fixture
def fake():
    return FakeGitHub(simulate_pipeline=False)


def make(fake, sleeps=None):
    http = GitHubHTTP(
        "https://api.github.test",
        transport=fake.transport(),
        sleep=(sleeps.append if sleeps is not None else (lambda s: None)),
    )
    svc = ServiceGitHubClient(http, lambda: fake.installation_token, fake.owner, fake.repo)
    return http, svc


def user(fake, http, login):
    return UserGitHubClient(http, fake.token_for(login), login, fake.users[login]["id"], fake.owner, fake.repo)


# --------------------------------------------------------- service identity
def test_service_can_create_issue_then_label(fake):
    _, svc = make(fake)
    issue = svc.create_issue("T", "body")
    svc.add_start_label(issue["number"])
    assert fake.s.issues[issue["number"]]["user"]["login"] == BOT
    assert fake.labels(issue["number"]) == ["sdlc:start"]


@pytest.mark.parametrize(
    "body", ["I answer: the stakeholders are managers", "/agent revise do it", "/model approve", "Approved", ""]
)
def test_service_cannot_post_free_comments(fake, body):
    _, svc = make(fake)
    n = svc.create_issue("T", "b")["number"]
    with pytest.raises(IdentityViolation):
        svc._call("POST", f"{svc.base}/issues/{n}/comments", json={"body": body})
    assert fake.s.comments[n] == []


def test_service_overflow_part_allowed(fake):
    _, svc = make(fake)
    n = svc.create_issue("T", "b")["number"]
    svc.post_overflow_part(n, "[Part 1/1 of a.pdf] characters 1-2\n\ntext")
    assert fake.s.comments[n][0]["user"]["login"] == BOT


@pytest.mark.parametrize(
    "method,path,payload",
    [
        ("POST", "/pulls/5/reviews", {"event": "APPROVE"}),
        ("POST", "/pulls/5/merge", {}),
        ("PUT", "/pulls/5/merge", {}),
        ("POST", "/actions/runs/9/pending_deployments", {"state": "approved"}),
        ("POST", "/issues/1/labels", {"labels": ["sdlc:awaiting-info"]}),
        ("POST", "/issues/1/labels", {"labels": ["sdlc:start", "x"]}),
        ("POST", "/issues", {"title": "t", "body": "b", "labels": ["sdlc:start"]}),
        ("POST", "/git/refs", {"ref": "refs/heads/main", "sha": "x"}),
        ("PATCH", "/git/refs/heads/main", {"sha": "x"}),
        ("PUT", "/contents/README.md", {"message": "m"}),
        ("DELETE", "/issues/1/labels/sdlc:awaiting-info", None),
    ],
)
def test_service_guard_denies_sensitive_calls(fake, method, path, payload):
    _, svc = make(fake)
    with pytest.raises(IdentityViolation):
        svc._call(method, svc.base + path, json=payload)
    assert not any(p.endswith(path) for _, p, _ in fake.s.request_log)


def test_service_client_has_no_review_or_command_methods():
    names = {n for n, _ in inspect.getmembers(ServiceGitHubClient, inspect.isfunction)}
    forbidden = {"post_comment", "submit_review", "review_deployment", "pending_deployments", "approve", "merge"}
    assert not names & forbidden
    src = inspect.getsource(ServiceGitHubClient)
    assert '"/agent ' not in src.replace('startswith(("/agent", "/model"))', "")


def test_commands_are_only_sent_through_the_user_client():
    """AST scan: no module calls a service-client write method with a command or answer."""
    offenders = []
    for py in APP_DIR.rglob("*.py"):
        tree = ast.parse(py.read_text(encoding="utf-8"))
        for node in ast.walk(tree):
            if isinstance(node, ast.Call) and isinstance(node.func, ast.Attribute):
                if node.func.attr in ("submit_review", "review_deployment"):
                    owner = ast.unparse(node.func.value)
                    if "svc" in owner or "service" in owner:
                        offenders.append(f"{py.name}: {ast.unparse(node)}")
                if node.func.attr == "post_comment" and (
                    "svc" in ast.unparse(node.func.value) or "service" in ast.unparse(node.func.value)
                ):
                    offenders.append(f"{py.name}: {ast.unparse(node)}")
    assert offenders == []


def test_intake_branch_is_created_without_touching_main(fake):
    _, svc = make(fake)
    main_before = fake.s.refs["main"]
    svc.create_intake_branch("intake/req_1", "main", {"intake/req_1/a.md": b"hello"}, "chore: intake")
    assert fake.s.refs["main"] == main_before
    assert fake.s.files["intake/req_1"]["intake/req_1/a.md"] == b"hello"
    # idempotent on retry
    svc.create_intake_branch("intake/req_1", "main", {"intake/req_1/a.md": b"hello"}, "chore: intake")
    with pytest.raises(IdentityViolation):
        svc.create_intake_branch("main", "main", {}, "x")


# --------------------------------------------------------- user identity
def test_user_comment_and_review_are_authored_by_user(fake):
    http, svc = make(fake)
    n = svc.create_issue("T", "b")["number"]
    pr = fake.open_stage_pr(n, 0)
    bob = user(fake, http, "bob-gh")
    bob.post_comment(n, "the stakeholders are managers")
    bob.submit_review(pr["number"], "APPROVE", "LGTM", pr["head"]["sha"])
    assert fake.s.comments[n][-1]["user"]["login"] == "bob-gh"
    assert fake.s.reviews[pr["number"]][0]["user"]["login"] == "bob-gh"


def test_user_client_cannot_merge_or_label(fake):
    http, _ = make(fake)
    bob = user(fake, http, "bob-gh")
    for method, path in [("PUT", "/pulls/1/merge"), ("POST", "/issues/1/labels"), ("POST", "/issues")]:
        with pytest.raises(IdentityViolation):
            bob._call(method, bob.base + path, json={})


def test_user_repr_hides_token(fake):
    http, _ = make(fake)
    bob = user(fake, http, "bob-gh")
    assert bob.token() not in repr(bob)


def test_github_rejects_self_approval_with_reason(fake):
    http, svc = make(fake)
    n = svc.create_issue("T", "b")["number"]
    pr = fake.open_stage_pr(n, 0)
    pr["user"] = fake.users["dave-gh"]
    dave = user(fake, http, "dave-gh")
    with pytest.raises(GitHubError) as ei:
        dave.submit_review(pr["number"], "APPROVE", "", pr["head"]["sha"])
    assert ei.value.status == 422 and "Can not approve your own pull request" in ei.value.message


# --------------------------------------------------------- retries / errors
def test_rate_limit_retries_same_identity_then_succeeds(fake):
    sleeps: list[float] = []
    http, svc = make(fake, sleeps)
    n = svc.create_issue("T", "b")["number"]
    bob = user(fake, http, "bob-gh")
    fake.fail_next(
        "POST",
        r"/issues/\d+/comments",
        403,
        {"message": "API rate limit exceeded"},
        {"x-ratelimit-remaining": "0", "retry-after": "1"},
    )
    bob.post_comment(n, "answer")
    assert sleeps == [1.0]
    posts = [entry for entry in fake.s.request_log if entry[0] == "POST" and entry[1].endswith("/comments")]
    assert [lg for _, _, lg in posts] == ["bob-gh", "bob-gh"]
    assert len(fake.s.comments[n]) == 1


def test_long_rate_limit_is_reported_not_waited(fake):
    http, svc = make(fake)
    n = svc.create_issue("T", "b")["number"]
    bob = user(fake, http, "bob-gh")
    fake.fail_next("POST", r"/comments", 429, {"message": "secondary rate limit"}, {"retry-after": "600"})
    with pytest.raises(GitHubError) as ei:
        bob.post_comment(n, "answer")
    assert ei.value.kind == "rate_limited" and "minute" in ei.value.message


def test_post_not_retried_on_server_error(fake):
    http, svc = make(fake)
    n = svc.create_issue("T", "b")["number"]
    bob = user(fake, http, "bob-gh")
    fake.fail_next("POST", r"/comments", 502, {"message": "Bad gateway"})
    with pytest.raises(GitHubError) as ei:
        bob.post_comment(n, "answer")
    assert ei.value.status == 502
    assert sum(1 for m, p, _ in fake.s.request_log if m == "POST" and p.endswith("/comments")) == 1


def test_revoked_token_maps_to_auth_error(fake):
    http, svc = make(fake)
    bob = user(fake, http, "bob-gh")
    fake.revoke(bob.token())
    with pytest.raises(GitHubError) as ei:
        bob.whoami()
    assert ei.value.kind == "auth"


def test_module_exports():
    assert clients_mod.START_LABEL == "sdlc:start"
