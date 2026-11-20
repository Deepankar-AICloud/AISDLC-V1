from __future__ import annotations

import hashlib
import json
import secrets
from datetime import UTC, datetime, timedelta
from typing import Any

from fastapi import APIRouter, Depends, File, Form, Header, Request, UploadFile
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.orm import Session
from starlette.concurrency import run_in_threadpool

from ..container import Container
from ..db import Assignment, AuditEntry, IntakeRequest, RequestAccessGrant, User, utcnow
from ..errors import ApiError, not_found
from ..extract import ExtractionError, Limits, run_extraction, scan_file
from ..github.identity import get_link
from ..intake.service import IntakeService
from ..review.service import ReviewService
from ..status.employee import default_employee_update, employee_progress, employee_status
from ..status.sync import assigned_request_ids, sync_request
from .deps import (
    container,
    db_session,
    load_owned_request,
    load_request,
    rate_limit,
    require_individual_identity,
    require_role,
)

router = APIRouter(prefix="/api")


def _employee_timestamp(value: datetime) -> str:
    if value.tzinfo is None:
        value = value.replace(tzinfo=UTC)
    return value.astimezone(UTC).isoformat().replace("+00:00", "Z")


def _issue_tracking_token(db: Session, request_id: str) -> str:
    token = secrets.token_urlsafe(32)
    grant = db.get(RequestAccessGrant, request_id)
    if grant is None:
        grant = RequestAccessGrant(request_id=request_id, token_hash=hashlib.sha256(token.encode()).hexdigest())
        db.add(grant)
    else:
        grant.token_hash = hashlib.sha256(token.encode()).hexdigest()
        grant.created_at = utcnow()
    db.commit()
    return token


def _load_employee_request(
    db: Session, c: Container, user: User, request_id: str, tracking_token: str
) -> IntakeRequest:
    if c.settings.auth_mode == "open":
        grant = db.get(RequestAccessGrant, request_id)
        expected = hashlib.sha256(tracking_token.encode()).hexdigest() if tracking_token else ""
        if grant is None or not secrets.compare_digest(grant.token_hash, expected):
            raise not_found()
        req = db.get(IntakeRequest, request_id)
        if req is None:
            raise not_found()
        return req
    require_individual_identity(c, user)
    return load_owned_request(db, user, request_id)


def request_dict(req: IntakeRequest, *, detail: bool = False) -> dict[str, Any]:
    snap = req.status_snapshot or {}
    out: dict[str, Any] = {
        "id": req.id,
        "title": req.title,
        "status": req.status,
        "stage": req.stage,
        "issue_number": req.issue_number,
        "issue_url": req.issue_url,
        "repository": req.repository,
        "created_at": req.created_at.isoformat() + "Z",
        "updated_at": req.updated_at.isoformat() + "Z",
        "open_stage_pr": snap.get("open_stage_pr"),
    }
    if detail:
        out.update(
            {
                "snapshot": snap,
                "error": req.error,
                "files": req.files_meta,
                "overflow_branch": req.overflow_branch,
                "overflow_parts": {"total": req.overflow_parts_total, "posted": req.overflow_parts_posted},
                "submit_step": req.submit_step,
                "last_synced_at": req.last_synced_at.isoformat() + "Z" if req.last_synced_at else None,
            }
        )
    return out


def employee_request_dict(req: IntakeRequest, db: Session, user: User, *, detail: bool = False) -> dict[str, Any]:
    snap = req.status_snapshot or {}
    status = employee_status(req.status, snap)
    assignments = list(db.scalars(select(Assignment).where(Assignment.request_id == req.id)))
    reviewers = [
        a.github_login
        for a in assignments
        if a.github_login and not (a.github_login.startswith("@") and "/" in a.github_login)
    ]
    assigned_reviewer = reviewers[0] if reviewers else ("IT review team" if assignments else None)

    update = snap.get("latest_human_update") or {}
    update_login = str(update.get("login") or "").lower()
    assignment_logins = {a.github_login.lower() for a in assignments}
    requester_link = get_link(db, user)
    is_requester_update = bool(requester_link and update_login == requester_link.github_login.lower())
    is_reviewer_update = bool(update_login and update_login in assignment_logins)
    if update.get("body") and (is_requester_update or is_reviewer_update):
        latest_update = {
            "from": "You" if is_requester_update else str(update.get("author") or assigned_reviewer or "IT team"),
            "message": str(update["body"]),
            "updated_at": str(update.get("created_at") or _employee_timestamp(req.updated_at)),
        }
    else:
        latest_update = {
            "from": "IT team",
            "message": default_employee_update(status),
            "updated_at": _employee_timestamp(req.updated_at),
        }

    action_required = status == "more_information_required"
    result: dict[str, Any] = {
        "id": req.id,
        "title": req.title,
        "status": status,
        "submitted_at": _employee_timestamp(req.created_at),
        "last_updated_at": latest_update["updated_at"],
        "latest_update": latest_update,
        "progress": employee_progress(status),
        "action_required": {
            "required": action_required,
            "questions": list(snap.get("questions") or []) if action_required else [],
        },
        "assigned_reviewer": assigned_reviewer,
        "expected_completion_at": None,
        "can_retry_submission": req.status == "submit_failed",
    }
    if detail:
        employee_details = snap.get("employee_details") or {}
        result.update(
            {
                "problem": str(employee_details.get("problem") or ""),
                "objective": str(employee_details.get("objective") or ""),
            }
        )
    return result


