"""Structured logging and correlation/run-ID helpers.

One run_id per Agentic SDLC execution ties together GitHub Actions run,
commit, PR/issue, agent, artifact, model, QC, tokens and cost. Secrets are
never logged.
"""
from __future__ import annotations

import json
import logging
import sys
import uuid
from datetime import datetime, timezone

_SECRET_HINTS = ("token", "password", "secret", "key", "credential")


def new_run_id(prefix: str = "sdlc") -> str:
    ts = datetime.now(timezone.utc).strftime("%Y%m%d-%H%M%S")
    return f"{prefix}-{ts}-{uuid.uuid4().hex[:8]}"


def now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def _redact(value: str) -> str:
    return value if len(value) < 8 else value[:2] + "***" + value[-2:]


class StructuredLogger:
    """Minimal structured logger emitting JSON lines to stderr."""

    def __init__(self, run_id: str) -> None:
        self.run_id = run_id
        self._log = logging.getLogger("sdlc")
        if not self._log.handlers:
            handler = logging.StreamHandler(sys.stderr)
            handler.setFormatter(logging.Formatter("%(message)s"))
            self._log.addHandler(handler)
            self._log.setLevel(logging.INFO)

    def event(self, message: str, **fields: object) -> None:
        safe: dict[str, object] = {}
        for k, v in fields.items():
            if any(h in k.lower() for h in _SECRET_HINTS) and isinstance(v, str):
                v = _redact(v)
            safe[k] = v
        record = {"ts": now_iso(), "run_id": self.run_id, "msg": message, **safe}
        self._log.info(json.dumps(record))
