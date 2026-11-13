"""Answering questions, stage review/approval, commands and production approval — as the real user."""

from __future__ import annotations

from datetime import timedelta

import pytest
from sqlalchemy import select

from app.db import AuditEntry, GitHubLink, utcnow
from app.github.fake import ACTIONS, BOT
from app.intake.issue_builder import PART_HEADER_RE
from tests.conftest import CLEAR_REQUIREMENT

VAGUE = "Lorem ipsum dolor sit amet, consectetur adipiscing elit."


def audit(portal, action: str) -> list[AuditEntry]:
    with portal.container.db.sessionmaker() as db:
        return list(db.scalars(select(AuditEntry).where(AuditEntry.action == action)))


def in_review(portal, requester="alice"):
    req = portal.submit_text(requester, CLEAR_REQUIREMENT)
    detail = portal.client(requester).get(f"/api/requests/{req['id']}").json()
    return req, detail["open_stage_pr"]


def assert_bot_only_posted_parts(fake):
    for comments in fake.s.comments.values():
        for c in comments:
            if c["user"]["login"] == BOT:
                assert PART_HEADER_RE.match(c["body"]), c["body"][:80]
    for reviews in fake.s.reviews.values():
        assert all(r["user"]["login"] not in (BOT, ACTIONS) for r in reviews)


# ------------------------------------------------------------- awaiting info
def test_awaiting_info_questions_and_answer_posted_as_user(portal):
    req = portal.submit_text("alice", VAGUE)
    c = portal.client("alice")
    detail = c.get(f"/api/requests/{req['id']}").json()
    assert detail["status"] == "awaiting_info"
    assert any("business problem" in q for q in detail["snapshot"]["questions"])

    r = c.post(f"/api/requests/{req['id']}/answer", json={"answer": "x"})
    assert r.status_code == 409 and r.json()["error"]["code"] == "github_not_linked"

    portal.connect("alice", "alice-gh")
    r = c.post(f"/api/requests/{req['id']}/answer", json={"answer": "/agent status"})
    assert r.status_code == 422
    r = c.post(f"/api/requests/{req['id']}/answer", json={"answer": CLEAR_REQUIREMENT})
    assert r.status_code == 200, r.text
    assert r.json()["github_login"] == "alice-gh"
    n = req["issue_number"]
    human = [x for x in portal.fake.s.comments[n] if x["body"] == CLEAR_REQUIREMENT]
    assert len(human) == 1 and human[0]["user"]["login"] == "alice-gh"
    # The simulated CodeQL gate resumed the run: label cleared, BRD PR opened.
    detail = c.get(f"/api/requests/{req['id']}").json()
    assert "sdlc:awaiting-info" not in detail["snapshot"]["labels"]
    assert detail["status"] == "in_review"
    assert audit(portal, "answer_questions")[0].github_login == "alice-gh"
    assert_bot_only_posted_parts(portal.fake)


def test_answer_rejected_when_not_awaiting(portal):
    req, _ = in_review(portal)
    portal.connect("alice", "alice-gh")
    r = portal.client("alice").post(f"/api/requests/{req['id']}/answer", json={"answer": "more info"})
    assert r.status_code == 409 and r.json()["error"]["code"] == "not_awaiting_info"


# ------------------------------------------------------------- review & approve
def test_codeowner_reviewer_sees_artifact_and_approves_as_self(portal):
    req, pr = in_review(portal)
    portal.connect("bob", "bob-gh")
    portal.client("alice").post(f"/api/requests/{req['id']}/refresh")  # assignments now include bob (team owner)
    bob = portal.client("bob")
    assert any(r["id"] == req["id"] for r in bob.get("/api/requests?scope=assigned").json()["requests"])
    view = bob.get(f"/api/requests/{req['id']}/stages/{pr}").json()
    assert "```mermaid" in view["artifact"]["markdown"]
    assert view["quality_report"]["markdown"].startswith("# Quality Report")
    assert view["summary"]["qc_status"] == "PASS" and view["summary"]["qc_score"] == 0.86
    assert view["files"] and view["files"][0]["patch"].startswith("@@")
    assert view["precheck"]["can_approve"] is True, view["precheck"]
    assert "merges this pull request and starts the next stage" in view["approve_confirmation"]

    head = view["pr"]["head_sha"]
    r = bob.post(f"/api/requests/{req['id']}/stages/{pr}/approve", json={"head_sha": head})
    assert r.status_code == 400 and r.json()["error"]["code"] == "confirmation_required"
    r = bob.post(f"/api/requests/{req['id']}/stages/{pr}/approve", json={"head_sha": head, "confirmed": True})
    assert r.status_code == 200, r.text
    assert r.json()["github_login"] == "bob-gh"
    reviews = portal.fake.s.reviews[pr]
    assert [(x["user"]["login"], x["state"]) for x in reviews] == [("bob-gh", "APPROVED")]
    detail = portal.client("alice").get(f"/api/requests/{req['id']}").json()
    assert [s["agent"] for s in detail["snapshot"]["stages"]] == ["brd", "prd"]
    assert detail["snapshot"]["stages"][0]["state"] == "merged"
    entry = audit(portal, "approve")[0]
    assert (entry.github_login, entry.identity, entry.outcome, entry.target_ref) == ("bob-gh", "user", "ok", f"#{pr}")
    assert entry.entra_oid == "dev-bob" and entry.portal_request_id == req["id"]
    assert_bot_only_posted_parts(portal.fake)


