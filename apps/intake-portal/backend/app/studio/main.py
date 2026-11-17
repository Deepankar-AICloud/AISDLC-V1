"""AISDLC Studio web app: shared sign-in, requirement upload and stage-by-stage generation.

Run locally:
    STUDIO_PASSWORD=... python -m uvicorn app.studio.main:create_studio_app --factory --port 8001
"""

import hmac
import logging
import re
import secrets
import uuid
from collections.abc import Awaitable, Callable
from pathlib import Path
from typing import Annotated, Any

from fastapi import APIRouter, Depends, FastAPI, File, Form, Request, UploadFile
from fastapi.exceptions import RequestValidationError
from fastapi.responses import FileResponse, JSONResponse, Response
from itsdangerous import BadSignature, URLSafeTimedSerializer
from pydantic import BaseModel, Field

from ..extract import ExtractionError, Limits, allowed_extensions, run_extraction, scan_file
from ..logging_setup import configure_logging, correlation_id, log_event
from ..main import BodyLimitMiddleware
from ..security import RateLimiter
from .jobs import STAGES, Job, JobError, JobStore, Runner
from .settings import StudioSettings

log = logging.getLogger("studio")
STATIC_DIR = Path(__file__).parent / "static"
COOKIE = "aisdlc_studio"
CSRF_HEADER = "x-csrf-token"
CSP = (
    "default-src 'self'; script-src 'self'; style-src 'self'; img-src 'self' data:; connect-src 'self'; "
    "object-src 'none'; base-uri 'none'; frame-ancestors 'none'; form-action 'self'"
)
_MODEL_NAME = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._:\-]{0,63}$")


class StudioError(Exception):
    def __init__(self, status: int, code: str, message: str) -> None:
        super().__init__(message)
        self.status, self.code, self.message = status, code, message


class LoginBody(BaseModel):
    username: str = Field(max_length=200)
    password: str = Field(max_length=500)


class ModelBody(BaseModel):
    model: str | None = Field(default=None, max_length=64)
    reason: str | None = Field(default=None, max_length=500)


class TextBody(BaseModel):
    text: str = Field(min_length=1, max_length=20_000)


def _error(code: str, message: str, status: int) -> JSONResponse:
    return JSONResponse(
        {"error": {"code": code, "message": message, "correlation_id": correlation_id.get()}}, status_code=status
    )