def _validate_supporting_file(name: str, data: bytes, c: Container, limits: Limits) -> None:
    scan_file(c.settings.malware_scan_hook, name, data)
    run_extraction(
        name,
        data,
        limits,
        isolation=c.settings.extraction_isolation,
        timeout=c.settings.extraction_timeout_seconds,
        memory_mb=c.settings.extraction_memory_mb,
    )


async def _read_supporting_files(files: list[UploadFile], c: Container) -> list[tuple[str, bytes]]:
    if len(files) > c.settings.max_files:
        raise ApiError(422, "too_many_files", f"Upload at most {c.settings.max_files} files at a time.")
    limits = Limits.from_settings(c.settings)
    uploads: list[tuple[str, bytes]] = []
    total = 0
    for uploaded in files:
        name = (uploaded.filename or "file")[:200]
        try:
            data = await uploaded.read(c.settings.max_file_bytes + 1)
            if len(data) > c.settings.max_file_bytes:
                raise ApiError(413, "file_too_large", f"{name} exceeds the per-file size limit.")
            total += len(data)
            if total > c.settings.max_total_bytes:
                raise ApiError(413, "total_too_large", "The supporting files exceed the total upload limit.")
            await run_in_threadpool(_validate_supporting_file, name, data, c, limits)
        except ExtractionError as exc:
            raise ApiError(422, exc.code, exc.message) from exc
        finally:
            await uploaded.close()
        uploads.append((name, data))
    return uploads


@router.post("/intake/preview")
async def preview(
    request: Request,
    fields: str = Form("{}"),
    pasted_text: str = Form(""),
    files: list[UploadFile] = File(default_factory=list),
    user: User = Depends(rate_limit("submit")),
    db: Session = Depends(db_session),
    c: Container = Depends(container),
) -> dict[str, Any]:
    try:
        fields_data = json.loads(fields or "{}")
        assert isinstance(fields_data, dict)
    except (ValueError, AssertionError) as exc:
        raise ApiError(422, "invalid_fields", "Form fields could not be read.") from exc
    uploads: list[tuple[str, bytes]] = []
    for f in files:
        data = await f.read(c.settings.max_file_bytes + 1)
        uploads.append((f.filename or "file", data))
        await f.close()
    return await run_in_threadpool(IntakeService(c).preview, db, user, fields_data, pasted_text, uploads)


class SubmitBody(BaseModel):
    draft_id: str
    fields: dict[str, str] | None = None
    pasted_text: str | None = None
    files: list[dict[str, Any]] = []


@router.post("/requests")
def submit(
    body: SubmitBody,
    idempotency_key: str = Header("", alias="Idempotency-Key"),
    user: User = Depends(rate_limit("submit")),
    db: Session = Depends(db_session),
    c: Container = Depends(container),
) -> dict[str, Any]:
    if c.settings.entra_requester_role not in (user.roles or []):
        raise ApiError(403, "requester_role_required", "Submitting needs the Requester role in the portal.")
    req, created = IntakeService(c).submit(db, user, body.model_dump(), idempotency_key)
    response: dict[str, Any] = {"created": created, "request": employee_request_dict(req, db, user, detail=True)}
    if c.settings.auth_mode == "open":
        response["tracking_token"] = _issue_tracking_token(db, req.id)
    return response


@router.get("/employee/requests")
def employee_requests(
    user: User = Depends(rate_limit("read")),
    db: Session = Depends(db_session),
    c: Container = Depends(container),
) -> dict[str, Any]:
    require_role(user, c.settings.entra_requester_role)
    require_individual_identity(c, user)
    rows = db.scalars(
        select(IntakeRequest)
        .where(IntakeRequest.requester_id == user.id)
        .order_by(IntakeRequest.created_at.desc())
        .limit(200)
    ).all()
    return {"requests": [employee_request_dict(row, db, user) for row in rows]}


@router.get("/employee/requests/{request_id}")
def employee_request(
    request_id: str,
    tracking_token: str = Header("", alias="X-Request-Access"),
    user: User = Depends(rate_limit("read")),
    db: Session = Depends(db_session),
    c: Container = Depends(container),
) -> dict[str, Any]:
    require_role(user, c.settings.entra_requester_role)
    req = _load_employee_request(db, c, user, request_id, tracking_token)
    if req.issue_number and (req.last_synced_at is None or req.last_synced_at < utcnow() - timedelta(seconds=30)):
        sync_request(c, db, req)
    return employee_request_dict(req, db, user, detail=True)


