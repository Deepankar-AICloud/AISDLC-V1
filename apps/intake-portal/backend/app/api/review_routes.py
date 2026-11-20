from __future__ import annotations

from typing import Any

from fastapi import APIRouter, Depends
from pydantic import BaseModel
from sqlalchemy.orm import Session

from ..container import Container
from ..db import User
from ..errors import ApiError
from ..github.commands import AgentCommand, ModelCommand
from ..review.production import ProductionService
from ..review.service import ReviewService
from .deps import container, db_session, load_request, rate_limit, require_role

router = APIRouter(prefix="/api")


@router.get("/requests/{request_id}/stages/{pr_number}")
def stage(
    request_id: str,
    pr_number: int,
    user: User = Depends(rate_limit("read")),
    db: Session = Depends(db_session),
    c: Container = Depends(container),
) -> dict[str, Any]:
    require_role(user, c.settings.entra_reviewer_role)
    req = load_request(db, c, user, request_id)
    return ReviewService(c).stage_view(db, user, req, pr_number)


class ApproveBody(BaseModel):
    head_sha: str
    confirmed: bool = False


@router.post("/requests/{request_id}/stages/{pr_number}/approve")
def approve(
    request_id: str,
    pr_number: int,
    body: ApproveBody,
    user: User = Depends(rate_limit("action")),
    db: Session = Depends(db_session),
    c: Container = Depends(container),
) -> dict[str, Any]:
    req = load_request(db, c, user, request_id)
    return ReviewService(c).approve(db, user, req, pr_number, body.head_sha, body.confirmed)


class NotesBody(BaseModel):
    notes: str


@router.post("/requests/{request_id}/stages/{pr_number}/request-changes")
def request_changes(
    request_id: str,
    pr_number: int,
    body: NotesBody,
    user: User = Depends(rate_limit("action")),
    db: Session = Depends(db_session),
    c: Container = Depends(container),
) -> dict[str, Any]:
    req = load_request(db, c, user, request_id)
    return ReviewService(c).request_changes(db, user, req, pr_number, body.notes)


class CommandBody(BaseModel):
    command: str
    notes: str = ""
    pr_number: int | None = None


@router.post("/requests/{request_id}/commands")
def command(
    request_id: str,
    body: CommandBody,
    user: User = Depends(rate_limit("action")),
    db: Session = Depends(db_session),
    c: Container = Depends(container),
) -> dict[str, Any]:
    req = load_request(db, c, user, request_id)
    return ReviewService(c).agent_command(db, user, req, body.command, body.notes, body.pr_number)


class ModelBody(BaseModel):
    command: str
    model: str = ""
    reason: str = ""


@router.post("/requests/{request_id}/model")
def model(
    request_id: str,
    body: ModelBody,
    user: User = Depends(rate_limit("action")),
    db: Session = Depends(db_session),
    c: Container = Depends(container),
) -> dict[str, Any]:
    req = load_request(db, c, user, request_id)
    return ReviewService(c).model_command(db, user, req, body.command, body.model, body.reason)


@router.get("/commands")
def allowed_commands(user: User = Depends(rate_limit("read")), c: Container = Depends(container)) -> dict[str, Any]:
    require_role(user, c.settings.entra_reviewer_role)
    return {
        "agent": [x.value for x in AgentCommand],
        "model": [x.value for x in ModelCommand],
        "models": c.allowed_models(),
    }


@router.get("/production")
def production(
    user: User = Depends(rate_limit("read")), db: Session = Depends(db_session), c: Container = Depends(container)
) -> dict[str, Any]:
    if c.settings.entra_reviewer_role not in (user.roles or []):
        raise ApiError(403, "reviewer_role_required", "Production approvals need the Reviewer role.")
    return ProductionService(c).list_pending(db, user)


class ProductionApproveBody(BaseModel):
    confirmation: str
    comment: str = ""


@router.post("/production/{run_id}/approve")
def production_approve(
    run_id: int,
    body: ProductionApproveBody,
    user: User = Depends(rate_limit("action")),
    db: Session = Depends(db_session),
    c: Container = Depends(container),
) -> dict[str, Any]:
    return ProductionService(c).approve(db, user, run_id, body.confirmation, body.comment)
