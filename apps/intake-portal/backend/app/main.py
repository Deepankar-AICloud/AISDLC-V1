"""AISDLC Portal API (FastAPI)."""

from __future__ import annotations

import logging
import re
import uuid
from collections.abc import AsyncIterator, Awaitable, Callable
from contextlib import asynccontextmanager
from pathlib import Path
from typing import Any

from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, JSONResponse, Response
from sqlalchemy import text
from starlette.types import ASGIApp, Message, Receive, Scope, Send

from .api import auth_routes, dev_routes, intake_routes, review_routes, webhooks
from .auth.entra import EntraClient
from .auth.session import SessionManager
from .config import Settings, get_settings
from .container import Container
from .errors import ApiError
from .github.fake import FakeGitHub
from .github.http import GitHubError, IdentityViolation
from .logging_setup import configure_logging, correlation_id, log_event

log = logging.getLogger("portal")
CSP = (
    "default-src 'self'; script-src 'self'; style-src 'self' 'unsafe-inline'; img-src 'self' data: "
    "https://avatars.githubusercontent.com; connect-src 'self'; font-src 'self' data:; object-src 'none'; "
    "base-uri 'none'; frame-ancestors 'none'; form-action 'self' https://login.microsoftonline.com "
    "https://github.com"
)


class BodyLimitMiddleware:
    """Rejects request bodies over MAX_REQUEST_BYTES, including chunked uploads without Content-Length."""

    def __init__(self, app: ASGIApp, max_bytes: int) -> None:
        self.app = app
        self.max_bytes = max_bytes

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        if scope["type"] != "http":
            await self.app(scope, receive, send)
            return
        declared = dict(scope.get("headers") or []).get(b"content-length")
        if declared and declared.isdigit() and int(declared) > self.max_bytes:
            await self._reject(send)
            return
        seen = 0

        async def limited() -> Message:
            nonlocal seen
            msg = await receive()
            if msg["type"] == "http.request":
                seen += len(msg.get("body", b""))
                if seen > self.max_bytes:
                    raise _TooLarge()
            return msg

        try:
            await self.app(scope, limited, send)
        except _TooLarge:
            await self._reject(send)

    @staticmethod
    async def _reject(send: Send) -> None:
        await send({"type": "http.response.start", "status": 413, "headers": [(b"content-type", b"application/json")]})
        await send(
            {
                "type": "http.response.body",
                "body": b'{"error":{"code":"request_too_large","message":"The upload is too large."}}',
            }
        )


class _TooLarge(Exception):
    pass


def error_body(code: str, message: str, **extra: Any) -> dict[str, Any]:
    return {"error": {"code": code, "message": message, "correlation_id": correlation_id.get(), **extra}}


