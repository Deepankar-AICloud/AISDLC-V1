"""Portal sign-in (Entra ID or dev bypass) and the GitHub connect (OAuth) flow."""

from __future__ import annotations

import html
import secrets
from typing import Any

from fastapi import APIRouter, Depends, Request, Response
from fastapi.responses import HTMLResponse, RedirectResponse
from pydantic import BaseModel
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
from ..github.identity import get_link, store_tokens
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
            }
    return out


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
        "user": {"name": user.display_name, "email": user.email, "roles": user.roles},
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


def dev_auth_router() -> APIRouter:
    app_router = APIRouter()

    @app_router.get("/auth/dev-users")
    def list_dev_users(c: Container = Depends(container)) -> list[dict[str, Any]]:
        return list(dev_users(c).values())

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
<p>Development only. Choose the GitHub account to connect.</p>
<form method="post" action="/dev/fake-github/login/oauth/authorize">
<input type="hidden" name="redirect_uri" value="{safe_redirect}"><input type="hidden" name="state"
value="{html.escape(state)}"><label for="login">GitHub account</label>
<select id="login" name="login">{options}</select> <button type="submit">Authorize</button></form></body></html>"""
    return HTMLResponse(page)
