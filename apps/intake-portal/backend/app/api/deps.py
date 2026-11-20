from __future__ import annotations

from collections.abc import Iterator

from fastapi import Depends, Request
from sqlalchemy.orm import Session

from ..auth.session import CSRF_HEADER, SessionManager
from ..container import Container
from ..db import IntakeRequest, User
from ..errors import ApiError, not_found
from ..status.sync import can_view

UNSAFE = {"POST", "PUT", "PATCH", "DELETE"}


def container(request: Request) -> Container:
    return request.app.state.container


def sessions(request: Request) -> SessionManager:
    return request.app.state.sessions


def db_session(c: Container = Depends(container)) -> Iterator[Session]:
    with c.db.sessionmaker() as s:
        yield s


def current_user(request: Request, db: Session = Depends(db_session), sm: SessionManager = Depends(sessions)) -> User:
    sess = sm.read(request)
    if sess is None:
        raise ApiError(401, "not_signed_in", "Sign in to continue.")
    user = db.get(User, int(sess["uid"]))
    if user is None:
        raise ApiError(401, "not_signed_in", "Sign in to continue.")
    if user.is_shared and container(request).settings.auth_mode not in ("password", "open"):
        raise ApiError(401, "not_signed_in", "Shared sign-in is no longer enabled.")
    if request.method in UNSAFE and not sm.csrf_ok(sess, request.headers.get(CSRF_HEADER)):
        raise ApiError(403, "csrf_failed", "Your session token is missing or stale. Reload the page and try again.")
    request.state.user_id = user.id
    return user


def rate_limit(bucket: str):
    def dep(request: Request, user: User = Depends(current_user), c: Container = Depends(container)) -> User:
        per = {
            "submit": c.settings.rate_limit_submit_per_min,
            "action": c.settings.rate_limit_actions_per_min,
            "read": c.settings.rate_limit_reads_per_min,
        }[bucket]
        if not c.rate.allow(str(user.id), bucket, per):
            raise ApiError(429, "rate_limited", "Too many requests. Wait a minute and try again.")
        return user

    return dep


def load_request(db: Session, c: Container, user: User, request_id: str) -> IntakeRequest:
    req = db.get(IntakeRequest, request_id)
    if req is None or not can_view(c, db, user, req):
        raise not_found()
    return req


def load_owned_request(db: Session, user: User, request_id: str) -> IntakeRequest:
    req = db.get(IntakeRequest, request_id)
    if req is None or req.requester_id != user.id:
        raise not_found()
    return req


def require_role(user: User, role: str) -> None:
    if role not in (user.roles or []):
        raise ApiError(403, "role_required", f"This action needs the {role} role in the portal.")


def require_individual_identity(c: Container, user: User) -> None:
    if c.settings.auth_mode == "open" or user.is_shared:
        raise ApiError(
            503,
            "individual_sign_in_required",
            "Personal request tracking requires an individual sign-in. Ask your administrator to enable "
            "Microsoft Entra sign-in.",
        )
