"""LLM runner abstraction.

Wraps the Copilot CLI (as used by existing workflows) behind a small interface
so agents request work without knowing the transport. Returns the text output
plus a usage record. Copilot CLI does not expose per-call token counts, so
``usage_source`` is reported as ``unavailable`` for those calls rather than
fabricating numbers (prompt rule 27).

The runner degrades gracefully: if the CLI is absent (e.g. local dev without
credentials) it returns a clearly-marked stub so deterministic pipeline steps
remain testable.
"""
from __future__ import annotations

import shutil
import subprocess
import os
import tempfile
import time
from dataclasses import dataclass, field
from typing import Optional

from .logging_util import now_iso


@dataclass
class LLMUsage:
    provider: str
    requested_model: str
    actual_model: str
    model_version: Optional[str] = None
    input_tokens: Optional[int] = None
    output_tokens: Optional[int] = None
    cached_input_tokens: Optional[int] = None
    cache_write_tokens: Optional[int] = None
    total_tokens: Optional[int] = None
    latency_ms: Optional[int] = None
    usage_source: str = "unavailable"  # provider_reported | calculated | unavailable
    fallback_reason: Optional[str] = None


@dataclass
class LLMResult:
    text: str
    usage: LLMUsage
    ok: bool = True
    error: Optional[str] = None
    timestamp: str = field(default_factory=now_iso)


def _copilot_available() -> bool:
    return shutil.which("copilot") is not None


def run_llm(
    prompt: str,
    *,
    provider: str,
    requested_model: str,
    actual_model: str,
    fallback_reason: Optional[str] = None,
    allow_tools: bool = False,
    timeout_s: int = 600,
) -> LLMResult:
    """Execute a prompt via the configured runner.

    Only the Copilot CLI runner is wired today. Token usage is reported as
    ``unavailable`` because the CLI does not surface it.
    """
    usage = LLMUsage(
        provider=provider,
        requested_model=requested_model,
        actual_model=actual_model,
        fallback_reason=fallback_reason,
        usage_source="unavailable",
    )

    if not _copilot_available():
        usage.usage_source = "unavailable"
        return LLMResult(
            text="[LLM UNAVAILABLE] Copilot CLI not found; returning stub output.",
            usage=usage,
            ok=False,
            error="copilot_cli_not_found",
        )

    cmd = ["copilot", "-p", prompt, "--model", actual_model,
           "--allow-all-tools", "--silent"]
    env = os.environ.copy()
    for key in ("GH_TOKEN", "GITHUB_TOKEN", "ACTIONS_RUNTIME_TOKEN",
                "ACTIONS_ID_TOKEN_REQUEST_TOKEN"):
        env.pop(key, None)

    workdir = None
    tempdir = None
    if not allow_tools:
        prompt = (
            "Generation-only request: do not invoke tools, run commands, inspect "
            "files, or modify files. Return only the requested text.\n\n" + prompt
        )
        cmd[2] = prompt
        tempdir = tempfile.TemporaryDirectory(prefix="sdlc-copilot-")
        workdir = tempdir.name

    start = time.monotonic()
    try:
        proc = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            timeout=timeout_s,
            check=False,
            cwd=workdir,
            env=env,
        )
    except subprocess.TimeoutExpired:
        usage.latency_ms = int((time.monotonic() - start) * 1000)
        return LLMResult(text="", usage=usage, ok=False, error="timeout")
    finally:
        if tempdir is not None:
            tempdir.cleanup()

    usage.latency_ms = int((time.monotonic() - start) * 1000)
    if proc.returncode != 0:
        return LLMResult(
            text=proc.stdout or "",
            usage=usage,
            ok=False,
            error=(proc.stderr or proc.stdout or "nonzero_exit").strip()[:500],
        )
    text = (proc.stdout or "").strip()
    if not text:
        return LLMResult(text="", usage=usage, ok=False, error="empty_response")
    return LLMResult(text=text, usage=usage, ok=True)
