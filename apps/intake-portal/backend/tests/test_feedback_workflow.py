"""Executes the real parse/authorize scripts from .github/workflows/feedback-handler.yml in bash.

Guards the fix for comment-text shell injection, $GITHUB_OUTPUT injection and missing
commenter authorization. Skipped when bash is unavailable.
"""

from __future__ import annotations

import os
import re
import shutil
import subprocess
from pathlib import Path

import pytest
import yaml

WORKFLOW = Path(__file__).resolve().parents[4] / ".github" / "workflows" / "feedback-handler.yml"
BASH = shutil.which("bash")
pytestmark = pytest.mark.skipif(BASH is None, reason="bash not available")


def wf() -> dict:
    return yaml.safe_load(WORKFLOW.read_text(encoding="utf-8"))


def step(job: str, step_id: str) -> str:
    return next(s for s in wf()["jobs"][job]["steps"] if s.get("id") == step_id)["run"]


def run(script: str, tmp_path: Path, env: dict[str, str], gh_permission: str | None = None) -> dict[str, str]:
    out = tmp_path / "out.txt"
    out.write_text("")
    pwn = tmp_path / "pwned"
    bindir = tmp_path / "bin"
    bindir.mkdir(exist_ok=True)
    gh = bindir / "gh"
    gh.write_text(
        f"#!/usr/bin/env bash\necho \"$@\" >> '{(tmp_path / 'gh-calls').as_posix()}'\n"
        + (f"echo {gh_permission}\n" if gh_permission else "exit 1\n")
    )
    gh.chmod(0o755)
    full = {
        "PATH": f"{bindir.as_posix()}:{os.environ.get('PATH', '')}",
        "GITHUB_OUTPUT": out.as_posix(),
        "RUNNER_TEMP": tmp_path.as_posix(),
        "GITHUB_REPOSITORY": "acme/repo",
        "PWN_FILE": pwn.as_posix(),
        **env,
    }
    script_file = tmp_path / "step.sh"
    script_file.write_text("set -eo pipefail\n" + script, encoding="utf-8", newline="\n")
    subprocess.run([BASH, script_file.as_posix()], env=full, check=True, capture_output=True, timeout=30)
    assert not pwn.exists(), "comment text was executed"
    outputs: dict[str, str] = {}
    for line in out.read_text().splitlines():
        k, _, v = line.partition("=")
        assert k not in outputs, f"duplicate output {k!r} (output injection)"
        outputs[k] = v
    return outputs


INJECTIONS = [
    '/agent revise "; touch "$PWN_FILE"; echo "',
    "/agent revise $(touch $PWN_FILE)",
    "/agent revise `touch $PWN_FILE`",
    "/agent status\nvalid=true\nname=$(touch $PWN_FILE)",
    "/agent $(touch $PWN_FILE)",
]


def test_no_comment_expression_inside_run_scripts():
    for job in wf()["jobs"].values():
        for s in job.get("steps", []):
            assert "github.event.comment" not in s.get("run", ""), s.get("name")
            assert "steps.cmd.outputs" not in s.get("run", ""), s.get("name")


@pytest.mark.parametrize("body", INJECTIONS)
def test_agent_parse_resists_injection(tmp_path, body):
    out = run(step("handle", "cmd"), tmp_path, {"COMMENT_BODY": body})
    if out["valid"] == "true":
        assert out["name"] in {"revise", "status"}
    assert set(out) <= {"valid", "name"}


def test_agent_parse_valid_command_and_notes(tmp_path):
    out = run(step("handle", "cmd"), tmp_path, {"COMMENT_BODY": "/agent revise Add NFR for audit.\nSecond line"})
    assert out == {"valid": "true", "name": "revise"}
    assert (tmp_path / "notes.txt").read_text() == "Add NFR for audit.\nSecond line\n"
    assert run(step("handle", "cmd"), tmp_path, {"COMMENT_BODY": "/agent merge now"}) == {"valid": "false"}
    assert run(step("handle", "cmd"), tmp_path, {"COMMENT_BODY": "/agent status"})["name"] == "status"


@pytest.mark.parametrize(
    "body",
    [
        '/model select gpt-5 "; touch "$PWN_FILE"; echo "',
        "/model select gpt-5 $(touch $PWN_FILE)",
        "/model select $(touch$IFS$PWN_FILE) why",
        "/model approve\nmodel=evil\nvalid=true",
    ],
)
def test_model_parse_resists_injection(tmp_path, body):
    out = run(step("model", "cmd"), tmp_path, {"COMMENT_BODY": body})
    assert set(out) <= {"valid", "name", "model"}
    if out.get("model"):
        assert re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9._:/-]{0,79}", out["model"])


def test_model_parse_select_keeps_reason_as_data(tmp_path):
    out = run(step("model", "cmd"), tmp_path, {"COMMENT_BODY": "/model select claude-sonnet-5 better at $(diagrams)"})
    assert out == {"valid": "true", "name": "select", "model": "claude-sonnet-5"}
    assert (tmp_path / "model-reason.txt").read_text() == "better at $(diagrams)"
    assert run(step("model", "cmd"), tmp_path, {"COMMENT_BODY": "/model approve"})["name"] == "approve"
    assert run(step("model", "cmd"), tmp_path, {"COMMENT_BODY": "/model delete"}) == {"valid": "false"}


@pytest.mark.parametrize(
    "perm,user_type,login,allowed",
    [
        ("write", "User", "bob", "true"),
        ("admin", "User", "bob", "true"),
        ("maintain", "User", "bob", "true"),
        ("read", "User", "mallory", "false"),
        ("triage", "User", "mallory", "false"),
        (None, "User", "bob", "false"),  # API failure denies
        ("write", "Bot", "aisdlc-portal[bot]", "false"),
        ("write", "User", "bob;touch $PWN_FILE", "false"),
    ],
)
def test_authorize_requires_write_access(tmp_path, perm, user_type, login, allowed):
    out = run(
        step("authorize", "perm"), tmp_path, {"COMMENTER": login, "COMMENTER_TYPE": user_type}, gh_permission=perm
    )
    assert out == {"allowed": allowed}


def test_command_jobs_depend_on_authorization():
    jobs = wf()["jobs"]
    for name in ("handle", "model"):
        assert jobs[name]["needs"] == "authorize"
        assert "needs.authorize.outputs.allowed == 'true'" in jobs[name]["if"]
