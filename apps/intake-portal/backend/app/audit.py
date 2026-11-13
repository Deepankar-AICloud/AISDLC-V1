"""Audit log for every GitHub write: who, what, target, when, GitHub status, portal request id.

Token values are never written; `detail` passes through the log redactor as a backstop.
"""

from __future__ import annotations

import logging

from sqlalchemy.orm import Session

from .db import AuditEntry, User
from .logging_setup import correlation_id, log_event, redact

log = logging.getLogger("audit")


def record(
    db: Session,
    *,
    user: User | None,
    github_login: str,
    identity: str,
    action: str,
    target_type: str,
    target_ref: str,
    outcome: str,
    github_status: int | None = None,
    request_id: str = "",
    detail: str = "",
) -> AuditEntry:
    entry = AuditEntry(
        entra_oid=user.entra_oid if user else "",
        github_login=github_login,
        identity=identity,
        action=action,
        target_type=target_type,
        target_ref=target_ref,
        github_status=github_status,
        outcome=outcome,
        portal_request_id=request_id,
        correlation_id=correlation_id.get(),
        detail=redact(detail)[:2000],
    )
    db.add(entry)
    db.commit()
    log_event(
        log,
        "audit",
        action=action,
        identity=identity,
        github_login=github_login,
        target=target_ref,
        outcome=outcome,
        github_status=github_status,
        request_id=request_id,
    )
    return entry
