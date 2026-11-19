"""Portal sign-in and the named-user GitHub connect (OAuth) flow."""

from __future__ import annotations

import html
import secrets
from typing import Any

from fastapi import APIRouter, Depends, Request, Response
from fastapi.responses import HTMLResponse, RedirectResponse
from pydantic import BaseModel, Field, SecretStr
from sqlalchemy import select
from sqlalchemy.orm import Session

from ..audit import record
from ..auth.entra import EntraError, EntraIdentity
from ..auth.session import CSRF_HEADER, SessionManager
from ..container import Container
from ..db import GitHubLink, User, utcnow
from ..errors import ApiError
from ..extract import allowed_extensions
from ..github.app_auth import OAuthError
from ..github.clients import UserGitHubClient
from ..github.http import GitHubError
from ..github.identity import get_link, require_individual_user, store_tokens
from .deps import container, current_user, db_session, sessions

router = APIRouter()
NOTICE = (
    "Do not upload secrets, credentials or regulated personal data unless that is approved for this "
    "repository. Everything you submit is copied into a GitHub issue."
)


def upsert_user(db: Session, ident: EntraIdentity) -> User:
    user = db.scalar(select(User).where(User.entra_oid == ident.oid))
    if user is None:
        user = User(entra_oid=ident.oid)
        db.add(user)
    user.display_name = ident.name
    user.email = ident.email
    user.roles = ident.roles
    user.last_login_at = utcnow()
    db.commit()
    return user


def dev_users(c: Container) -> dict[str, dict[str, Any]]:
    out: dict[str, dict[str, Any]] = {}
    for entry in c.settings.dev_users.split(";"):
        parts = entry.strip().split(":")
        if len(parts) >= 2 and parts[0]:
            out[parts[0]] = {
                "username": parts[0],
                "roles": [r for r in parts[1].split(",") if r],
                "github_login": parts[2] if len(parts) > 2 else "",
                "password": "",
            }
    admin_password = c.settings.dev_admin_password.get_secret_value()
    if admin_password:
        out["admin"] = {
            "username": "admin",
            "roles": ["Requester", "Reviewer"],
            "github_login": "admin-gh",
            "password": admin_password,
        }
    return out


ROLE_RANK = {"none": 0, "read": 1, "triage": 2, "write": 3, "maintain": 4, "admin": 5}
GITHUB_OID_PREFIX = "github:"
LOGIN_FLOW_COOKIE = "portal_ghlogin"


def sign_in_kind(user: User) -> str:
    if user.is_shared:
        return "password"
    if user.entra_oid.startswith(GITHUB_OID_PREFIX):
        return "github"
    if user.entra_oid.startswith("dev-"):
        return "dev"
    return "microsoft"


@router.get("/auth/options")
def auth_options(request: Request, c: Container = Depends(container)) -> dict[str, bool]:
    """Public: which sign-in methods this server offers (for the login page)."""
    return {
        "microsoft": request.app.state.entra is not None,
        "github": c.settings.github_signin_enabled,
        "dev": c.settings.auth_mode == "dev",
        "password": c.settings.auth_mode == "password",
        "open": c.settings.auth_mode == "open",
    }


def _check_origin_and_rate(request: Request, c: Container, bucket: str) -> None:
    origin = request.headers.get("origin")
    if origin and origin.rstrip("/") not in {c.settings.public_base_url.rstrip("/"), *c.settings.cors_origins}:
        raise ApiError(403, "bad_origin", "Cross-origin sign-in is not allowed.")
    peer = request.client.host if request.client else "unknown"
    if not c.rate.allow(peer, bucket, c.settings.rate_limit_login_per_min):
        raise ApiError(429, "rate_limited", "Too many sign-in attempts. Wait a minute and try again.")


