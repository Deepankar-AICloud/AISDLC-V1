"""Allowlisted AISDLC commands. Free text can never change the command itself.

Mirrors `.github/workflows/feedback-handler.yml`:
  /agent revise|regenerate|rerun-qc|explain|status|impact
  /model approve|select|compare|status
`feedback-handler.yml` interpolates `${{ github.event.comment.body }}` into
shell, so until that workflow is fixed the portal refuses notes containing shell
metacharacters (BLOCK_SHELL_METACHARACTERS=true).
"""

from __future__ import annotations

import re
from enum import StrEnum


class AgentCommand(StrEnum):
    revise = "revise"
    regenerate = "regenerate"
    rerun_qc = "rerun-qc"
    explain = "explain"
    status = "status"
    impact = "impact"


class ModelCommand(StrEnum):
    approve = "approve"
    select = "select"
    compare = "compare"
    status = "status"


class CommandError(ValueError):
    pass


NOTES_MAX = 4000
_SHELL_META = re.compile(r"[\"`$\\]")
_MODEL_ID = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._:/-]{0,79}$")


def clean_notes(notes: str, *, block_shell: bool, required: bool = False) -> str:
    text = (notes or "").replace("\r\n", "\n").strip()
    if required and not text:
        raise CommandError("Please describe the changes you want.")
    if len(text) > NOTES_MAX:
        raise CommandError(f"Notes are limited to {NOTES_MAX} characters.")
    if block_shell and _SHELL_META.search(text):
        raise CommandError(
            'Notes cannot contain ", `, $ or \\ until feedback-handler.yml stops interpolating comment text into '
            "shell (see the portal README, 'Required GitHub protections')."
        )
    if re.search(r"^\s*/", text, re.M):
        raise CommandError("Notes cannot contain lines starting with '/', which could read as another command.")
    return text


def agent_command(cmd: AgentCommand, notes: str = "", *, block_shell: bool = True) -> str:
    text = clean_notes(notes, block_shell=block_shell, required=cmd is AgentCommand.revise)
    return f"/agent {cmd.value}" + (f" {text}" if text else "")


def model_command(
    cmd: ModelCommand, model: str = "", reason: str = "", *, allowed_models: set[str], block_shell: bool = True
) -> str:
    if cmd is ModelCommand.select:
        if not _MODEL_ID.match(model or ""):
            raise CommandError("Choose a model from the list.")
        if allowed_models and model not in allowed_models:
            raise CommandError(f"'{model}' is not a configured model.")
        reason_text = clean_notes(reason, block_shell=block_shell, required=True).replace("\n", " ")
        return f"/model select {model} {reason_text}"
    return f"/model {cmd.value}"


def answer_text(answer: str) -> str:
    """An answer to sdlc:awaiting-info. Must not start with '/', or the CodeQL gate ignores it."""
    text = (answer or "").replace("\r\n", "\n").strip()
    if not text:
        raise CommandError("Please enter an answer.")
    if len(text) > 30_000:
        raise CommandError("Answers are limited to 30,000 characters.")
    if text.startswith("/"):
        raise CommandError("Answers cannot start with '/'; AISDLC would treat it as a command and ignore it.")
    if PART_PREFIX.match(text):
        raise CommandError("Answers cannot start with '[Part '.")
    return text


PART_PREFIX = re.compile(r"^\[Part \d+/\d+ of ")
