"""Identity mapping: one Entra user <-> one GitHub account, and user-token resolution.

There is no fallback identity. If a user is not linked, or their token is expired
and cannot be refreshed, or GitHub says it was revoked, the action is blocked and
the user is asked to reconnect.
"""

from __future__ import annotations

from datetime import timedelta

from sqlalchemy import select
from sqlalchemy.orm import Session

from ..container import Container
from ..db import GitHubLink, User, utcnow
from ..errors import ApiError
from .app_auth import OAuthError, TokenSet
from .clients import UserGitHubClient
from .http import GitHubError


def not_linked() -> ApiError:
    return ApiError(
        409,
        "github_not_linked",
        "Connect your GitHub account first. Comments, reviews and approvals are always made with "
        "your own GitHub identity, never a shared account.",
    )


def reconnect_required(reason: str = "") -> ApiError:
    return ApiError(
        409,
        "github_reconnect_required",
        "Your GitHub connection has expired or was revoked. Reconnect GitHub and try again."
        + (f" ({reason})" if reason else ""),
    )


def get_link(db: Session, user: User) -> GitHubLink | None:
    return db.scalar(select(GitHubLink).where(GitHubLink.user_id == user.id))


def require_individual_user(user: User) -> None:
    if user.is_shared:
        raise ApiError(
            403,
            "shared_identity",
            "The shared account can submit requirements and view results. Sign in with your own reviewer "
            "account for answers, model decisions, reviews and approvals.",
        )


def link_for_login(db: Session, login: str) -> GitHubLink | None:
    return db.scalar(select(GitHubLink).where(GitHubLink.github_login.ilike(login)))


def store_tokens(c: Container, link: GitHubLink, tokens: TokenSet) -> None:
    link.access_token_enc = c.cipher.encrypt_str(tokens.access_token)
    link.refresh_token_enc = c.cipher.encrypt_str(tokens.refresh_token) if tokens.refresh_token else None
    link.access_expires_at = tokens.access_expires_at
    link.refresh_expires_at = tokens.refresh_expires_at
    link.revoked = False


def mark_revoked(db: Session, link: GitHubLink) -> None:
    link.revoked = True
    link.access_token_enc = None
    link.refresh_token_enc = None
    db.commit()


def user_client(c: Container, db: Session, user: User, *, verify_identity: bool = False) -> UserGitHubClient:
    require_individual_user(user)
    link = get_link(db, user)
    if link is None:
        raise not_linked()
    if link.revoked or link.access_token_enc is None:
        raise reconnect_required()
    now = utcnow()
    if link.access_expires_at and link.access_expires_at - timedelta(minutes=2) <= now:
        if not link.refresh_token_enc or (link.refresh_expires_at and link.refresh_expires_at <= now):
            mark_revoked(db, link)
            raise reconnect_required("token expired")
        try:
            tokens = c.oauth.refresh(c.cipher.decrypt_str(link.refresh_token_enc))
        except OAuthError as exc:
            mark_revoked(db, link)
            raise reconnect_required("refresh failed") from exc
        store_tokens(c, link, tokens)
        db.commit()
    client = UserGitHubClient(
        c.http, c.cipher.decrypt_str(link.access_token_enc), link.github_login, link.github_id, c.owner, c.repo
    )
    if verify_identity:
        try:
            me = client.whoami()
        except GitHubError as exc:
            if exc.kind == "auth":
                mark_revoked(db, link)
                raise reconnect_required() from exc
            raise
        if int(me.get("id", -1)) != link.github_id:
            mark_revoked(db, link)
            raise ApiError(
                409,
                "github_identity_mismatch",
                "The GitHub token no longer belongs to the linked account. Reconnect GitHub.",
            )
    return client