def _sign_in_shared(db: Session, c: Container, sm: SessionManager, response: Response, action: str) -> dict[str, str]:
    user = upsert_user(
        db,
        EntraIdentity(oid="shared:admin", name="Admin (shared)", email="", roles=[c.settings.entra_requester_role]),
    )
    record(
        db,
        user=user,
        github_login="",
        identity="portal",
        action=action,
        target_type="account",
        target_ref="shared:admin",
        outcome="ok",
    )
    return {"status": "signed_in", "csrf_token": sm.issue(response, user.id)}


@router.post("/auth/open-session")
def open_session(
    request: Request,
    response: Response,
    db: Session = Depends(db_session),
    c: Container = Depends(container),
    sm: SessionManager = Depends(sessions),
) -> dict[str, str]:
    """AUTH_MODE=open: start a shared-requester session without credentials."""
    if c.settings.auth_mode != "open":
        raise ApiError(404, "not_found", "Open access is not enabled.")
    _check_origin_and_rate(request, c, "open-session")
    return _sign_in_shared(db, c, sm, response, "open_session")


class PasswordLogin(BaseModel):
    username: str = Field(max_length=100)
    password: SecretStr = Field(max_length=1024)


@router.post("/auth/password-login")
def password_login(
    body: PasswordLogin,
    request: Request,
    response: Response,
    db: Session = Depends(db_session),
    c: Container = Depends(container),
    sm: SessionManager = Depends(sessions),
) -> dict[str, str]:
    if c.settings.auth_mode != "password":
        raise ApiError(404, "not_found", "Password sign-in is not enabled.")
    _check_origin_and_rate(request, c, "password-login")
    valid_user = secrets.compare_digest(body.username.encode(), b"admin")
    valid_password = secrets.compare_digest(
        body.password.get_secret_value().encode(), c.settings.portal_admin_password.get_secret_value().encode()
    )
    if not (valid_user and valid_password):
        raise ApiError(401, "bad_credentials", "Incorrect username or password.")
    return _sign_in_shared(db, c, sm, response, "password_signin")


@router.get("/auth/github/login")
def github_login(c: Container = Depends(container), sm: SessionManager = Depends(sessions)) -> Response:
    if not c.settings.github_signin_enabled:
        raise ApiError(404, "not_found", "GitHub sign-in is not enabled.")
    state = secrets.token_urlsafe(24)
    resp = RedirectResponse(c.oauth.authorize_url(state), status_code=302)
    sm.set_flow(resp, LOGIN_FLOW_COOKIE, {"state": state, "purpose": "signin"})
    return resp


def github_signin_callback(
    request: Request, code: str, state: str, db: Session, c: Container, sm: SessionManager
) -> Response:
    """Sign in (or register) a portal user from a verified GitHub account."""
    resp = RedirectResponse("/", status_code=302)
    flow = sm.pop_flow(request, resp, LOGIN_FLOW_COOKIE)

    def fail(reason: str, login: str = "", detail: str = "") -> Response:
        if login:
            record(
                db,
                user=None,
                github_login=login,
                identity="user",
                action="github_signin",
                target_type="account",
                target_ref=login,
                outcome="rejected",
                detail=detail or reason,
            )
        r = RedirectResponse(f"/login?error={reason}", status_code=302)
        r.delete_cookie(LOGIN_FLOW_COOKIE, path="/")
        return r

    s = c.settings
    if not s.github_signin_enabled:
        return fail("github_disabled")
    if (
        not code
        or flow is None
        or flow.get("purpose") != "signin"
        or not secrets.compare_digest(flow.get("state", ""), state)
    ):
        return fail("signin_failed")
    try:
        tokens = c.oauth.exchange(code)
        me = UserGitHubClient(c.http, tokens.access_token, "", 0, c.owner, c.repo).whoami()
    except (OAuthError, GitHubError):
        return fail("signin_failed")
    gh_id, gh_login = int(me["id"]), str(me["login"])
    if me.get("type", "User") != "User":
        return fail("github_no_access", gh_login, "not a user account")
    try:
        role = c.service.collaborator_role(gh_login)
    except GitHubError:
        return fail("signin_failed", gh_login, "repository role lookup failed")
    if ROLE_RANK.get(role, 0) < ROLE_RANK[s.github_signin_min_role]:
        return fail("github_no_access", gh_login, f"repository role '{role}'")
    link = db.scalar(select(GitHubLink).where(GitHubLink.github_id == gh_id))
    if link is not None:
        owner = db.get(User, link.user_id)
        if owner is not None and not owner.entra_oid.startswith(GITHUB_OID_PREFIX):
            # Never let a GitHub account open a portal account that signs in with Microsoft.
            return fail("github_linked_to_microsoft", gh_login, "linked to a Microsoft account")
    is_writer = ROLE_RANK.get(role, 0) >= ROLE_RANK["write"]
    roles = [s.entra_requester_role] + ([s.entra_reviewer_role] if is_writer else [])
    user = upsert_user(
        db,
        EntraIdentity(
            oid=f"{GITHUB_OID_PREFIX}{gh_id}",
            name=str(me.get("name") or gh_login),
            email=str(me.get("email") or ""),
            roles=roles,
        ),
    )
    if link is None:
        link = GitHubLink(user_id=user.id, github_id=gh_id, github_login=gh_login)
        db.add(link)
    link.github_login = gh_login
    store_tokens(c, link, tokens)
    link.connected_at = utcnow()
    db.commit()
    record(
        db,
        user=user,
        github_login=gh_login,
        identity="user",
        action="github_signin",
        target_type="account",
        target_ref=gh_login,
        outcome="ok",
        detail=f"repository role '{role}', portal roles {roles}",
    )
    sm.issue(resp, user.id)
    return resp