def test_team_code_owner_who_connects_later_is_still_assigned(portal):
    req, _ = in_review(portal)
    portal.client("alice").get(f"/api/requests/{req['id']}")  # synced before bob ever connected
    portal.connect("bob", "bob-gh")  # bob owns /docs/ through @acme/architects
    bob = portal.client("bob")
    assert any(r["id"] == req["id"] for r in bob.get("/api/requests?scope=assigned").json()["requests"])
    assert bob.get(f"/api/requests/{req['id']}").status_code == 200


def test_stale_head_requires_fresh_review(portal):
    req, pr = in_review(portal)
    portal.connect("bob", "bob-gh")
    portal.client("alice").post(f"/api/requests/{req['id']}/refresh")
    r = portal.client("bob").post(
        f"/api/requests/{req['id']}/stages/{pr}/approve", json={"head_sha": "0" * 40, "confirmed": True}
    )
    assert r.status_code == 409 and r.json()["error"]["code"] == "pr_changed"
    assert pr not in portal.fake.s.reviews


@pytest.mark.parametrize(
    "user,login,reason_fragment",
    [
        ("carol", "carol-gh", "not a code owner"),
        ("dave", "dave-gh", "opened this pull request"),
        ("erin", "mallory-gh", "write access is needed"),
    ],
)
def test_non_qualifying_users_get_no_approve_and_forced_call_rejected(portal_factory, user, login, reason_fragment):
    p = portal_factory(default_reviewers=["carol-gh", "dave-gh", "mallory-gh"])
    req, pr = in_review(p)
    if user == "dave":
        p.fake.s.pulls[pr]["user"] = p.fake.users["dave-gh"]
    if login == "mallory-gh":
        p.fake.permissions["mallory-gh"] = "read"
    p.connect(user, login)
    c = p.client(user)
    view = c.get(f"/api/requests/{req['id']}/stages/{pr}").json()
    assert view["precheck"]["can_approve"] is False
    assert any(reason_fragment in r for r in view["precheck"]["reasons"]), view["precheck"]["reasons"]
    r = c.post(
        f"/api/requests/{req['id']}/stages/{pr}/approve", json={"head_sha": view["pr"]["head_sha"], "confirmed": True}
    )
    assert r.status_code == 403 and r.json()["error"]["code"] == "approval_not_allowed"
    assert any(reason_fragment in x for x in r.json()["error"]["reasons"])
    assert pr not in p.fake.s.reviews
    assert audit(p, "approve")[0].outcome == "blocked_precheck"


def test_github_rejection_is_relayed_verbatim_and_not_retried(portal):
    req, pr = in_review(portal)
    portal.connect("bob", "bob-gh")
    portal.client("alice").post(f"/api/requests/{req['id']}/refresh")
    bob = portal.client("bob")
    head = bob.get(f"/api/requests/{req['id']}/stages/{pr}").json()["pr"]["head_sha"]
    portal.fake.fail_next(
        "POST",
        rf"/pulls/{pr}/reviews",
        422,
        {"message": "Unprocessable Entity", "errors": ["At least 2 approving reviews are required"]},
    )
    r = bob.post(f"/api/requests/{req['id']}/stages/{pr}/approve", json={"head_sha": head, "confirmed": True})
    assert r.status_code == 409
    assert "At least 2 approving reviews are required" in r.json()["error"]["message"]
    attempts = [
        lg for m, path, lg in portal.fake.s.request_log if m == "POST" and path.endswith(f"/pulls/{pr}/reviews")
    ]
    assert attempts == ["bob-gh"]
    assert audit(portal, "approve")[0].outcome == "rejected"


