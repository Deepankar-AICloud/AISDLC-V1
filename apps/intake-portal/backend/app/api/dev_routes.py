"""Development-only routes for the fake GitHub (registered only when GITHUB_MODE=fake in development/test)."""

from __future__ import annotations

from typing import Any
from urllib.parse import urlencode

from fastapi import APIRouter, Depends, Form, Request
from fastapi.responses import HTMLResponse, RedirectResponse
from sqlalchemy.orm import Session

from ..auth.session import SessionManager
from ..container import Container
from ..errors import ApiError
from .auth_routes import fake_authorize_page
from .deps import container, db_session, sessions

router = APIRouter(prefix="/dev/fake-github")


def _fake(c: Container):
    if c.fake is None:
        raise ApiError(404, "not_found", "Not found.")
    return c.fake


@router.get("/login/oauth/authorize", response_class=HTMLResponse)
def authorize(
    request: Request,
    client_id: str = "",
    redirect_uri: str = "",
    state: str = "",
    c: Container = Depends(container),
    sm: SessionManager = Depends(sessions),
    db: Session = Depends(db_session),
) -> HTMLResponse:
    _fake(c)
    return fake_authorize_page(c, sm, request, db, client_id, redirect_uri, state)


@router.post("/login/oauth/authorize")
def authorize_submit(
    login: str = Form(...), state: str = Form(...), redirect_uri: str = Form(""), c: Container = Depends(container)
) -> RedirectResponse:
    fake = _fake(c)
    if login not in fake.users:
        raise ApiError(404, "not_found", "Unknown fake user.")
    code = fake.issue_oauth_code(login)
    # Always our own callback, never the posted value (no open redirect).
    return RedirectResponse(f"{c.oauth.redirect_uri}?{urlencode({'code': code, 'state': state})}", status_code=302)


@router.post("/production-run")
def production_run(c: Container = Depends(container)) -> dict[str, Any]:
    run = _fake(c).start_production_run()
    return {"run_id": run["id"]}


@router.post("/state")
def state_summary(c: Container = Depends(container)) -> dict[str, Any]:
    fake = _fake(c)
    return {
        "issues": {n: {"labels": fake.labels(n), "author": i["user"]["login"]} for n, i in fake.s.issues.items()},
        "comments": {
            n: [{"author": x["user"]["login"], "body": x["body"][:200]} for x in cs]
            for n, cs in fake.s.comments.items()
        },
        "reviews": {
            n: [{"author": r["user"]["login"], "state": r["state"]} for r in rs] for n, rs in fake.s.reviews.items()
        },
        "label_log": fake.s.label_log,
    }
