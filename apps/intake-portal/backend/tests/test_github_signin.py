"""Sign in with GitHub: for people without a work account. Off by default; gated on repository access."""

from __future__ import annotations

from fastapi.testclient import TestClient
from sqlalchemy import select

from app.config import Settings
from app.db import AuditEntry, GitHubLink, User
from tests.conftest import CLEAR_REQUIREMENT


def github_signin(portal, login: str = "", new_login: str = "") -> tuple[TestClient, str]:
    c = TestClient(portal.app, follow_redirects=False)
    r = c.get("/auth/github/login")
    assert r.status_code == 302, r.text
    state = r.headers["location"].split("state=")[1].split("&")[0]
    r = c.post("/dev/fake-github/login/oauth/authorize", data={"login": login, "new_login": new_login, "state": state})
    assert r.status_code == 302, r.text
    r = c.get(r.headers["location"].replace("http://testserver", ""))
    return c, r.headers["location"]


def me(c: TestClient) -> dict:
    r = c.get("/api/me")
    assert r.status_code == 200, r.text
    c.headers["X-CSRF-Token"] = r.json()["csrf_token"]
    return r.json()


def test_disabled_by_default(portal):
    assert TestClient(portal.app).get("/auth/options").json() == {
        "microsoft": False,
        "github": False,
        "dev": True,
        "password": False,
    }
    assert TestClient(portal.app, follow_redirects=False).get("/auth/github/login").status_code == 404
    assert Settings.model_fields["github_signin_enabled"].default is False


def test_new_github_user_with_triage_becomes_requester_and_is_connected(portal_factory):
    p = portal_factory(github_signin_enabled=True)
    assert TestClient(p.app).get("/auth/options").json()["github"] is True
    c, location = github_signin(p, new_login="newbie-gh")
    assert location == "/"
    info = me(c)
    assert info["user"]["roles"] == ["Requester"] and info["user"]["sign_in"] == "github"
    assert info["github"] == {"connected": True, "login": "newbie-gh", "needs_reconnect": False}
    # The new user can submit, and their answers are posted as themselves.
    d = c.post("/api/intake/preview", data={"pasted_text": "Lorem ipsum dolor sit amet.", "fields": "{}"}).json()
    req = c.post("/api/requests", json={"draft_id": d["draft_id"]}, headers={"Idempotency-Key": "k1"}).json()["request"]
    r = c.post(f"/api/requests/{req['id']}/answer", json={"answer": CLEAR_REQUIREMENT})
    assert r.status_code == 200 and r.json()["github_login"] == "newbie-gh"
    with p.container.db.sessionmaker() as db:
        entry = db.scalar(select(AuditEntry).where(AuditEntry.action == "github_signin"))
        assert entry.outcome == "ok" and entry.github_login == "newbie-gh"


def test_writer_also_gets_reviewer_role(portal_factory):
    p = portal_factory(github_signin_enabled=True)
    c, _ = github_signin(p, login="bob-gh")
    assert me(c)["user"]["roles"] == ["Requester", "Reviewer"]


def test_users_without_enough_repository_access_are_refused(portal_factory):
    p = portal_factory(github_signin_enabled=True)
    p.fake.permissions["mallory-gh"] = "read"
    c, location = github_signin(p, login="mallory-gh")
    assert location == "/login?error=github_no_access"
    assert c.get("/api/me").status_code == 401
    with p.container.db.sessionmaker() as db:
        assert db.scalar(select(User).where(User.entra_oid.like("github:%"))) is None
        entry = db.scalar(select(AuditEntry).where(AuditEntry.action == "github_signin"))
        assert entry.outcome == "rejected" and "read" in entry.detail


def test_github_account_linked_to_microsoft_user_cannot_be_used_to_sign_in(portal_factory):
    p = portal_factory(github_signin_enabled=True)
    p.connect("bob", "bob-gh")  # bob signs in with Microsoft (dev) and linked bob-gh
    c, location = github_signin(p, login="bob-gh")
    assert location == "/login?error=github_linked_to_microsoft"
    assert c.get("/api/me").status_code == 401


def test_returning_github_user_keeps_one_account(portal_factory):
    p = portal_factory(github_signin_enabled=True)
    github_signin(p, new_login="repeat-gh")
    c, _ = github_signin(p, login="repeat-gh")
    assert me(c)["github"]["login"] == "repeat-gh"
    with p.container.db.sessionmaker() as db:
        assert len(db.scalars(select(GitHubLink).where(GitHubLink.github_login == "repeat-gh")).all()) == 1


def test_github_identity_cannot_be_disconnected(portal_factory):
    p = portal_factory(github_signin_enabled=True)
    c, _ = github_signin(p, new_login="keep-gh")
    me(c)
    r = c.post("/api/github/disconnect")
    assert r.status_code == 409 and r.json()["error"]["code"] == "github_identity"


def test_forged_state_is_rejected(portal_factory):
    p = portal_factory(github_signin_enabled=True)
    c = TestClient(p.app, follow_redirects=False)
    c.get("/auth/github/login")
    r = c.get("/auth/github/callback?code=x&state=forged")
    assert r.headers["location"] == "/login?error=signin_failed"