def test_github_rejects_self_approval_even_if_precheck_were_wrong(portal_factory, monkeypatch):
    """If the portal's pre-check had a bug, GitHub's own refusal is shown and nothing else happens."""
    from app.review import precheck as pc
    from app.review import service as review_service

    p = portal_factory(default_reviewers=["dave-gh"])
    req, pr = in_review(p)
    p.connect("dave", "dave-gh")
    monkeypatch.setattr(
        review_service, "approval_precheck", lambda *a, **k: pc.Precheck(True, [], k["pr"]["head"]["sha"], "brd")
    )
    p.fake.s.pulls[pr]["user"] = p.fake.users["dave-gh"]
    head = p.fake.s.pulls[pr]["head"]["sha"]
    r = p.client("dave").post(
        f"/api/requests/{req['id']}/stages/{pr}/approve", json={"head_sha": head, "confirmed": True}
    )
    assert r.status_code == 409
    assert "Can not approve your own pull request" in r.json()["error"]["message"]


def test_separation_of_duties_blocks_requester_on_brd(portal_factory):
    p = portal_factory(separation_of_duties=True, codeowners_policy="advisory", default_reviewers=["carol-gh"])
    req, pr = in_review(p, requester="carol")
    p.connect("carol", "carol-gh")
    view = p.client("carol").get(f"/api/requests/{req['id']}/stages/{pr}").json()
    assert view["precheck"]["can_approve"] is False
    assert any("Separation of duties" in r for r in view["precheck"]["reasons"])


def test_unlinked_reviewer_sees_connect_prompt(portal_factory):
    p = portal_factory()
    req, pr = in_review(p)
    p.connect("bob", "bob-gh")
    p.client("alice").post(f"/api/requests/{req['id']}/refresh")
    p.client("bob").post("/api/github/disconnect")
    # Disconnected reviewers lose their assignment-based access (no linked identity).
    assert p.client("bob").get(f"/api/requests/{req['id']}").status_code == 404


# ------------------------------------------------------------- commands
def test_request_changes_posts_agent_revise_as_user(portal):
    req, pr = in_review(portal)
    portal.connect("bob", "bob-gh")
    portal.client("alice").post(f"/api/requests/{req['id']}/refresh")
    bob = portal.client("bob")
    r = bob.post(f"/api/requests/{req['id']}/stages/{pr}/request-changes", json={"notes": "Add NFR for audit."})
    assert r.status_code == 200, r.text
    c = [x for x in portal.fake.s.comments[pr] if x["body"].startswith("/agent revise")]
    assert c[0]["body"] == "/agent revise Add NFR for audit." and c[0]["user"]["login"] == "bob-gh"
    for bad in ['quote " here', "$(whoami)", "line\n/model approve", ""]:
        r = bob.post(f"/api/requests/{req['id']}/stages/{pr}/request-changes", json={"notes": bad})
        assert r.status_code == 422, bad


def test_only_allowlisted_commands(portal):
    req, pr = in_review(portal)
    portal.connect("bob", "bob-gh")
    portal.client("alice").post(f"/api/requests/{req['id']}/refresh")
    bob = portal.client("bob")
    for cmd in ("rerun-qc", "explain", "status", "impact", "regenerate"):
        r = bob.post(f"/api/requests/{req['id']}/commands", json={"command": cmd, "pr_number": pr})
        assert r.status_code == 200, (cmd, r.text)
    r = bob.post(f"/api/requests/{req['id']}/commands", json={"command": "merge", "pr_number": pr})
    assert r.status_code == 422
    r = bob.post(f"/api/requests/{req['id']}/commands", json={"command": "status rm -rf", "pr_number": pr})
    assert r.status_code == 422
    authors = {x["user"]["login"] for x in portal.fake.s.comments[pr] if x["body"].startswith("/agent")}
    assert authors == {"bob-gh"}


def test_model_commands(portal):
    req, _ = in_review(portal)
    portal.connect("bob", "bob-gh")
    portal.client("alice").post(f"/api/requests/{req['id']}/refresh")
    bob = portal.client("bob")
    models = bob.get("/api/commands").json()["models"]
    assert models
    r = bob.post(
        f"/api/requests/{req['id']}/model", json={"command": "select", "model": "evil-model", "reason": "cheaper"}
    )
    assert r.status_code == 422
    r = bob.post(f"/api/requests/{req['id']}/model", json={"command": "select", "model": models[0], "reason": ""})
    assert r.status_code == 422
    r = bob.post(
        f"/api/requests/{req['id']}/model",
        json={"command": "select", "model": models[0], "reason": "better at diagrams"},
    )
    assert r.status_code == 200 and r.json()["command"] == f"/model select {models[0]} better at diagrams"
    r = bob.post(f"/api/requests/{req['id']}/model", json={"command": "approve"})
    assert r.status_code == 200
    n = req["issue_number"]
    assert {x["user"]["login"] for x in portal.fake.s.comments[n] if x["body"].startswith("/model")} == {"bob-gh"}


