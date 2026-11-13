"""Signed, HttpOnly session cookie. It carries only the user id and a CSRF token (never GitHub tokens)."""

from __future__ import annotations

import hmac
import secrets
from typing import Any

from fastapi import Request, Response
from itsdangerous import BadSignature, URLSafeTimedSerializer

COOKIE = "portal_session"
CSRF_HEADER = "x-csrf-token"


class SessionManager:
    def __init__(self, secret: str, max_age: int, secure: bool) -> None:
        self.ser = URLSafeTimedSerializer(secret, salt="aisdlc-portal-session")
        self.flow = URLSafeTimedSerializer(secret, salt="aisdlc-portal-flow")
        self.max_age = max_age
        self.secure = secure

    def issue(self, response: Response, user_id: int) -> str:
        csrf = secrets.token_urlsafe(32)
        value = self.ser.dumps({"uid": user_id, "csrf": csrf})
        response.set_cookie(
            COOKIE, value, max_age=self.max_age, httponly=True, secure=self.secure, samesite="lax", path="/"
        )
        return csrf

    def read(self, request: Request) -> dict[str, Any] | None:
        raw = request.cookies.get(COOKIE)
        if not raw:
            return None
        try:
            data = self.ser.loads(raw, max_age=self.max_age)
        except BadSignature:
            return None
        return data if isinstance(data, dict) and "uid" in data else None

    def clear(self, response: Response) -> None:
        response.delete_cookie(COOKIE, path="/")

    # Short-lived signed cookies for OIDC / OAuth round trips (state, nonce, PKCE verifier).
    def set_flow(self, response: Response, name: str, data: dict[str, Any]) -> None:
        response.set_cookie(
            name, self.flow.dumps(data), max_age=600, httponly=True, secure=self.secure, samesite="lax", path="/"
        )

    def pop_flow(self, request: Request, response: Response, name: str) -> dict[str, Any] | None:
        raw = request.cookies.get(name)
        response.delete_cookie(name, path="/")
        if not raw:
            return None
        try:
            data = self.flow.loads(raw, max_age=600)
        except BadSignature:
            return None
        return data if isinstance(data, dict) else None

    @staticmethod
    def csrf_ok(session: dict[str, Any], header_value: str | None) -> bool:
        return bool(header_value) and hmac.compare_digest(str(session.get("csrf", "")), header_value or "")
