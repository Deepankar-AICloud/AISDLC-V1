from __future__ import annotations

import json
from datetime import timedelta
from typing import Any

from fastapi import APIRouter, Depends, File, Form, Header, Request, UploadFile
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.orm import Session

from ..container import Container
from ..db import AuditEntry, IntakeRequest, User, utcnow
from ..errors import ApiError
from ..github.identity import get_link
from ..intake.service import IntakeService
from ..review.service import ReviewService
from ..status.sync import assigned_request_ids, sync_request
from .deps import container, db_session, load_request, rate_limit

router = APIRouter(prefix="/api")


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
    from starlette.concurrency import run_in_threadpool

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
    return {"created": created, "request": request_dict(req, detail=True)}


@router.get("/requests")
def list_requests(
    scope: str = "mine",
    user: User = Depends(rate_limit("read")),
    db: Session = Depends(db_session),
    c: Container = Depends(container),
) -> dict[str, Any]:
    if scope == "assigned":
        if c.settings.entra_reviewer_role not in (user.roles or []):
            return {"requests": []}
        link = get_link(db, user)
        if link is None or link.revoked:
            return {"requests": [], "hint": "Connect GitHub to see requests assigned to you."}
        ids = assigned_request_ids(c, db, user)
        rows = db.scalars(
            select(IntakeRequest).where(IntakeRequest.id.in_(list(ids))).order_by(IntakeRequest.created_at.desc())
        ).all()
    else:
        rows = db.scalars(
            select(IntakeRequest)
            .where(IntakeRequest.requester_id == user.id)
            .order_by(IntakeRequest.created_at.desc())
            .limit(200)
        ).all()
    return {"requests": [request_dict(r) for r in rows]}


@router.get("/requests/{request_id}")
def get_request(
    request_id: str,
    user: User = Depends(rate_limit("read")),
    db: Session = Depends(db_session),
    c: Container = Depends(container),
) -> dict[str, Any]:
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
    req = load_request(db, c, user, request_id)
    sync_request(c, db, req)
    return request_dict(req, detail=True)


@router.post("/requests/{request_id}/retry-submit")
def retry_submit(
    request_id: str,
    user: User = Depends(rate_limit("submit")),
    db: Session = Depends(db_session),
    c: Container = Depends(container),
) -> dict[str, Any]:
    req = load_request(db, c, user, request_id)
    if req.requester_id != user.id:
        raise ApiError(403, "not_requester", "Only the requester can retry a submission.")
    if req.status != "submit_failed":
        raise ApiError(409, "not_failed", "This submission is not in a failed state.")
    IntakeService(c).run_submit(db, user, req)
    return request_dict(req, detail=True)


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
    req = load_request(db, c, user, request_id)
    return ReviewService(c).answer(db, user, req, body.answer)


@router.get("/requests/{request_id}/audit")
def audit(
    request_id: str,
    user: User = Depends(rate_limit("read")),
    db: Session = Depends(db_session),
    c: Container = Depends(container),
) -> dict[str, Any]:
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