class Sessions:
    """Signed HttpOnly cookie carrying only a session marker and CSRF token."""

    def __init__(self, secret: str, max_age: int, secure: bool) -> None:
        self.ser = URLSafeTimedSerializer(secret, salt="aisdlc-studio-session")
        self.max_age, self.secure = max_age, secure

    def issue(self, response: Response, username: str) -> str:
        csrf = secrets.token_urlsafe(32)
        value = self.ser.dumps({"u": username, "csrf": csrf})
        response.set_cookie(
            COOKIE, value, max_age=self.max_age, httponly=True, secure=self.secure, samesite="strict", path="/"
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
        return data if isinstance(data, dict) and "u" in data else None

    def clear(self, response: Response) -> None:
        response.delete_cookie(COOKIE, path="/")


def _client_ip(request: Request) -> str:
    return request.client.host if request.client else "unknown"


def _job_view(store: JobStore, job: Job) -> dict[str, Any]:
    return {
        "id": job.id,
        "number": job.number,
        "title": job.title,
        "status": job.status,
        "busy": job.busy,
        "stage": job.stage,
        "message": job.message,
        "approved": job.approved,
        "questions": job.questions,
        "result": job.result,
        "sources": job.sources,
        "events": job.events[-30:],
        "available": store.available_stages(job),
        "created_at": job.created_at,
        "updated_at": job.updated_at,
    }


def create_studio_app(settings: StudioSettings | None = None) -> FastAPI:
    settings = settings or StudioSettings()
    configure_logging(settings.log_level)
    if settings.weak_password:
        log.warning(
            "STUDIO_PASSWORD is weak. Anyone who can reach this Studio can sign in and use your Copilot quota; "
            "use a strong password and restrict network access before exposing it beyond your machine."
        )
    store = JobStore(settings)
    runner = Runner(store, settings)
    secret = settings.session_secret.get_secret_value() or secrets.token_urlsafe(48)
    sessions = Sessions(secret, settings.session_max_age_seconds, settings.secure_cookies)
    limiter = RateLimiter()
    limits = Limits(max_file_bytes=settings.max_file_bytes, max_extracted_chars=settings.max_requirement_chars)

    app = FastAPI(title="AISDLC Studio", version="0.1.0", docs_url=None, redoc_url=None, openapi_url=None)
    app.state.settings, app.state.store, app.state.runner = settings, store, runner

    @app.middleware("http")
    async def headers(request: Request, call_next: Callable[[Request], Awaitable[Response]]) -> Response:
        token = correlation_id.set(uuid.uuid4().hex)
        try:
            response = await call_next(request)
            if request.url.path.startswith("/api/"):
                log_event(log, "request", method=request.method, path=request.url.path, status=response.status_code)
        finally:
            correlation_id.reset(token)
        response.headers["Content-Security-Policy"] = CSP
        response.headers["X-Content-Type-Options"] = "nosniff"
        response.headers["Referrer-Policy"] = "no-referrer"
        response.headers["X-Frame-Options"] = "DENY"
        response.headers["Cross-Origin-Opener-Policy"] = "same-origin"
        if settings.secure_cookies:
            response.headers["Strict-Transport-Security"] = "max-age=31536000; includeSubDomains"
        if request.url.path.startswith("/api/"):
            response.headers["Cache-Control"] = "no-store"
        return response

    app.add_middleware(BodyLimitMiddleware, max_bytes=settings.max_request_bytes)

    @app.exception_handler(StudioError)
    async def studio_error(_: Request, exc: StudioError) -> JSONResponse:
        return _error(exc.code, exc.message, exc.status)

    @app.exception_handler(JobError)
    async def job_error(_: Request, exc: JobError) -> JSONResponse:
        return _error(exc.code, exc.message, exc.status)

    @app.exception_handler(RequestValidationError)
    async def validation_error(_: Request, exc: RequestValidationError) -> JSONResponse:
        return _error("invalid_request", "Some fields are missing or invalid.", 422)

    @app.exception_handler(Exception)
    async def unhandled(_: Request, exc: Exception) -> JSONResponse:
        log.exception("unhandled error")
        return _error("internal_error", "Something went wrong. Quote the reference when reporting it.", 500)

    # -- auth dependencies ---------------------------------------------------
    def session(request: Request) -> dict[str, Any]:
        data = sessions.read(request)
        if data is None:
            raise StudioError(401, "unauthenticated", "Please sign in.")
        return data

    def mutating(request: Request, sess: Annotated[dict[str, Any], Depends(session)]) -> dict[str, Any]:
        header = request.headers.get(CSRF_HEADER) or ""
        if not header or not hmac.compare_digest(str(sess.get("csrf", "")), header):
            raise StudioError(403, "csrf_failed", "Your session expired. Reload the page and sign in again.")
        if not limiter.allow(_client_ip(request), "actions", settings.rate_limit_actions_per_min):
            raise StudioError(429, "rate_limited", "Too many actions. Wait a minute and try again.")
        return sess

    Session = Annotated[dict[str, Any], Depends(session)]
    Mutating = Annotated[dict[str, Any], Depends(mutating)]
    api = APIRouter(prefix="/api")

    @app.get("/healthz")
    def healthz() -> dict[str, str]:
        return {"status": "ok"}

    @api.post("/login")
    def login(body: LoginBody, request: Request, response: Response) -> dict[str, Any]:
        if not limiter.allow(_client_ip(request), "login", settings.rate_limit_login_per_min):
            raise StudioError(429, "rate_limited", "Too many sign-in attempts. Wait a minute and try again.")
        user_ok = hmac.compare_digest(body.username.encode(), settings.studio_username.encode())
        pass_ok = hmac.compare_digest(body.password.encode(), settings.studio_password.get_secret_value().encode())
        if not (user_ok and pass_ok):
            log_event(log, "login_failed", ip=_client_ip(request))
            raise StudioError(401, "invalid_credentials", "Incorrect username or password.")
        csrf = sessions.issue(response, settings.studio_username)
        log_event(log, "login", ip=_client_ip(request))
        return {"username": settings.studio_username, "csrf_token": csrf}

    @api.post("/logout")
    def logout(response: Response) -> dict[str, bool]:
        sessions.clear(response)
        return {"ok": True}

    @api.get("/session")
    def current(sess: Session) -> dict[str, Any]:
        return {
            "username": sess["u"],
            "csrf_token": sess["csrf"],
            "stages": [{"key": k, "label": v} for k, v in STAGES if k != "code" or settings.enable_code_stage],
            "accept": allowed_extensions(False),
            "max_file_mb": settings.max_file_bytes // (1024 * 1024),
            "mode": "ai" if settings.use_llm else "dry-run",
        }

    @api.get("/jobs")
    def list_jobs(_: Session) -> list[dict[str, Any]]:
        return [
            {
                "id": j.id,
                "number": j.number,
                "title": j.title,
                "status": j.status,
                "stage": j.stage,
                "busy": j.busy,
                "updated_at": j.updated_at,
            }
            for j in store.all()
        ]

    @api.post("/jobs")
    def create_job(
        request: Request,
        _: Mutating,
        title: Annotated[str, Form(max_length=200)] = "",
        text: Annotated[str, Form(max_length=200_000)] = "",
        files: Annotated[list[UploadFile] | None, File()] = None,
    ) -> dict[str, Any]:
        if not limiter.allow(_client_ip(request), "create", settings.rate_limit_create_per_min):
            raise StudioError(429, "rate_limited", "Too many new requests. Wait a minute and try again.")
        uploads = [f for f in files or [] if f.filename]
        if len(uploads) > settings.max_files:
            raise StudioError(400, "too_many_files", f"Upload at most {settings.max_files} files.")
        parts: list[str] = [text.strip()] if text.strip() else []
        sources: list[dict[str, Any]] = []
        for up in uploads:
            name = Path(up.filename or "upload").name
            data = up.file.read(settings.max_file_bytes + 1)
            if len(data) > settings.max_file_bytes:
                raise StudioError(400, "too_large", f"{name} is larger than {settings.max_file_bytes // 2**20} MB.")
            try:
                scan_file(settings.malware_scan_hook, name, data)
                res = run_extraction(
                    name,
                    data,
                    limits,
                    isolation=settings.extraction_isolation,
                    timeout=settings.extraction_timeout_seconds,
                )
            except ExtractionError as exc:
                raise StudioError(400, exc.code, exc.message) from exc
            if res.text.strip():
                parts.append(f"=== Document: {name} ===\n{res.text.strip()}")
            sources.append(
                {
                    "filename": name,
                    "kind": res.kind,
                    "chars": res.chars,
                    "warnings": res.warnings[:5],
                    "injection_flags": len(res.injection_flags),
                }
            )
        requirement = "\n\n".join(parts)
        if len(requirement.strip()) < 30:
            raise StudioError(400, "too_short", "Describe the requirement (at least a few sentences) or upload a file.")
        if len(requirement) > settings.max_requirement_chars:
            raise StudioError(400, "too_long", "The requirement is too long. Shorten it or upload fewer files.")
        clean_title = " ".join(title.split())[:200] or requirement.strip().splitlines()[0][:80]
        job = store.create(clean_title, requirement, sources)
        runner.submit(job.id, "start")
        return _job_view(store, store.get(job.id))

    @api.get("/jobs/{job_id}")
    def get_job(job_id: str, _: Session) -> dict[str, Any]:
        return _job_view(store, store.get(job_id))

    @api.get("/jobs/{job_id}/artifacts/{stage}")
    def get_artifact(job_id: str, stage: str, _: Session) -> dict[str, str]:
        return {"stage": stage, "markdown": store.artifact_text(store.get(job_id), stage)}

    @api.get("/jobs/{job_id}/download")
    def download(job_id: str, _: Session) -> Response:
        job = store.get(job_id)
        if job.busy:
            raise StudioError(409, "busy", "Wait for the current step to finish before downloading.")
        return Response(
            store.bundle(job),
            media_type="application/zip",
            headers={"Content-Disposition": f'attachment; filename="aisdlc-{job.number}.zip"'},
        )

    @api.post("/jobs/{job_id}/model")
    def confirm_model(job_id: str, body: ModelBody, _: Mutating) -> dict[str, Any]:
        model = (body.model or "").strip() or None
        if model and not _MODEL_NAME.match(model):
            raise StudioError(400, "invalid_model", "That model name is not valid.")
        reason = " ".join((body.reason or "").split()) or ("Selected in AISDLC Studio" if model else None)
        return _job_view(store, runner.submit(job_id, "confirm_model", model=model, reason=reason))

    @api.post("/jobs/{job_id}/answer")
    def answer(job_id: str, body: TextBody, _: Mutating) -> dict[str, Any]:
        return _job_view(store, runner.submit(job_id, "answer", text=body.text.strip()))

    @api.post("/jobs/{job_id}/approve")
    def approve(job_id: str, _: Mutating) -> dict[str, Any]:
        return _job_view(store, runner.submit(job_id, "approve"))

    @api.post("/jobs/{job_id}/revise")
    def revise(job_id: str, body: TextBody, _: Mutating) -> dict[str, Any]:
        return _job_view(store, runner.submit(job_id, "revise", notes=body.text.strip()))

    @api.post("/jobs/{job_id}/retry")
    def retry(job_id: str, _: Mutating) -> dict[str, Any]:
        return _job_view(store, runner.submit(job_id, "retry"))

    @api.delete("/jobs/{job_id}")
    def delete(job_id: str, _: Mutating) -> dict[str, bool]:
        store.delete(job_id)
        return {"ok": True}

    app.include_router(api)

    @app.get("/{path:path}", include_in_schema=False)
    def static(path: str) -> Response:
        if path.startswith("api/"):
            return _error("not_found", "Not found.", 404)
        root = STATIC_DIR.resolve()
        candidate = (root / path).resolve()
        if path and candidate.is_file() and candidate.is_relative_to(root):
            return FileResponse(candidate, headers={"Cache-Control": "no-cache"})
        return FileResponse(root / "index.html", headers={"Cache-Control": "no-store"})

    log_event(log, "studio_started", env=settings.app_env, llm=settings.use_llm, code_stage=settings.enable_code_stage)
    return app
