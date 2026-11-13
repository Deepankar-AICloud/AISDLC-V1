"""Security acceptance criteria: no token exposure, safe configuration, webhook auth, Entra validation."""

from __future__ import annotations

import hashlib
import hmac
import json
import logging
import time
from pathlib import Path

import jwt
import pytest
from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric import rsa
from fastapi.testclient import TestClient
from sqlalchemy import select

from app.auth.entra import EntraClient, EntraError
from app.config import Settings, UnsafeConfigurationError
from app.db import GitHubLink
from app.logging_setup import RedactingJsonFormatter, redact
from tests import samples
from tests.conftest import CLEAR_REQUIREMENT

FRONTEND = Path(__file__).resolve().parents[2] / "frontend"


def all_tokens(portal) -> list[str]:
    toks = list(portal.fake.tokens) + list(portal.fake.refresh_tokens) + [portal.fake.installation_token]
    return [t for t in toks if len(t) > 10]


def test_no_github_token_in_any_response_or_log(portal, capsys):
    req = portal.submit_text("alice", CLEAR_REQUIREMENT, files=[("a.pdf", samples.pdf_bytes(1))])
    portal.connect("bob", "bob-gh")
    portal.connect("alice", "alice-gh")
    alice, bob = portal.client("alice"), portal.client("bob")
    alice.post(f"/api/requests/{req['id']}/refresh")
    detail = alice.get(f"/api/requests/{req['id']}").json()
    pr = detail["open_stage_pr"]
    bob.get(f"/api/requests/{req['id']}/stages/{pr}")
    bob.post(f"/api/requests/{req['id']}/stages/{pr}/request-changes", json={"notes": "tighten scope"})
    alice.get("/api/me")
    portal.fake.revoke_login("bob-gh")  # error path
    bob.post(f"/api/requests/{req['id']}/commands", json={"command": "status", "pr_number": pr})
    out = capsys.readouterr().out
    with portal.container.db.sessionmaker() as db:
        stored = [lnk.access_token_enc for lnk in db.scalars(select(GitHubLink))]
    toks = all_tokens(portal)
    assert toks
    for t in toks:
        assert t not in out, "token leaked into logs"
        for body in portal.responses:
            assert t not in body, "token leaked into an API response"
        for blob in stored:
            assert blob is None or t.encode() not in blob, "token stored unencrypted"


def test_frontend_source_has_no_tokens_or_secrets():
    src = FRONTEND / "src"
    if not src.exists():
        pytest.skip("frontend not present")
    import re

    pattern = re.compile(r"gh[pousr]_[A-Za-z0-9]{10,}|github_pat_|GITHUB_APP_PRIVATE_KEY|client_secret", re.I)
    for f in src.rglob("*"):
        if f.suffix in (".ts", ".tsx", ".js", ".css", ".html"):
            assert not pattern.search(f.read_text(encoding="utf-8")), f


def test_redaction():
    assert "ghu_abcdefghijklmnop1234" not in redact("token ghu_abcdefghijklmnop1234 here")
    assert redact("https://x?code=abc123&state=1") == "https://x?code=[REDACTED]&state=1"
    assert "abcdefghijklmnop" not in redact("Authorization: Bearer abcdefghijklmnop.qrs")
    rec = logging.LogRecord("x", logging.INFO, __file__, 1, "leak ghs_1234567890abcdefXYZ", None, None)
    assert "ghs_1234567890abcdefXYZ" not in RedactingJsonFormatter().format(rec)


# ------------------------------------------------------------------ configuration safety
def test_dev_bypass_impossible_in_production():
    with pytest.raises(UnsafeConfigurationError):
        Settings(app_env="production", auth_mode="dev")
    with pytest.raises(UnsafeConfigurationError):
        Settings(app_env="production", github_mode="fake")


def test_dev_bypass_requires_loopback():
    with pytest.raises(UnsafeConfigurationError):
        Settings(app_env="development", auth_mode="dev", bind_host="0.0.0.0")  # noqa: S104


def test_production_requires_secrets_and_https():
    with pytest.raises(UnsafeConfigurationError) as ei:
        Settings(app_env="production")
    assert "TOKEN_ENCRYPTION_KEY" in str(ei.value) and "GITHUB_WEBHOOK_SECRET" in str(ei.value)


