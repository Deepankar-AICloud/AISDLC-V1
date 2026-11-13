"""GitHub webhook receiver (HMAC-SHA256 verified, replay-deduplicated). Polling covers missed deliveries."""

from __future__ import annotations

import hashlib
import hmac
import json
import logging

from fastapi import APIRouter, BackgroundTasks, Depends, Request, Response
from sqlalchemy.exc import IntegrityError

from ..container import Container
from ..db import WebhookDelivery
from ..errors import ApiError
from ..status.sync import requests_for_event, sync_request
from .deps import container

router = APIRouter()
log = logging.getLogger(__name__)
MAX_WEBHOOK_BYTES = 5 * 1024 * 1024


def verify_signature(secret: str, body: bytes, header: str | None) -> bool:
    if not secret or not header or not header.startswith("sha256="):
        return False
    expected = "sha256=" + hmac.new(secret.encode(), body, hashlib.sha256).hexdigest()
    return hmac.compare_digest(expected, header)


def _resync(c: Container, event: str, payload: dict) -> None:
    with c.db.sessionmaker() as db:
        for req in requests_for_event(db, event, payload):
            sync_request(c, db, req)


@router.post("/webhooks/github", status_code=204)
async def github_webhook(request: Request, background: BackgroundTasks, c: Container = Depends(container)) -> Response:
    body = await request.body()
    if len(body) > MAX_WEBHOOK_BYTES:
        raise ApiError(413, "too_large", "Payload too large.")
    if not verify_signature(
        c.settings.github_webhook_secret.get_secret_value(), body, request.headers.get("x-hub-signature-256")
    ):
        raise ApiError(401, "bad_signature", "Invalid webhook signature.")
    delivery = request.headers.get("x-github-delivery", "")[:64]
    event = request.headers.get("x-github-event", "")
    if delivery:
        with c.db.sessionmaker() as db:
            db.add(WebhookDelivery(delivery_id=delivery))
            try:
                db.commit()
            except IntegrityError:
                return Response(status_code=204)  # replay
    try:
        payload = json.loads(body)
    except ValueError as exc:
        raise ApiError(400, "bad_payload", "Invalid JSON.") from exc
    background.add_task(_resync, c, event, payload)
    return Response(status_code=204)
