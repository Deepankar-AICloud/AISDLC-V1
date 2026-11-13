"""Microsoft Entra ID sign-in: OIDC authorization code flow with PKCE, validated server-side."""

from __future__ import annotations

import base64
import hashlib
import secrets
from dataclasses import dataclass
from typing import Any
from urllib.parse import urlencode

import httpx
import jwt


@dataclass
class EntraIdentity:
    oid: str
    name: str
    email: str
    roles: list[str]


class EntraError(Exception):
    pass


class EntraClient:
    def __init__(
        self,
        tenant_id: str,
        client_id: str,
        client_secret: str,
        redirect_uri: str,
        transport: httpx.BaseTransport | None = None,
        jwks_client: Any = None,
    ) -> None:
        self.tenant = tenant_id
        self.client_id = client_id
        self.client_secret = client_secret
        self.redirect_uri = redirect_uri
        self.authority = f"https://login.microsoftonline.com/{tenant_id}"
        self.http = httpx.Client(transport=transport, timeout=15)
        self.jwks = jwks_client or jwt.PyJWKClient(f"{self.authority}/discovery/v2.0/keys", cache_keys=True)

    def start(self) -> tuple[str, dict[str, str]]:
        state = secrets.token_urlsafe(24)
        nonce = secrets.token_urlsafe(24)
        verifier = secrets.token_urlsafe(48)
        challenge = base64.urlsafe_b64encode(hashlib.sha256(verifier.encode()).digest()).rstrip(b"=").decode()
        q = urlencode(
            {
                "client_id": self.client_id,
                "response_type": "code",
                "redirect_uri": self.redirect_uri,
                "response_mode": "query",
                "scope": "openid profile email",
                "state": state,
                "nonce": nonce,
                "code_challenge": challenge,
                "code_challenge_method": "S256",
            }
        )
        return f"{self.authority}/oauth2/v2.0/authorize?{q}", {"state": state, "nonce": nonce, "verifier": verifier}

    def finish(self, code: str, flow: dict[str, str]) -> EntraIdentity:
        resp = self.http.post(
            f"{self.authority}/oauth2/v2.0/token",
            data={
                "client_id": self.client_id,
                "client_secret": self.client_secret,
                "grant_type": "authorization_code",
                "code": code,
                "redirect_uri": self.redirect_uri,
                "code_verifier": flow["verifier"],
                "scope": "openid profile email",
            },
        )
        if resp.status_code != 200:
            raise EntraError("Sign-in failed: the authorization code was rejected.")
        id_token = resp.json().get("id_token")
        if not id_token:
            raise EntraError("Sign-in failed: no ID token was returned.")
        return self.validate(id_token, flow["nonce"])

    def validate(self, id_token: str, nonce: str) -> EntraIdentity:
        try:
            key = self.jwks.get_signing_key_from_jwt(id_token)
            claims = jwt.decode(
                id_token,
                key.key,
                algorithms=["RS256"],
                audience=self.client_id,
                issuer=f"{self.authority}/v2.0",
                options={"require": ["exp", "iat", "aud", "iss"]},
            )
        except jwt.PyJWTError as exc:
            raise EntraError("Sign-in failed: the ID token is invalid.") from exc
        if claims.get("nonce") != nonce:
            raise EntraError("Sign-in failed: nonce mismatch.")
        if claims.get("tid") and claims["tid"] != self.tenant:
            raise EntraError("Sign-in failed: wrong tenant.")
        return EntraIdentity(
            oid=str(claims["oid"]),
            name=str(claims.get("name", "")),
            email=str(claims.get("preferred_username") or claims.get("email") or ""),
            roles=[str(r) for r in claims.get("roles", [])],
        )