# ------------------------------------------------------------------ session
@router.get("/api/me")
def me(
    request: Request,
    user: User = Depends(current_user),
    db: Session = Depends(db_session),
    c: Container = Depends(container),
    sm: SessionManager = Depends(sessions),
) -> dict[str, Any]:
    sess = sm.read(request) or {}
    link = get_link(db, user)
    s = c.settings
    return {
        "user": {"name": user.display_name, "email": user.email, "roles": user.roles, "sign_in": sign_in_kind(user)},
        "csrf_token": sess.get("csrf"),
        "github": {
            "connected": bool(link and not link.revoked),
            "login": link.github_login if link else None,
            "needs_reconnect": bool(link and link.revoked),
        },
        "config": {
            "repository": c.repo_info(),
            "allowed_extensions": allowed_extensions(s.feature_ocr),
            "feature_ocr": s.feature_ocr,
            "max_files": s.max_files,
            "max_file_mb": s.max_file_bytes // (1024 * 1024),
            "max_total_mb": s.max_total_bytes // (1024 * 1024),
            "max_pasted_chars": s.max_pasted_chars,
            "notice": NOTICE,
            "auth_mode": s.auth_mode,
            "github_mode": s.github_mode,
            "reviewer_role": s.entra_reviewer_role,
            "requester_role": s.entra_requester_role,
            "separation_of_duties": s.separation_of_duties,
        },
    }


@router.post("/auth/logout")
def logout(request: Request, response: Response, sm: SessionManager = Depends(sessions)) -> dict[str, str]:
    sess = sm.read(request)
    if sess and not sm.csrf_ok(sess, request.headers.get(CSRF_HEADER)):
        raise ApiError(403, "csrf_failed", "Reload the page and try again.")
    sm.clear(response)
    return {"status": "signed_out"}


# ------------------------------------------------------------------ Entra
@router.get("/auth/login")
def login(request: Request, sm: SessionManager = Depends(sessions)) -> Response:
    entra = request.app.state.entra
    if entra is None:
        return RedirectResponse("/login")
    url, flow = entra.start()
    resp = RedirectResponse(url, status_code=302)
    sm.set_flow(resp, "portal_oidc", flow)
    return resp