def create_app(settings: Settings | None = None, fake: FakeGitHub | None = None) -> FastAPI:
    settings = settings or get_settings()
    configure_logging(settings.log_level)
    container = Container(settings, fake=fake)

    @asynccontextmanager
    async def lifespan(app: FastAPI) -> AsyncIterator[None]:
        from .status.sync import Poller

        poller = Poller(container)
        if settings.poller_enabled:
            poller.start()
        app.state.poller = poller
        yield
        poller.stop()

    app = FastAPI(
        title="AISDLC Portal",
        version="0.1.0",
        lifespan=lifespan,
        docs_url="/api/docs" if settings.is_dev else None,
        redoc_url=None,
        openapi_url="/api/openapi.json" if settings.is_dev else None,
    )
    app.state.container = container
    secret = settings.session_secret.get_secret_value() or ("dev-only-session-secret-" + "x" * 16)
    app.state.sessions = SessionManager(secret, settings.session_max_age_seconds, settings.secure_cookies)
    app.state.entra = (
        EntraClient(
            settings.entra_tenant_id,
            settings.entra_client_id,
            settings.entra_client_secret.get_secret_value(),
            settings.public_base_url.rstrip("/") + "/auth/callback",
        )
        if settings.auth_mode == "entra" and settings.entra_tenant_id
        else None
    )

    if settings.cors_origins:
        app.add_middleware(
            CORSMiddleware,
            allow_origins=settings.cors_origins,
            allow_credentials=True,
            allow_methods=["GET", "POST", "DELETE"],
            allow_headers=["content-type", "x-csrf-token", "idempotency-key", "x-request-id"],
        )

    @app.middleware("http")
    async def context_and_headers(request: Request, call_next: Callable[[Request], Awaitable[Response]]) -> Response:
        incoming = request.headers.get("x-request-id", "")
        cid = incoming if re.fullmatch(r"[A-Za-z0-9\-]{8,64}", incoming) else uuid.uuid4().hex
        token = correlation_id.set(cid)
        try:
            response = await call_next(request)
            if not request.url.path.startswith("/healthz"):
                log_event(log, "request", method=request.method, path=request.url.path, status=response.status_code)
        finally:
            correlation_id.reset(token)
        response.headers["X-Request-ID"] = cid
        response.headers["Content-Security-Policy"] = CSP
        response.headers["X-Content-Type-Options"] = "nosniff"
        response.headers["Referrer-Policy"] = "no-referrer"
        response.headers["X-Frame-Options"] = "DENY"
        response.headers["Permissions-Policy"] = "camera=(), microphone=(), geolocation=()"
        response.headers["Cross-Origin-Opener-Policy"] = "same-origin"
        if settings.secure_cookies:
            response.headers["Strict-Transport-Security"] = "max-age=31536000; includeSubDomains"
        if request.url.path.startswith(("/api/", "/auth/")):
            response.headers["Cache-Control"] = "no-store"
        return response

    app.add_middleware(BodyLimitMiddleware, max_bytes=settings.max_request_bytes)

    @app.exception_handler(ApiError)
    async def api_error(_: Request, exc: ApiError) -> JSONResponse:
        return JSONResponse(error_body(exc.code, exc.message, **exc.details), status_code=exc.status)

    @app.exception_handler(GitHubError)
    async def gh_error(_: Request, exc: GitHubError) -> JSONResponse:
        status = 429 if exc.kind == "rate_limited" else 502
        return JSONResponse(
            error_body("github_error", f"GitHub returned an error: {exc.message}", github_status=exc.status),
            status_code=status,
        )

    @app.exception_handler(IdentityViolation)
    async def identity_error(_: Request, exc: IdentityViolation) -> JSONResponse:
        log.error("identity violation blocked", extra={"fields": {"detail": str(exc)}})
        return JSONResponse(
            error_body("identity_violation", "This action was blocked by the identity policy."), status_code=403
        )

    @app.exception_handler(RequestValidationError)
    async def validation_error(_: Request, exc: RequestValidationError) -> JSONResponse:
        fields = [".".join(str(p) for p in e.get("loc", [])[1:]) for e in exc.errors()]
        return JSONResponse(
            error_body("invalid_request", "Some fields are missing or invalid.", fields=fields), status_code=422
        )

    @app.exception_handler(Exception)
    async def unhandled(_: Request, exc: Exception) -> JSONResponse:
        log.exception("unhandled error")
        return JSONResponse(
            error_body("internal_error", "Something went wrong. Quote the reference when reporting it."),
            status_code=500,
        )

    @app.get("/healthz")
    def healthz() -> dict[str, Any]:
        with container.db.sessionmaker() as db:
            db.execute(text("SELECT 1"))
        return {"status": "ok", "env": settings.app_env, "github_mode": settings.github_mode}

    app.include_router(auth_routes.router)
    if settings.auth_mode == "dev":
        app.include_router(auth_routes.dev_auth_router())
    app.include_router(intake_routes.router)
    app.include_router(review_routes.router)
    app.include_router(webhooks.router)
    if settings.github_mode == "fake":
        app.include_router(dev_routes.router)

    static_dir = settings.serve_frontend_dir
    if static_dir and Path(static_dir).is_dir():
        root = Path(static_dir).resolve()

        @app.get("/{path:path}", include_in_schema=False)
        def spa(path: str) -> Response:
            if path.startswith(("api/", "auth/", "webhooks/", "dev/")):
                return JSONResponse(error_body("not_found", "Not found."), status_code=404)
            candidate = (root / path).resolve()
            if path and candidate.is_file() and candidate.is_relative_to(root):
                return FileResponse(candidate)
            return FileResponse(root / "index.html", headers={"Cache-Control": "no-store"})

    return app
