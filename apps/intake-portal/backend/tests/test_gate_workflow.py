"""Executes the real dispatch script of .github/workflows/agentic-sdlc-codeql-gate.yml with a stubbed `gh`.

Guards the fix that only people with triage access or more (never bots) can resume a paused run.
"""

from __future__ import annotations

import os
import shutil
import subprocess
from pathlib import Path

import pytest
import yaml

WORKFLOW = Path(__file__).resolve().parents[4] / ".github" / "workflows" / "agentic-sdlc-codeql-gate.yml"
BASH = shutil.which("bash")
pytestmark = pytest.mark.skipif(BASH is None, reason="bash not available")

GH_STUB = r"""#!/usr/bin/env bash
echo "$*" >> "$GH_LOG"
case "$*" in
  *"/permission"*) [[ -n "$STUB_ROLE" ]] && echo "$STUB_ROLE" || exit 1 ;;
  *"commits/main"*) echo "sha-main" ;;
  *"--json state"*) echo "OPEN" ;;
  *"--json labels"*) echo "sdlc:awaiting-info" ;;
  "run list"*) echo "sha-main" ;;
  *"actions/artifacts"*) echo "4242" ;;
  "issue edit"*|"workflow run"*|"issue comment"*) ;;
  *) echo "unexpected gh call: $*" >&2; exit 2 ;;
esac
"""


def dispatch_script() -> str:
    wf = yaml.safe_load(WORKFLOW.read_text(encoding="utf-8"))
    return wf["jobs"]["dispatch"]["steps"][0]["run"]


def run_gate(
    tmp_path: Path,
    *,
    login: str,
    user_type: str = "User",
    role: str | None = "triage",
    body: str = "Here is the missing information.",
    event: str = "issue_comment",
) -> list[str]:
    bindir = tmp_path / "bin"
    bindir.mkdir(exist_ok=True)
    gh = bindir / "gh"
    gh.write_text(GH_STUB, newline="\n")
    gh.chmod(0o755)
    log = tmp_path / "gh.log"
    log.write_text("")
    script = tmp_path / "gate.sh"
    script.write_text("set -eo pipefail\n" + dispatch_script(), encoding="utf-8", newline="\n")
    env = {
        "PATH": f"{bindir.as_posix()}:{os.environ.get('PATH', '')}",
        "GH_LOG": log.as_posix(),
        "STUB_ROLE": role or "",
        "GITHUB_REPOSITORY": "acme/repo",
        "EVENT_NAME": event,
        "ISSUE_NUMBER": "7",
        "CODEQL_SHA": "",
        "COMMENT_BODY": body,
        "COMMENT_AUTHOR_LOGIN": login,
        "COMMENT_AUTHOR_TYPE": user_type,
        "RESUME": "true",
    }
    subprocess.run([BASH, script.as_posix()], env=env, check=True, capture_output=True, timeout=30)
    return log.read_text().splitlines()


def resumed(calls: list[str]) -> bool:
    return any(c.startswith("workflow run agentic-sdlc.yml") for c in calls)


@pytest.mark.parametrize("role", ["triage", "write", "maintain", "admin"])
def test_people_with_triage_or_more_resume(tmp_path, role):
    calls = run_gate(tmp_path, login="alice-gh", role=role)
    assert resumed(calls)
    assert any("--remove-label sdlc:awaiting-info" in c for c in calls)


@pytest.mark.parametrize(
    ("login", "user_type", "role"),
    [
        ("mallory", "User", "read"),
        ("mallory", "User", "none"),
        ("bob", "User", None),  # permission API failure denies
        ("aisdlc-portal[bot]", "Bot", "write"),
        ("dependabot[bot]", "Bot", "write"),
        ("bob;touch-x", "User", "write"),
    ],
)
def test_others_cannot_resume(tmp_path, login, user_type, role):
    calls = run_gate(tmp_path, login=login, user_type=user_type, role=role)
    assert not resumed(calls)
    assert not any("issue edit" in c for c in calls)


def test_edited_issue_body_needs_the_same_access(tmp_path):
    assert not resumed(run_gate(tmp_path, login="mallory", role="read", event="issues"))
    assert resumed(run_gate(tmp_path, login="carol-gh", role="write", event="issues"))


def test_commands_and_actions_comments_still_ignored(tmp_path):
    assert not resumed(run_gate(tmp_path, login="bob", role="write", body="/agent status"))
    assert not resumed(run_gate(tmp_path, login="github-actions[bot]", user_type="Bot", role="write"))


def test_comment_author_type_is_passed_to_the_script():
    wf = yaml.safe_load(WORKFLOW.read_text(encoding="utf-8"))
    env = wf["jobs"]["dispatch"]["steps"][0]["env"]
    assert "COMMENT_AUTHOR_TYPE" in env and "github.event.comment.body" not in dispatch_script()