@router.post("/employee/requests/{request_id}/information")
async def employee_information(
    request_id: str,
    tracking_token: str = Header("", alias="X-Request-Access"),
    answer: str = Form(""),
    files: list[UploadFile] = File(default_factory=list),
    user: User = Depends(rate_limit("action")),
    db: Session = Depends(db_session),
    c: Container = Depends(container),
) -> dict[str, bool]:
    require_role(user, c.settings.entra_requester_role)
    req = _load_employee_request(db, c, user, request_id, tracking_token)
    uploads = await _read_supporting_files(files, c)
    ReviewService(c).answer(db, user, req, answer, uploads)
    return {"submitted": True}


@router.get("/requests")
def list_requests(
    scope: str = "mine",
    user: User = Depends(rate_limit("read")),
    db: Session = Depends(db_session),
    c: Container = Depends(container),
) -> dict[str, Any]:
    require_role(user, c.settings.entra_reviewer_role)
    if scope == "assigned":
        link = get_link(db, user)
        if link is None or link.revoked:
            return {"requests": [], "hint": "Connect GitHub to see requests assigned to you."}
        ids = assigned_request_ids(c, db, user)
        rows = db.scalars(
            select(IntakeRequest).where(IntakeRequest.id.in_(list(ids))).order_by(IntakeRequest.created_at.desc())
        ).all()
    elif scope == "mine":
        rows = db.scalars(
            select(IntakeRequest)
            .where(IntakeRequest.requester_id == user.id)
            .order_by(IntakeRequest.created_at.desc())
            .limit(200)
        ).all()
    else:
        raise ApiError(422, "invalid_scope", "Request scope must be 'mine' or 'assigned'.")
    return {"requests": [request_dict(r) for r in rows]}


@router.get("/requests/{request_id}")
def get_request(
    request_id: str,
    user: User = Depends(rate_limit("read")),
    db: Session = Depends(db_session),
    c: Container = Depends(container),
) -> dict[str, Any]:
    require_role(user, c.settings.entra_reviewer_role)
    req = load_request(db, c, user, request_id)
    if req.issue_number and (req.last_synced_at is None or req.last_synced_at < utcnow() - timedelta(seconds=30)):
        sync_request(c, db, req)
    out = request_dict(req, detail=True)
    out["is_requester"] = req.requester_id == user.id
    return out


@router.post("/requests/{request_id}/refresh")
def refresh(
    request_id: str,
    user: User = Depends(rate_limit("action")),
    db: Session = Depends(db_session),
    c: Container = Depends(container),
) -> dict[str, Any]:
    require_role(user, c.settings.entra_reviewer_role)
    req = load_request(db, c, user, request_id)
    sync_request(c, db, req)
    return request_dict(req, detail=True)


@router.post("/requests/{request_id}/retry-submit")
def retry_submit(
    request_id: str,
    tracking_token: str = Header("", alias="X-Request-Access"),
    user: User = Depends(rate_limit("submit")),
    db: Session = Depends(db_session),
    c: Container = Depends(container),
) -> dict[str, Any]:
    require_role(user, c.settings.entra_requester_role)
    req = _load_employee_request(db, c, user, request_id, tracking_token)
    if req.status != "submit_failed":
        raise ApiError(409, "not_failed", "This submission is not in a failed state.")
    IntakeService(c).run_submit(db, user, req)
    return employee_request_dict(req, db, user, detail=True)


class AnswerBody(BaseModel):
    answer: str


@router.post("/requests/{request_id}/answer")
def answer(
    request_id: str,
    body: AnswerBody,
    user: User = Depends(rate_limit("action")),
    db: Session = Depends(db_session),
    c: Container = Depends(container),
) -> dict[str, Any]:
    require_role(user, c.settings.entra_reviewer_role)
    req = load_request(db, c, user, request_id)
    return ReviewService(c).answer(db, user, req, body.answer)


@router.get("/requests/{request_id}/audit")
def audit(
    request_id: str,
    user: User = Depends(rate_limit("read")),
    db: Session = Depends(db_session),
    c: Container = Depends(container),
) -> dict[str, Any]:
    require_role(user, c.settings.entra_reviewer_role)
    req = load_request(db, c, user, request_id)
    rows = db.scalars(
        select(AuditEntry).where(AuditEntry.portal_request_id == req.id).order_by(AuditEntry.ts.desc()).limit(200)
    ).all()
    return {
        "entries": [
            {
                "ts": r.ts.isoformat() + "Z",
                "github_login": r.github_login,
                "identity": r.identity,
                "action": r.action,
                "target": r.target_ref,
                "outcome": r.outcome,
                "github_status": r.github_status,
            }
            for r in rows
        ]
    }
