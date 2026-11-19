"""Shared requesters use the original GitHub intake; human actions keep named identities."""

import httpx
import jwt
import pytest
from cryptography.fernet import Fernet
from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric import rsa
from fastapi.testclient import TestClient
from sqlalchemy import select

from app.config import Settings, UnsafeConfigurationError
from app.db import AuditEntry, GitHubLink
from tests.conftest import CLEAR_REQUIREMENT
from tests.test_api_intake import label_after_content
from tests.test_github_signin import github_signin, me

PASSWORD = "test-only-portal-password"


@pytest.fixture
def shared_portal(portal_factory):
    return portal_factory(auth_mode="password", portal_admin_password=PASSWORD, github_signin_enabled=True)


def sign_in(portal):
    client = TestClient(portal.app, follow_redirects=False)
    response = client.post("/auth/password-login", json={"username": "admin", "password": PASSWORD})
    assert response.status_code == 200, response.text
    client.headers["X-CSRF-Token"] = response.json()["csrf_token"]
    return client


def test_password_login_is_opt_in(portal):
    client = TestClient(portal.app)
    assert client.get("/auth/options").json()["password"] is False
    assert client.post("/auth/password-login", json={"username": "admin", "password": PASSWORD}).status_code == 404


def test_shared_login_checks_credentials_and_keeps_secrets_server_side(shared_portal, capsys):
    client = TestClient(shared_portal.app)
    options = client.get("/auth/options")
    assert options.json() == {"microsoft": False, "github": True, "dev": False, "password": True, "open": False}
    for username, password in (("admin", "wrong"), ("nobody", PASSWORD), ("admin", "")):
        response = client.post("/auth/password-login", json={"username": username, "password": password})
        assert response.status_code == 401
        assert response.json()["error"]["code"] == "bad_credentials"
        assert client.get("/api/me").status_code == 401
    client = sign_in(shared_portal)
    info = client.get("/api/me")
    assert info.json()["user"]["roles"] == ["Requester"]
    assert info.json()["user"]["sign_in"] == "password"
    assert info.json()["github"]["connected"] is False
    assert PASSWORD not in options.text + info.text + capsys.readouterr().out
    assert client.post("/auth/dev-login", json={"username": "alice"}).status_code == 404
    with shared_portal.container.db.sessionmaker() as db:
        entry = db.scalar(select(AuditEntry).where(AuditEntry.action == "password_signin"))
        assert entry.outcome == "ok" and entry.identity == "portal"


def test_password_login_origin_rate_limit_csrf_and_logout(shared_portal):
    client = TestClient(shared_portal.app)
    body = {"username": "admin", "password": PASSWORD}
    assert client.post("/auth/password-login", json=body, headers={"Origin": "https://evil.test"}).status_code == 403
    shared_portal.settings.rate_limit_login_per_min = 2
    for _ in range(2):
        assert client.post("/auth/password-login", json={**body, "password": "wrong"}).status_code == 401
    assert client.post("/auth/password-login", json=body).status_code == 429
    shared_portal.container.rate.reset()
    response = client.post("/auth/password-login", json=body)
    cookie = response.headers["set-cookie"].lower()
    assert "httponly" in cookie and "samesite=lax" in cookie
    assert client.post("/api/intake/preview", data={"pasted_text": CLEAR_REQUIREMENT}).status_code == 403
    client.headers["X-CSRF-Token"] = response.json()["csrf_token"]
    assert client.post("/auth/logout").status_code == 200
    assert client.get("/api/me").status_code == 401