def test_dev_routes_absent_in_entra_mode(tmp_path):
    from app.main import create_app

    s = Settings(
        app_env="test",
        auth_mode="entra",
        github_mode="fake",
        database_url=f"sqlite:///{tmp_path}/x.db",
        data_dir=tmp_path,
        poller_enabled=False,
    )
    c = TestClient(create_app(s))
    assert c.post("/auth/dev-login", json={"username": "alice"}).status_code in (404, 405)


def test_session_cookie_flags(portal_factory):
    p = portal_factory(public_base_url="https://portal.example.test")
    c = TestClient(p.app, base_url="https://testserver")
    r = c.post("/auth/dev-login", json={"username": "alice"})
    cookie = r.headers["set-cookie"].lower()
    assert "httponly" in cookie and "secure" in cookie and "samesite=lax" in cookie


def test_cross_origin_dev_login_rejected(portal):
    c = TestClient(portal.app)
    r = c.post("/auth/dev-login", json={"username": "alice"}, headers={"Origin": "https://evil.example"})
    assert r.status_code == 403


# ------------------------------------------------------------------ webhooks
def _sig(secret: str, body: bytes) -> str:
    return "sha256=" + hmac.new(secret.encode(), body, hashlib.sha256).hexdigest()


def test_webhook_signature_and_replay(portal_factory):
    p = portal_factory(github_webhook_secret="s3cret")
    req = p.submit_text("alice", CLEAR_REQUIREMENT)
    c = TestClient(p.app)
    body = json.dumps({"action": "labeled", "issue": {"number": req["issue_number"]}}).encode()
    headers = {"X-GitHub-Event": "issues", "X-GitHub-Delivery": "d-1", "Content-Type": "application/json"}
    assert (
        c.post("/webhooks/github", content=body, headers={**headers, "X-Hub-Signature-256": "sha256=bad"}).status_code
        == 401
    )
    assert c.post("/webhooks/github", content=body, headers=headers).status_code == 401
    ok = c.post("/webhooks/github", content=body, headers={**headers, "X-Hub-Signature-256": _sig("s3cret", body)})
    assert ok.status_code == 204
    replay = c.post("/webhooks/github", content=body, headers={**headers, "X-Hub-Signature-256": _sig("s3cret", body)})
    assert replay.status_code == 204
    detail = p.client("alice").get(f"/api/requests/{req['id']}").json()
    assert detail["last_synced_at"] is not None


def test_webhook_rejected_when_secret_unset(portal):
    c = TestClient(portal.app)
    body = b"{}"
    assert c.post("/webhooks/github", content=body, headers={"X-Hub-Signature-256": _sig("", body)}).status_code == 401


# ------------------------------------------------------------------ Entra ID token validation
class _Key:
    def __init__(self, key):
        self.key = key


class _Jwks:
    def __init__(self, pub):
        self.pub = pub

    def get_signing_key_from_jwt(self, _):
        return _Key(self.pub)


@pytest.fixture(scope="module")
def rsa_keys():
    priv = rsa.generate_private_key(public_exponent=65537, key_size=2048)
    pem = priv.private_bytes(
        serialization.Encoding.PEM, serialization.PrivateFormat.PKCS8, serialization.NoEncryption()
    )
    return pem, priv.public_key()


def _token(pem, **over):
    claims = {
        "aud": "client-1",
        "iss": "https://login.microsoftonline.com/tenant-1/v2.0",
        "iat": int(time.time()),
        "exp": int(time.time()) + 600,
        "nonce": "n1",
        "oid": "oid-1",
        "tid": "tenant-1",
        "name": "Ann",
        "preferred_username": "ann@example.test",
        "roles": ["Requester"],
    }
    claims.update(over)
    return jwt.encode(claims, pem, algorithm="RS256")


def test_entra_id_token_validation(rsa_keys):
    pem, pub = rsa_keys
    e = EntraClient("tenant-1", "client-1", "secret", "https://p/auth/callback", jwks_client=_Jwks(pub))
    ident = e.validate(_token(pem), "n1")
    assert ident.oid == "oid-1" and ident.roles == ["Requester"]
    for bad in (
        {"aud": "other"},
        {"nonce": "x"},
        {"iss": "https://evil/v2.0"},
        {"exp": int(time.time()) - 10},
        {"tid": "other-tenant"},
    ):
        with pytest.raises(EntraError):
            e.validate(_token(pem, **bad), "n1")


def test_entra_authorize_uses_pkce_and_state():
    e = EntraClient("tenant-1", "client-1", "secret", "https://p/auth/callback", jwks_client=object())
    url, flow = e.start()
    assert "code_challenge_method=S256" in url and f"state={flow['state']}" in url and flow["verifier"]