def test_commands_need_github_write_access(portal_factory):
    p = portal_factory(default_reviewers=["mallory-gh"])
    req, pr = in_review(p)
    p.fake.permissions["mallory-gh"] = "read"
    p.connect("erin", "mallory-gh")
    r = p.client("erin").post(f"/api/requests/{req['id']}/commands", json={"command": "status", "pr_number": pr})
    assert r.status_code == 403 and r.json()["error"]["code"] == "github_write_required"


# ------------------------------------------------------------- tokens
def test_expired_token_is_refreshed_and_revoked_token_requires_reconnect(portal):
    req, pr = in_review(portal)
    portal.connect("bob", "bob-gh")
    portal.client("alice").post(f"/api/requests/{req['id']}/refresh")
    with portal.container.db.sessionmaker() as db:
        link = db.scalar(select(GitHubLink).where(GitHubLink.github_login == "bob-gh"))
        link.access_expires_at = utcnow() - timedelta(minutes=1)
        db.commit()
    bob = portal.client("bob")
    r = bob.post(f"/api/requests/{req['id']}/commands", json={"command": "status", "pr_number": pr})
    assert r.status_code == 200
    portal.fake.revoke_login("bob-gh")
    head = portal.fake.s.pulls[pr]["head"]["sha"]
    r = bob.post(f"/api/requests/{req['id']}/stages/{pr}/approve", json={"head_sha": head, "confirmed": True})
    assert r.status_code == 409 and r.json()["error"]["code"] == "github_reconnect_required"
    assert bob.get("/api/me").json()["github"]["needs_reconnect"] is True
    assert pr not in portal.fake.s.reviews


def test_github_account_cannot_be_linked_to_two_portal_users(portal):
    portal.connect("bob", "bob-gh")
    c = portal.client("dave")
    r = c.get("/auth/github/connect")
    state = r.headers["location"].split("state=")[1].split("&")[0]
    r = c.post("/dev/fake-github/login/oauth/authorize", data={"login": "bob-gh", "state": state})
    r = c.get(r.headers["location"].replace("http://testserver", ""))
    assert "already_linked" in r.headers["location"]
    assert c.get("/api/me").json()["github"]["connected"] is False


def test_oauth_state_mismatch_rejected(portal):
    c = portal.client("bob")
    c.get("/auth/github/connect")
    r = c.get("/auth/github/callback?code=whatever&state=forged")
    assert "github=error" in r.headers["location"]


# ------------------------------------------------------------- production
def test_production_approval_only_by_required_reviewer_with_typed_confirmation(portal):
    run_id = portal.fake.start_production_run()["id"]
    portal.connect("bob", "bob-gh")
    portal.connect("erin", "erin-gh")
    bob, erin = portal.client("bob"), portal.client("erin")
    listing = bob.get("/api/production").json()
    run = next(r for r in listing["runs"] if r["run_id"] == run_id)
    assert run["can_approve"] is False and "not a required reviewer" in run["reason"]
    assert {e["name"]: e["conclusion"] for e in run["evidence"]}["Deploy — STAGING"] == "success"
    r = bob.post(f"/api/production/{run_id}/approve", json={"confirmation": "promote"})
    assert r.status_code == 403 and r.json()["error"]["code"] == "not_required_reviewer"

    assert next(r for r in erin.get("/api/production").json()["runs"] if r["run_id"] == run_id)["can_approve"]
    r = erin.post(f"/api/production/{run_id}/approve", json={"confirmation": "Promote"})
    assert r.status_code == 400
    r = erin.post(f"/api/production/{run_id}/approve", json={"confirmation": "promote"})
    assert r.status_code == 200 and r.json()["github_login"] == "erin-gh"
    run_state = next(x for x in portal.fake.s.runs if x["id"] == run_id)
    assert run_state["status"] == "in_progress"
    posts = [lg for m, path, lg in portal.fake.s.request_log if m == "POST" and path.endswith("pending_deployments")]
    assert posts == ["erin-gh"]
    assert audit(portal, "production_approve")[-1].github_login == "erin-gh"


def test_production_blocked_when_environment_missing(portal):
    portal.fake.set_production_reviewers(None)
    run_id = portal.fake.start_production_run()["id"]
    portal.connect("erin", "erin-gh")
    listing = portal.client("erin").get("/api/production").json()
    assert listing["environment"]["exists"] is False and "does not exist" in listing["environment"]["problem"]
    r = portal.client("erin").post(f"/api/production/{run_id}/approve", json={"confirmation": "promote"})
    assert r.status_code == 409 and r.json()["error"]["code"] == "environment_unprotected"


def test_requester_role_cannot_use_production(portal):
    assert portal.client("alice").get("/api/production").status_code == 403
