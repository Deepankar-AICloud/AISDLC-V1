"""GitHub App authentication: app JWT, down-scoped installation tokens, user OAuth."""

from __future__ import annotations

import threading
import time
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from urllib.parse import urlencode

import jwt

from .http import GitHubError, GitHubHTTP

# The service identity never needs to write pull requests, so it cannot review them.
SERVICE_TOKEN_PERMISSIONS: dict[str, str] = {
    "issues": "write",
    "contents": "write",
    "pull_requests": "read",
    "actions": "read",
    "metadata": "read",
    "deployments": "read",
}


def make_app_jwt(app_id: str, private_key: str, now: float | None = None) -> str:
    now = int(now or time.time())
    return jwt.encode({"iat": now - 60, "exp": now + 540, "iss": app_id}, private_key, algorithm="RS256")


class InstallationTokenProvider:
    def __init__(
        self,
        http: GitHubHTTP,
        *,
        app_id: str,
        private_key: str,
        owner: str,
        repo: str,
        installation_id: str = "",
        permissions: dict[str, str] | None = None,
    ) -> None:
        self.http = http
        self.app_id = app_id
        self.private_key = private_key
        self.owner = owner
        self.repo = repo
        self.installation_id = installation_id
        self.permissions = permissions or SERVICE_TOKEN_PERMISSIONS
        self._token = ""
        self._expires = 0.0
        self._lock = threading.Lock()

    def __call__(self) -> str:
        with self._lock:
            if self._token and time.time() < self._expires - 300:
                return self._token
            app_jwt = make_app_jwt(self.app_id, self.private_key)
            if not self.installation_id:
                data = self.http.request("GET", f"/repos/{self.owner}/{self.repo}/installation", app_jwt).json()
                self.installation_id = str(data["id"])
            data = self.http.request(
                "POST",
                f"/app/installations/{self.installation_id}/access_tokens",
                app_jwt,
                json={"repositories": [self.repo], "permissions": self.permissions},
            ).json()
            self._token = data["token"]
            exp = datetime.fromisoformat(data["expires_at"].replace("Z", "+00:00"))
            self._expires = exp.timestamp()
            return self._token


@dataclass
class TokenSet:
    access_token: str
    access_expires_at: datetime | None
    refresh_token: str | None
    refresh_expires_at: datetime | None


class OAuthError(Exception):
    pass


class GitHubOAuth:
    """GitHub App user-to-server OAuth web flow (no scopes: the App's permissions apply)."""

    def __init__(self, web_http: GitHubHTTP, web_url: str, client_id: str, client_secret: str, redirect_uri: str):
        self.web_http = web_http
        self.web_url = web_url.rstrip("/")
        self.client_id = client_id
        self.client_secret = client_secret
        self.redirect_uri = redirect_uri

    def authorize_url(self, state: str) -> str:
        q = urlencode(
            {"client_id": self.client_id, "redirect_uri": self.redirect_uri, "state": state, "allow_signup": "false"}
        )
        return f"{self.web_url}/login/oauth/authorize?{q}"

    def _token_call(self, payload: dict[str, str]) -> TokenSet:
        try:
            data = self.web_http.request(
                "POST",
                "/login/oauth/access_token",
                None,
                json={"client_id": self.client_id, "client_secret": self.client_secret, **payload},
                accept="application/json",
            ).json()
        except GitHubError as exc:
            raise OAuthError(f"GitHub token exchange failed ({exc.status}).") from exc
        if "error" in data or "access_token" not in data:
            raise OAuthError(str(data.get("error_description") or data.get("error") or "token exchange failed"))
        now = datetime.now(UTC).replace(tzinfo=None)
        exp = now + timedelta(seconds=int(data["expires_in"])) if data.get("expires_in") else None
        rexp = (
            now + timedelta(seconds=int(data["refresh_token_expires_in"]))
            if data.get("refresh_token_expires_in")
            else None
        )
        return TokenSet(data["access_token"], exp, data.get("refresh_token"), rexp)

    def exchange(self, code: str) -> TokenSet:
        return self._token_call({"code": code, "redirect_uri": self.redirect_uri})

    def refresh(self, refresh_token: str) -> TokenSet:
        return self._token_call({"grant_type": "refresh_token", "refresh_token": refresh_token})