@router.get("/auth/callback")
def callback(
    request: Request,
    code: str = "",
    state: str = "",
    error: str = "",
    db: Session = Depends(db_session),
    sm: SessionManager = Depends(sessions),
    c: Container = Depends(container),
) -> Response:
    resp = RedirectResponse("/", status_code=302)
    flow = sm.pop_flow(request, resp, "portal_oidc")
    if error or not code or flow is None or not secrets.compare_digest(flow.get("state", ""), state):
        return RedirectResponse("/login?error=signin_failed", status_code=302)
    try:
        ident = request.app.state.entra.finish(code, flow)
    except EntraError:
        return RedirectResponse("/login?error=signin_failed", status_code=302)
    if not {c.settings.entra_requester_role, c.settings.entra_reviewer_role} & set(ident.roles):
        return RedirectResponse("/login?error=no_role", status_code=302)
    user = upsert_user(db, ident)
    sm.issue(resp, user.id)
    return resp


# ------------------------------------------------------------------ dev bypass (development only)
class DevLogin(BaseModel):
    username: str
    password: str = ""


def dev_auth_router() -> APIRouter:
    app_router = APIRouter()

    @app_router.get("/auth/dev-users")
    def list_dev_users(c: Container = Depends(container)) -> list[dict[str, Any]]:
        # One-click users only; password users sign in with the form and are never listed.
        return [{k: v for k, v in u.items() if k != "password"} for u in dev_users(c).values() if not u["password"]]

    @app_router.post("/auth/dev-login")
    def dev_login(
        body: DevLogin,
        request: Request,
        response: Response,
        db: Session = Depends(db_session),
        sm: SessionManager = Depends(sessions),
        c: Container = Depends(container),
    ) -> dict[str, str]:
        origin = request.headers.get("origin")
        if origin and origin.rstrip("/") not in {c.settings.public_base_url.rstrip("/"), *c.settings.cors_origins}:
            raise ApiError(403, "bad_origin", "Cross-origin sign-in is not allowed.")
        u = dev_users(c).get(body.username)
        if u is None:
            raise ApiError(404, "unknown_dev_user", "Unknown development user.")
        if u["password"] and not secrets.compare_digest(body.password.encode(), u["password"].encode()):
            raise ApiError(401, "bad_credentials", "Incorrect username or password.")
        user = upsert_user(
            db,
            EntraIdentity(
                oid=f"dev-{u['username']}",
                name=u["username"].title() + " (dev)",
                email=f"{u['username']}@example.test",
                roles=u["roles"],
            ),
        )
        csrf = sm.issue(response, user.id)
        return {"status": "signed_in", "csrf_token": csrf}

    return app_router


# ------------------------------------------------------------------ GitHub connect
@router.get("/auth/github/connect")
def github_connect(
    request: Request,
    user: User = Depends(current_user),
    c: Container = Depends(container),
    sm: SessionManager = Depends(sessions),
) -> Response:
    require_individual_user(user)
    state = secrets.token_urlsafe(24)
    resp = RedirectResponse(c.oauth.authorize_url(state), status_code=302)
    sm.set_flow(resp, "portal_gh", {"state": state, "uid": user.id})
    return resp


