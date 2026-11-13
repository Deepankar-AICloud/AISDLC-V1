"""Shared GitHub HTTP layer: error mapping and rate-limit backoff.

Retries never change identity: the token is fixed for the lifetime of a call.
Non-idempotent requests (POST/PATCH) are retried only when GitHub rejected them
before acting (429 / primary or secondary rate limit), never on 5xx or network
errors, so a comment or review is never posted twice.
"""

from __future__ import annotations

import logging
import time
from collections.abc import Callable
from dataclasses import dataclass
from typing import Any

import httpx

log = logging.getLogger(__name__)
MAX_WAIT_SECONDS = 60


@dataclass
class GitHubError(Exception):
    status: int
    kind: str
    message: str
    documentation_url: str = ""

    def __str__(self) -> str:
        return f"GitHub {self.status} ({self.kind}): {self.message}"


class IdentityViolation(RuntimeError):
    """A call was attempted with an identity that must never perform it."""


def _kind(resp: httpx.Response) -> str:
    s = resp.status_code
    if s == 401:
        return "auth"
    if s == 429 or (s == 403 and _is_rate_limited(resp)):
        return "rate_limited"
    if s == 403:
        return "forbidden"
    if s == 404:
        return "not_found"
    if s == 405:
        return "not_allowed"
    if s == 409:
        return "conflict"
    if s == 422:
        return "validation"
    if s >= 500:
        return "server"
    return "error"


def _is_rate_limited(resp: httpx.Response) -> bool:
    if resp.headers.get("x-ratelimit-remaining") == "0":
        return True
    try:
        msg = str(resp.json().get("message", "")).lower()
    except ValueError:
        msg = ""
    return "rate limit" in msg


def error_from(resp: httpx.Response) -> GitHubError:
    try:
        data = resp.json()
    except ValueError:
        data = {}
    message = str(data.get("message") or resp.reason_phrase or "GitHub request failed")
    errors = data.get("errors")
    if isinstance(errors, list) and errors:
        details = [e if isinstance(e, str) else e.get("message") or e.get("code") or "" for e in errors]
        details = [d for d in details if d]
        if details:
            message = f"{message}: {'; '.join(details)}"
    return GitHubError(resp.status_code, _kind(resp), message, str(data.get("documentation_url", "")))


def _wait_seconds(resp: httpx.Response, attempt: int) -> float:
    if ra := resp.headers.get("retry-after"):
        try:
            return float(ra)
        except ValueError:
            pass
    if resp.headers.get("x-ratelimit-remaining") == "0" and (reset := resp.headers.get("x-ratelimit-reset")):
        try:
            return max(0.0, float(reset) - time.time()) + 1
        except ValueError:
            pass
    return float(2**attempt)


class GitHubHTTP:
    def __init__(
        self,
        base_url: str,
        *,
        transport: httpx.BaseTransport | None = None,
        max_retries: int = 3,
        sleep: Callable[[float], None] = time.sleep,
        timeout: float = 30,
    ) -> None:
        self.client = httpx.Client(
            base_url=base_url.rstrip("/"),
            transport=transport,
            timeout=timeout,
            headers={
                "Accept": "application/vnd.github+json",
                "X-GitHub-Api-Version": "2022-11-28",
                "User-Agent": "aisdlc-intake-portal",
            },
        )
        self.max_retries = max_retries
        self.sleep = sleep

    def request(
        self,
        method: str,
        path: str,
        token: str | None,
        *,
        json: Any = None,
        params: dict[str, Any] | None = None,
        accept: str | None = None,
        auth_scheme: str = "Bearer",
    ) -> httpx.Response:
        headers = {"Authorization": f"{auth_scheme} {token}"} if token else {}
        if accept:
            headers["Accept"] = accept
        idempotent = method.upper() in ("GET", "HEAD", "PUT", "DELETE")
        attempt = 0
        while True:
            try:
                resp = self.client.request(method, path, json=json, params=params, headers=headers)
            except httpx.TransportError as exc:
                if idempotent and attempt < self.max_retries:
                    attempt += 1
                    self.sleep(float(2**attempt))
                    continue
                raise GitHubError(0, "network", f"Could not reach GitHub ({type(exc).__name__}).") from exc
            if resp.status_code < 400:
                return resp
            err = error_from(resp)
            retryable = err.kind == "rate_limited" or (idempotent and err.kind == "server")
            if retryable and attempt < self.max_retries:
                wait = _wait_seconds(resp, attempt + 1)
                if wait > MAX_WAIT_SECONDS:
                    raise GitHubError(
                        err.status,
                        "rate_limited",
                        f"GitHub rate limit reached; try again in about {int(wait // 60) + 1} minute(s).",
                    )
                attempt += 1
                log.warning("github retry", extra={"fields": {"status": err.status, "attempt": attempt, "path": path}})
                self.sleep(wait)
                continue
            raise err

    def paginate(self, path: str, token: str, params: dict[str, Any] | None = None, limit: int = 1000) -> list[Any]:
        params = dict(params or {})
        params.setdefault("per_page", 100)
        page = 1
        out: list[Any] = []
        while len(out) < limit:
            params["page"] = page
            data = self.request("GET", path, token, params=params).json()
            items = data if isinstance(data, list) else data.get("items") or data.get("workflow_runs") or []
            out += items
            if len(items) < params["per_page"]:
                break
            page += 1
        return out[:limit]