def test_shared_requester_submits_but_cannot_borrow_a_reviewer_identity(shared_portal):
    client = sign_in(shared_portal)
    preview = client.post("/api/intake/preview", data={"pasted_text": CLEAR_REQUIREMENT, "fields": "{}"})
    assert preview.status_code == 200
    response = client.post(
        "/api/requests",
        json={"draft_id": preview.json()["draft_id"]},
        headers={"Idempotency-Key": "shared-intake"},
    )
    assert response.status_code == 200, response.text
    req = response.json()["request"]
    assert req["submit_step"] == "done"
    assert shared_portal.fake.s.issues[req["issue_number"]]["user"]["login"] == "aisdlc-portal[bot]"
    assert client.get(f"/api/requests/{req['id']}").status_code == 200
    assert client.get("/auth/github/connect").status_code == 403
    assert client.post(f"/api/requests/{req['id']}/model", json={"command": "approve"}).status_code == 403
    assert client.post("/api/production/123/approve", json={"confirmation": "promote"}).status_code == 403
    with shared_portal.container.db.sessionmaker() as db:
        assert db.scalar(select(GitHubLink)) is None

    # Named reviewers still sign in separately and retain the existing approval checks.
    reviewer, location = github_signin(shared_portal, login="bob-gh")
    assert location == "/"
    assert me(reviewer)["user"]["roles"] == ["Requester", "Reviewer"]
    detail = client.get(f"/api/requests/{req['id']}").json()
    stage_url = f"/api/requests/{req['id']}/stages/{detail['open_stage_pr']}"
    stage = client.get(stage_url)
    assert stage.status_code == 200
    assert (
        client.post(
            stage_url + "/approve", json={"head_sha": stage.json()["pr"]["head_sha"], "confirmed": True}
        ).status_code
        == 403
    )
    review = reviewer.get(stage_url)
    assert review.status_code == 200
    assert review.json()["precheck"]["can_approve"] is True
    approved = reviewer.post(
        stage_url + "/approve", json={"head_sha": review.json()["pr"]["head_sha"], "confirmed": True}
    )
    assert approved.status_code == 200
    assert approved.json()["github_login"] == "bob-gh"


def test_shared_requester_cannot_answer_as_a_human(shared_portal):
    client = sign_in(shared_portal)
    preview = client.post("/api/intake/preview", data={"pasted_text": "An incomplete idea.", "fields": "{}"}).json()
    req = client.post(
        "/api/requests", json={"draft_id": preview["draft_id"]}, headers={"Idempotency-Key": "incomplete"}
    ).json()["request"]
    response = client.post(f"/api/requests/{req['id']}/answer", json={"answer": CLEAR_REQUIREMENT})
    assert response.status_code == 403 and response.json()["error"]["code"] == "shared_identity"


def test_password_session_stops_working_when_mode_is_disabled(shared_portal):
    client = sign_in(shared_portal)
    shared_portal.settings.auth_mode = "entra"
    assert client.get("/api/me").status_code == 401


def test_open_mode_starts_a_shared_session_without_credentials(portal_factory):
    p = portal_factory(auth_mode="open")
    client = TestClient(p.app)
    assert client.get("/auth/options").json()["open"] is True
    assert client.get("/api/me").status_code == 401
    assert client.post("/auth/open-session", headers={"Origin": "https://evil.test"}).status_code == 403
    assert client.post("/auth/password-login", json={"username": "admin", "password": "x"}).status_code == 404
    response = client.post("/auth/open-session")
    assert response.status_code == 200
    client.headers["X-CSRF-Token"] = response.json()["csrf_token"]
    info = client.get("/api/me").json()
    assert info["user"]["roles"] == ["Requester"] and info["config"]["auth_mode"] == "open"
    preview = client.post("/api/intake/preview", data={"pasted_text": CLEAR_REQUIREMENT, "fields": "{}"})
    assert preview.status_code == 200
    created = client.post(
        "/api/requests", json={"draft_id": preview.json()["draft_id"]}, headers={"Idempotency-Key": "open-intake"}
    )
    assert created.status_code == 200, created.text
    req = created.json()["request"]
    assert client.post(f"/api/requests/{req['id']}/model", json={"command": "approve"}).status_code == 403


def test_open_session_is_disabled_in_other_modes(portal):
    client = TestClient(portal.app)
    assert client.get("/auth/options").json()["open"] is False
    assert client.post("/auth/open-session").status_code == 404


def test_open_mode_is_local_development_only():
    with pytest.raises(UnsafeConfigurationError, match="AUTH_MODE=open"):
        Settings(app_env="production", auth_mode="open", github_mode="fake")
    with pytest.raises(UnsafeConfigurationError, match="loopback"):
        Settings(app_env="development", auth_mode="open", github_mode="fake", bind_host="0.0.0.0")  # noqa: S104
    with pytest.raises(UnsafeConfigurationError, match="AUTH_MODE=open requires BIND_HOST"):
        Settings(
            app_env="test", auth_mode="open", github_mode="fake", bind_host="0.0.0.0", public_base_url="http://testserver"  # noqa: S104
        )

def test_password_mode_requires_a_password_and_named_reviewers():
    with pytest.raises(UnsafeConfigurationError, match="PORTAL_ADMIN_PASSWORD"):
        Settings(app_env="test", auth_mode="password")
    with pytest.raises(UnsafeConfigurationError, match="reviewer"):
        Settings(app_env="test", auth_mode="password", portal_admin_password=PASSWORD)