@router.get("/auth/github/callback")
def github_callback(
    request: Request,
    code: str = "",
    state: str = "",
    db: Session = Depends(db_session),
    c: Container = Depends(container),
    sm: SessionManager = Depends(sessions),
) -> Response:
    if LOGIN_FLOW_COOKIE in request.cookies and "portal_gh" not in request.cookies:
        return github_signin_callback(request, code, state, db, c, sm)
    resp = RedirectResponse("/account?github=connected", status_code=302)
    flow = sm.pop_flow(request, resp, "portal_gh")
    sess = sm.read(request)

    def fail(reason: str) -> Response:
        r = RedirectResponse(f"/account?github=error&reason={reason}", status_code=302)
        r.delete_cookie("portal_gh", path="/")
        return r

    if (
        not code
        or flow is None
        or sess is None
        or flow.get("uid") != sess.get("uid")
        or not secrets.compare_digest(flow.get("state", ""), state)
    ):
        return fail("state")
    user = db.get(User, int(sess["uid"]))
    if user is None:
        return fail("session")
    require_individual_user(user)
    try:
        tokens = c.oauth.exchange(code)
        me = UserGitHubClient(c.http, tokens.access_token, "", 0, c.owner, c.repo).whoami()
    except (OAuthError, GitHubError):
        return fail("exchange")
    gh_id, gh_login = int(me["id"]), str(me["login"])
    other = db.scalar(select(GitHubLink).where(GitHubLink.github_id == gh_id, GitHubLink.user_id != user.id))
    if other is not None:
        record(
            db,
            user=user,
            github_login=gh_login,
            identity="user",
            action="github_connect",
            target_type="account",
            target_ref=gh_login,
            outcome="rejected",
            detail="GitHub account linked to another portal user",
        )
        return fail("already_linked")
    link = get_link(db, user)
    if link is not None and link.github_id != gh_id and not link.revoked:
        record(
            db,
            user=user,
            github_login=gh_login,
            identity="user",
            action="github_connect",
            target_type="account",
            target_ref=gh_login,
            outcome="rejected",
            detail=f"already linked to {link.github_login}",
        )
        return fail("different_account")
    if link is None:
        link = GitHubLink(user_id=user.id, github_id=gh_id, github_login=gh_login)
        db.add(link)
    link.github_id, link.github_login = gh_id, gh_login
    store_tokens(c, link, tokens)
    link.connected_at = utcnow()
    db.commit()
    record(
        db,
        user=user,
        github_login=gh_login,
        identity="user",
        action="github_connect",
        target_type="account",
        target_ref=gh_login,
        outcome="ok",
    )
    return resp


@router.post("/api/github/disconnect")
def github_disconnect(user: User = Depends(current_user), db: Session = Depends(db_session)) -> dict[str, str]:
    if user.entra_oid.startswith(GITHUB_OID_PREFIX):
        raise ApiError(
            409,
            "github_identity",
            "You signed in with GitHub, so the GitHub connection is your identity. Sign out instead.",
        )
    link = get_link(db, user)
    if link:
        login = link.github_login
        db.delete(link)
        db.commit()
        record(
            db,
            user=user,
            github_login=login,
            identity="user",
            action="github_disconnect",
            target_type="account",
            target_ref=login,
            outcome="ok",
        )
    return {"status": "disconnected"}


def fake_authorize_page(
    c: Container, sm: SessionManager, request: Request, db: Session, client_id: str, redirect_uri: str, state: str
) -> HTMLResponse:
    """Development stand-in for github.com's authorize screen."""
    sess = sm.read(request)
    user = db.get(User, int(sess["uid"])) if sess else None
    mapped = ""
    if user is not None:
        mapped = dev_users(c).get(user.entra_oid.removeprefix("dev-"), {}).get("github_login", "")
    assert c.fake is not None
    options = "".join(
        f'<option value="{html.escape(lg)}"{" selected" if lg == mapped else ""}>{html.escape(lg)}</option>'
        for lg in sorted(c.fake.users)
        if not lg.endswith("[bot]")
    )
    safe_redirect = html.escape(redirect_uri)
    page = f"""<!doctype html><html lang="en"><head><meta charset="utf-8"><title>Authorize (fake GitHub)</title>
<style>body{{font-family:system-ui;max-width:32rem;margin:3rem auto;padding:0 1rem}}button{{padding:.6rem 1rem}}</style>
</head><body><h1>Fake GitHub: authorize AISDLC Portal</h1>
<p>Development only. Choose the GitHub account to use, or create a new one.</p>
<form method="post" action="/dev/fake-github/login/oauth/authorize">
<input type="hidden" name="redirect_uri" value="{safe_redirect}"><input type="hidden" name="state"
value="{html.escape(state)}"><label for="login">GitHub account</label>
<select id="login" name="login">{options}</select>
<p><label for="new_login">Or create a new GitHub account (gets triage access)</label>
<input id="new_login" name="new_login" pattern="[A-Za-z0-9-]{{1,39}}" placeholder="new-user-gh"></p>
<button type="submit">Authorize</button></form></body></html>"""
    return HTMLResponse(page)