def test_admin_password_works_for_loopback_development(portal_factory):
    p = portal_factory(
        app_env="development",
        auth_mode="password",
        portal_admin_password="admin",
        github_signin_enabled=True,
        public_base_url="http://localhost:8000",
    )
    client = TestClient(p.app, base_url="http://localhost:8000")
    response = client.post(
        "/auth/password-login",
        json={"username": "admin", "password": "admin"},
        headers={"Origin": "http://localhost:8000"},
    )
    assert response.status_code == 200
    assert client.get("/api/me").json()["user"]["roles"] == ["Requester"]


def test_weak_password_is_localhost_only():
    with pytest.raises(UnsafeConfigurationError, match="loopback"):
        Settings(
            app_env="development",
            auth_mode="password",
            portal_admin_password="admin",
            github_signin_enabled=True,
            bind_host="0.0.0.0",
        )
    with pytest.raises(UnsafeConfigurationError, match="PORTAL_ADMIN_PASSWORD"):
        Settings(
            app_env="production",
            auth_mode="password",
            portal_admin_password="admin",
            github_signin_enabled=True,
        )


def test_password_mode_real_backend_fails_fast_without_github_credentials():
    with pytest.raises(UnsafeConfigurationError, match="GITHUB_APP"):
        Settings(
            app_env="development",
            auth_mode="password",
            portal_admin_password="admin",
            github_signin_enabled=True,
            bind_host="127.0.0.1",
            github_mode="app",
        )


def test_production_password_intake_uses_app_authentication_and_github_api(portal_factory):
    key = rsa.generate_private_key(public_exponent=65537, key_size=2048)
    private_pem = key.private_bytes(
        serialization.Encoding.PEM, serialization.PrivateFormat.PKCS8, serialization.NoEncryption()
    ).decode()
    p = portal_factory(
        app_env="production",
        auth_mode="password",
        portal_admin_password=PASSWORD,
        github_mode="app",
        github_repository="demo/aisdlc",
        github_app_id="123",
        github_app_private_key=private_pem,
        github_app_client_id="client",
        github_app_client_secret="synthetic-oauth-secret",
        github_signin_enabled=True,
        github_webhook_secret="synthetic-webhook-secret",
        token_encryption_key=Fernet.generate_key().decode(),
        session_secret="synthetic-session-key-for-tests-only",
        public_base_url="https://testserver",
        extraction_isolation="process",
    )
    p.fake.owner, p.fake.repo = "demo", "aisdlc"
    auth_requests = []

    def github_api(request):
        if request.url.path in ("/repos/demo/aisdlc/installation", "/app/installations/456/access_tokens"):
            token = request.headers["authorization"].removeprefix("Bearer ")
            assert jwt.decode(token, key.public_key(), algorithms=["RS256"])["iss"] == "123"
            auth_requests.append(request.url.path)
            payload = (
                {"id": 456}
                if request.method == "GET"
                else {"token": p.fake.installation_token, "expires_at": "2099-01-01T00:00:00Z"}
            )
            return httpx.Response(200, json=payload)
        return p.fake.handle(request)

    p.container.http.client.close()
    with httpx.Client(base_url="https://api.github.com", transport=httpx.MockTransport(github_api)) as transport:
        p.container.http.client = transport
        with TestClient(p.app, base_url="https://testserver") as client:
            response = client.post("/auth/password-login", json={"username": "admin", "password": PASSWORD})
            assert response.status_code == 200
            assert "Secure" in response.headers["set-cookie"]
            client.headers["X-CSRF-Token"] = response.json()["csrf_token"]
            assert client.get("/api/me").json()["config"]["github_mode"] == "app"
            assert client.get("/dev/fake-github/state").status_code == 404
            draft = client.post("/api/intake/preview", data={"pasted_text": CLEAR_REQUIREMENT, "fields": "{}"}).json()
            response = client.post(
                "/api/requests", json={"draft_id": draft["draft_id"]}, headers={"Idempotency-Key": "real-contract"}
            )
            assert response.status_code == 200, response.text
            req = response.json()["request"]
            assert req["submit_step"] == "done"
            assert label_after_content(p.fake, req["issue_number"])
            assert auth_requests == ["/repos/demo/aisdlc/installation", "/app/installations/456/access_tokens"]
            assert p.container.fake is None
