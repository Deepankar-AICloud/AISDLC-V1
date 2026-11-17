from __future__ import annotations

import io
import json
import os
import shutil
import subprocess
import zipfile
from pathlib import Path
from typing import Any

import pytest
from fastapi.testclient import TestClient

from app.studio import jobs as jobs_mod
from app.studio.jobs import Runner, child_env, parse_summary
from app.studio.main import create_studio_app
from app.studio.settings import StudioSettings

REQUIREMENT = (
    "Business problem: employees wait days for laptop requests. Objective: self-service ordering with manager "
    "approval. Stakeholders: employees, managers, IT procurement."
)
AGENTS_YML = """agents:
  brd: {produces: docs/brd, artifact_prefix: BRD}
  prd: {produces: docs/prd, artifact_prefix: PRD}
  epic: {produces: docs/epic, artifact_prefix: EPIC}
  architecture: {produces: docs/architecture, artifact_prefix: ARCH}
  nfr: {produces: docs/nfr, artifact_prefix: NFR}
  task: {produces: docs/tasks, artifact_prefix: TASK}
  code: {produces: docs/code, artifact_prefix: CODE, writes_files: [src/frontend]}
"""
PREFIX = {
    "brd": ("docs/brd", "BRD"),
    "prd": ("docs/prd", "PRD"),
    "epic": ("docs/epic", "EPIC"),
    "architecture": ("docs/architecture", "ARCH"),
    "nfr": ("docs/nfr", "NFR"),
    "task": ("docs/tasks", "TASK"),
    "code": ("docs/code", "CODE"),
}


class FakeOrchestrator:
    """Mimics scripts.sdlc: model gate per stage, then GENERATED (or a scripted outcome)."""

    def __init__(self) -> None:
        self.stage = "brd"
        self.confirmed: set[str] = set()
        self.calls: list[list[str]] = []
        self.next_status: list[str] = []
        self.contexts: list[str] = []

    def ensure_workspace(self, runner: Runner, job: Any) -> None:
        ws = runner.store.workspace(job)
        (ws / "config").mkdir(parents=True, exist_ok=True)
        (ws / "config" / "agents.yml").write_text(AGENTS_YML, encoding="utf-8")
        subprocess.run(["git", "init", "--quiet", str(ws)], check=True)
        subprocess.run(
            [
                "git",
                "-c",
                "user.name=Test",
                "-c",
                "user.email=test@localhost",
                "commit",
                "--allow-empty",
                "-qm",
                "Base",
            ],
            cwd=ws,
            check=True,
        )

    def python(self, runner: Runner, job: Any, args: list[str], timeout: int) -> subprocess.CompletedProcess[str]:
        self.calls.append(args)
        module = args[1]
        out: dict[str, Any] = {}
        if module == "scripts.sdlc.model_confirm":
            self.confirmed.add(self.stage)
        elif module == "scripts.sdlc.approve":
            order = list(PREFIX)
            self.stage = order[order.index(self.stage) + 1] if self.stage != order[-1] else self.stage
        elif module == "scripts.sdlc.run":
            self.contexts.append(Path(args[args.index("--context-file") + 1]).read_text(encoding="utf-8"))
            if self.next_status:
                out = {
                    "status": self.next_status.pop(0),
                    "agent": self.stage,
                    "qc_score": 41,
                    "qc_status": "FAIL",
                    "qc_issues": ["Missing objectives"],
                }
            elif self.stage not in self.confirmed:
                out = {
                    "status": "AWAITING_MODEL_CONFIRMATION",
                    "agent": self.stage,
                    "recommendation": {
                        "recommended_model": "gpt-5.5",
                        "reason": "Best for documents",
                        "estimates": {"estimated_total_cost": "$0.10"},
                        "alternatives": [{"model": "gpt-5-mini", "profile": "cheaper"}],
                    },
                }
            else:
                folder, prefix = PREFIX[self.stage]
                path = runner.store.workspace(job) / folder / f"{prefix}-{job.number}.md"
                path.parent.mkdir(parents=True, exist_ok=True)
                path.write_text(f"# {prefix} for {job.title}\n\n<script>alert(1)</script>\n", encoding="utf-8")
                if self.stage == "code":
                    source = runner.store.workspace(job) / "src" / "frontend" / "generated.ts"
                    source.parent.mkdir(parents=True, exist_ok=True)
                    source.write_text("export const generated = true;\n", encoding="utf-8", newline="\n")
                out = {
                    "status": "GENERATED",
                    "agent": self.stage,
                    "qc_score": 92,
                    "qc_status": "PASS",
                    "selected_model": "gpt-5.5",
                }
        stdout = "noise line\n" + json.dumps(out, indent=2) if out else ""
        return subprocess.CompletedProcess(args, 0, stdout, "")


def make_settings(tmp_path: Path, **overrides: Any) -> StudioSettings:
    params: dict[str, Any] = dict(
        app_env="test",
        studio_password="admin",
        data_dir=tmp_path / "studio",
        extraction_isolation="inline",
        enable_code_stage=False,
        rate_limit_login_per_min=1000,
        rate_limit_create_per_min=1000,
        rate_limit_actions_per_min=1000,
    )
    params.update(overrides)
    return StudioSettings(**params)


@pytest.fixture
def fake(monkeypatch: pytest.MonkeyPatch) -> FakeOrchestrator:
    orch = FakeOrchestrator()
    monkeypatch.setattr(Runner, "_ensure_workspace", lambda self, job: orch.ensure_workspace(self, job))
    monkeypatch.setattr(Runner, "_python", lambda self, job, args, timeout: orch.python(self, job, args, timeout))
    return orch


@pytest.fixture
def studio(tmp_path: Path, fake: FakeOrchestrator) -> TestClient:
    return TestClient(create_studio_app(make_settings(tmp_path)))


def login(client: TestClient, password: str = "admin") -> Any:
    r = client.post("/api/login", json={"username": "admin", "password": password})
    if r.status_code == 200:
        client.headers["X-CSRF-Token"] = r.json()["csrf_token"]
    return r


def settle(client: TestClient, job_id: str) -> dict[str, Any]:
    client.app.state.runner.wait()  # type: ignore[attr-defined]
    return client.get(f"/api/jobs/{job_id}").json()


def test_login_and_session(studio: TestClient) -> None:
    assert studio.get("/api/jobs").status_code == 401
    assert login(studio, "wrong").status_code == 401
    assert login(studio).status_code == 200
    cookie = studio.cookies.get("aisdlc_studio")
    assert cookie and "admin" not in cookie
    s = studio.get("/api/session").json()
    assert s["username"] == "admin" and s["csrf_token"]
    assert "code" not in [x["key"] for x in s["stages"]]


def test_login_rate_limited(tmp_path: Path, fake: FakeOrchestrator) -> None:
    client = TestClient(create_studio_app(make_settings(tmp_path, rate_limit_login_per_min=2)))
    assert [login(client, "x").status_code for _ in range(3)] == [401, 401, 429]


def test_mutations_require_csrf(studio: TestClient) -> None:
    login(studio)
    token = studio.headers.pop("X-CSRF-Token")
    assert studio.post("/api/jobs", data={"text": REQUIREMENT}).status_code == 403
    r = studio.post("/api/jobs", data={"text": REQUIREMENT}, headers={"X-CSRF-Token": token + "x"})
    assert r.status_code == 403


def test_rejects_too_short_requirement(studio: TestClient) -> None:
    login(studio)
    r = studio.post("/api/jobs", data={"text": "too short"})
    assert r.status_code == 400 and r.json()["error"]["code"] == "too_short"


@pytest.mark.parametrize("code_enabled", [False, True])
def test_full_document_flow(tmp_path: Path, fake: FakeOrchestrator, code_enabled: bool) -> None:
    studio = TestClient(create_studio_app(make_settings(tmp_path, enable_code_stage=code_enabled)))
    login(studio)
    r = studio.post(
        "/api/jobs",
        data={"title": "Laptops", "text": REQUIREMENT},
        files=[("files", ("notes.md", b"# Notes\nMust integrate with ServiceNow.", "text/markdown"))],
    )
    assert r.status_code == 200, r.text
    job_id = r.json()["id"]

    job = settle(studio, job_id)
    assert job["status"] == "awaiting_model" and job["number"] == 1001
    assert job["result"]["recommendation"]["model"] == "gpt-5.5"
    assert "ServiceNow" in fake.contexts[0] and "TITLE: Laptops" in fake.contexts[0]
    assert studio.post(f"/api/jobs/{job_id}/approve").status_code == 409

    studio.post(f"/api/jobs/{job_id}/model", json={"model": "gpt-5-mini", "reason": "cost"})
    job = settle(studio, job_id)
    assert job["status"] == "review" and job["available"] == ["brd"]
    assert fake.calls[1][4:6] == ["--model", "gpt-5-mini"]
    doc = studio.get(f"/api/jobs/{job_id}/artifacts/brd").json()["markdown"]
    assert doc.startswith("# BRD for Laptops")

    studio.post(f"/api/jobs/{job_id}/revise", json={"text": "Add data retention."})
    job = settle(studio, job_id)
    assert job["status"] == "review" and "Add data retention." in fake.contexts[-1]

    for stage in ["prd", "epic", "architecture", "nfr", "task"] + (["code"] if code_enabled else []):
        studio.post(f"/api/jobs/{job_id}/approve")
        job = settle(studio, job_id)
        assert (job["stage"], job["status"]) == (stage, "awaiting_model")
        studio.post(f"/api/jobs/{job_id}/model", json={})
        assert settle(studio, job_id)["status"] == "review"
        if stage == "code":
            assert "code" not in settle(studio, job_id)["approved"]

    studio.post(f"/api/jobs/{job_id}/approve")
    job = settle(studio, job_id)
    assert job["status"] == "completed" and len(job["approved"]) == (7 if code_enabled else 6)

    bundle = studio.get(f"/api/jobs/{job_id}/download")
    assert bundle.status_code == 200 and bundle.headers["content-type"] == "application/zip"
    with zipfile.ZipFile(io.BytesIO(bundle.content)) as archive:
        assert "documents/TASK-1001.md" in archive.namelist()
        if code_enabled:
            assert "documents/CODE-1001.md" in archive.namelist()
            assert archive.read("code/files/src/frontend/generated.ts") == b"export const generated = true;\n"
    assert studio.delete(f"/api/jobs/{job_id}").status_code == 200
    assert studio.get(f"/api/jobs/{job_id}").status_code == 404


def test_failed_quality_check_cannot_be_approved(studio: TestClient, fake: FakeOrchestrator) -> None:
    login(studio)
    fake.confirmed.add("brd")
    fake.next_status = ["NEEDS_HUMAN"]
    job_id = studio.post("/api/jobs", data={"text": REQUIREMENT}).json()["id"]
    job = settle(studio, job_id)
    assert job["status"] == "needs_attention" and job["result"]["qc_issues"] == ["Missing objectives"]
    assert studio.post(f"/api/jobs/{job_id}/approve").status_code == 409
    studio.post(f"/api/jobs/{job_id}/retry")
    assert settle(studio, job_id)["status"] == "review"


def test_rejects_invalid_ids_and_model_names(studio: TestClient, fake: FakeOrchestrator) -> None:
    login(studio)
    assert studio.get("/api/jobs/..%2F..%2Fetc").status_code == 404
    job_id = studio.post("/api/jobs", data={"text": REQUIREMENT}).json()["id"]
    settle(studio, job_id)
    assert studio.post(f"/api/jobs/{job_id}/model", json={"model": "--evil flag"}).status_code == 400


def test_static_and_security_headers(studio: TestClient) -> None:
    r = studio.get("/")
    assert r.status_code == 200 and "AISDLC Studio" in r.text
    assert "script-src 'self'" in r.headers["content-security-policy"]
    assert studio.get("/app.js").status_code == 200


def test_parse_summary_ignores_noise() -> None:
    out = 'log line {\n{\n  "status": "GENERATED",\n  "nested": {\n    "a": 1\n  }\n}\n'
    assert parse_summary(out) == {"status": "GENERATED", "nested": {"a": 1}}
    assert parse_summary("no json here") is None


def test_child_env_excludes_studio_secrets(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("STUDIO_PASSWORD", "s3cret")
    monkeypatch.setenv("SESSION_SECRET", "x" * 40)
    monkeypatch.setenv("GITHUB_TOKEN", "ghp_x")
    monkeypatch.setenv("COPILOT_GITHUB_TOKEN", "ok")
    env = child_env()
    assert "STUDIO_PASSWORD" not in env and "SESSION_SECRET" not in env and "GITHUB_TOKEN" not in env
    assert env["COPILOT_GITHUB_TOKEN"] == "ok"


def test_settings_validation(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("STUDIO_PASSWORD", raising=False)
    with pytest.raises(ValueError, match="STUDIO_PASSWORD"):
        StudioSettings(data_dir=tmp_path)
    with pytest.raises(ValueError, match="SESSION_SECRET"):
        StudioSettings(app_env="production", studio_password="x" * 20, public_base_url="https://s.example")
    with pytest.raises(ValueError, match="https"):
        StudioSettings(app_env="production", studio_password="x" * 20, session_secret="y" * 40)
    assert make_settings(tmp_path).weak_password


def test_restart_recovers_busy_jobs(tmp_path: Path, fake: FakeOrchestrator) -> None:
    settings = make_settings(tmp_path)
    store = jobs_mod.JobStore(settings)
    job = store.create("t", REQUIREMENT, [])
    job.busy, job.status = True, "running"
    store.save(job)
    recovered = jobs_mod.JobStore(settings).get(job.id)
    assert (recovered.busy, recovered.status) == (False, "needs_attention")


@pytest.mark.parametrize("qc_status,artifact_exists", [("FAIL", True), ("PASS", False)])
def test_generated_requires_passing_artifact(tmp_path: Path, qc_status: str, artifact_exists: bool) -> None:
    settings = make_settings(tmp_path)
    store = jobs_mod.JobStore(settings)
    job = store.create("Fixture", REQUIREMENT, [])
    FakeOrchestrator().ensure_workspace(Runner(store, settings), job)
    if artifact_exists:
        path = store.workspace(job) / "docs" / "brd" / f"BRD-{job.number}.md"
        path.parent.mkdir(parents=True)
        path.write_text("# Draft", encoding="utf-8")
    Runner(store, settings)._apply(job, {"status": "GENERATED", "agent": "brd", "qc_status": qc_status})
    assert job.status == "needs_attention"


def test_failed_process_cannot_offer_approval(
    studio: TestClient, fake: FakeOrchestrator, monkeypatch: pytest.MonkeyPatch
) -> None:
    login(studio)
    monkeypatch.setattr(
        Runner,
        "_python",
        lambda *a, **kw: subprocess.CompletedProcess([], 1, '{\n"status":"GENERATED","qc_status":"PASS"\n}', "error"),
    )
    job_id = studio.post("/api/jobs", data={"text": REQUIREMENT}).json()["id"]
    assert settle(studio, job_id)["status"] == "failed"
    assert studio.post(f"/api/jobs/{job_id}/approve").status_code == 409


def test_bundle_reports_git_failure(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(subprocess, "run", lambda *a, **kw: subprocess.CompletedProcess([], 128, "", "broken repo"))
    with pytest.raises(jobs_mod.JobError, match="Could not read the generated code"):
        jobs_mod._git(tmp_path, "status")


def test_backend_secrets_are_not_served(tmp_path: Path, fake: FakeOrchestrator) -> None:
    password, signing_key = "server-only-password-canary", "server-only-signing-key-canary-123456"
    client = TestClient(
        create_studio_app(make_settings(tmp_path, studio_password=password, session_secret=signing_key))
    )
    login_response = login(client, password)
    assert login_response.status_code == 200
    assert "HttpOnly" in login_response.headers["set-cookie"]
    assert "SameSite=strict" in login_response.headers["set-cookie"]
    for response in [login_response, *(client.get(p) for p in ("/", "/app.js", "/api/session", "/api/jobs"))]:
        assert password not in response.text and signing_key not in response.text


def test_code_build_resolves_windows_launchers(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.syspath_prepend(str(Path(__file__).resolve().parents[4]))
    from scripts.sdlc import orchestrator

    frontend = tmp_path / "src" / "frontend"
    frontend.mkdir(parents=True)
    (frontend / "package.json").write_text("{}", encoding="utf-8")
    monkeypatch.setattr(orchestrator, "REPO_ROOT", tmp_path)
    monkeypatch.setattr(orchestrator.Orchestrator, "_git", staticmethod(lambda *args: "src/frontend/example.ts"))
    monkeypatch.setattr(shutil, "which", lambda name: f"C:\\tools\\{name}.CMD")
    called: list[list[str]] = []

    def run(command: list[str], **kwargs: Any) -> subprocess.CompletedProcess[str]:
        called.append(command)
        return subprocess.CompletedProcess(command, 0, "", "")

    monkeypatch.setattr(subprocess, "run", run)
    worker = object.__new__(orchestrator.Orchestrator)
    issues, _ = worker._build_checks(["src/frontend"])
    assert issues == []
    assert [cmd[0] for cmd in called] == [r"C:\tools\npm.CMD", r"C:\tools\npm.CMD", r"C:\tools\npx.CMD"]


@pytest.mark.skipif(os.environ.get("RUN_STUDIO_LIVE_TEST") != "1", reason="Opt-in real Copilot call uses account quota")
def test_live_code_stage(tmp_path: Path) -> None:
    """Real code generation against synthetic, pre-approved upstream fixtures; no real customer approvals."""
    settings = make_settings(tmp_path, enable_code_stage=True, use_llm=True)
    client = TestClient(create_studio_app(settings))
    app = client.app
    store = app.state.store  # type: ignore[attr-defined]
    runner = app.state.runner  # type: ignore[attr-defined]
    requirement = (
        "Synthetic validation only. Users need consistent request status labels. Add a named exported function "
        "requestStatusLabel(status: string): string in src/frontend/src/utils/requestStatusLabel.ts. "
        "Map pending to Pending, approved to Approved, rejected to Rejected; all other strings including empty "
        "return Unknown. Matching is case-sensitive. Add Vitest tests; do not change UI, backend, dependencies or "
        "deployment. Objective: reliable labels for employees; scope only this helper and tests."
    )
    job = store.create("Synthetic code-stage verification", requirement, [])
    runner._ensure_workspace(job)
    ws = store.workspace(job)
    task = ws / "docs" / "tasks" / f"TASK-{job.number}.md"
    architecture = ws / "docs" / "architecture" / f"ARCH-{job.number}.md"
    task.parent.mkdir(parents=True, exist_ok=True)
    architecture.parent.mkdir(parents=True, exist_ok=True)
    task.write_text(
        "# Synthetic approved task fixture\n\n### TASK-001 - Implement request status labels\n"
        + requirement
        + "\nFiles: src/frontend/src/utils/requestStatusLabel.ts and requestStatusLabel.test.ts.\n",
        encoding="utf-8",
    )
    architecture.write_text("# Synthetic approved architecture fixture\n\n" + requirement, encoding="utf-8")
    state_dir = ws / ".sdlc"
    state_dir.mkdir(exist_ok=True)
    (state_dir / f"issue-{job.number}.json").write_text(
        json.dumps(
            {
                "run_id": "studio-live-code-test",
                "issue_number": job.number,
                "current_state": "CODE_GENERATION",
                "artifacts": {"task": str(task), "architecture": str(architecture)},
            }
        ),
        encoding="utf-8",
    )
    job.stage, job.status = "code", "failed"
    store.save(job)
    login(client)
    assert client.post(f"/api/jobs/{job.id}/retry").status_code == 200
    runner.wait(180)
    snapshot = client.get(f"/api/jobs/{job.id}").json()
    assert snapshot["status"] == "awaiting_model", snapshot
    assert client.post(f"/api/jobs/{job.id}/approve").status_code == 409
    assert client.post(f"/api/jobs/{job.id}/model", json={}).status_code == 200
    runner.wait(settings.stage_timeout_seconds + 30)
    snapshot = client.get(f"/api/jobs/{job.id}").json()
    assert snapshot["status"] == "review", snapshot
    assert snapshot["result"]["qc_status"] == "PASS", snapshot
    assert snapshot["approved"] == []
    source = ws / "src" / "frontend" / "src" / "utils" / "requestStatusLabel.ts"
    assert source.is_file()
    verify = """
const fs = require('fs'), ts = require('typescript'), vm = require('vm'), assert = require('assert/strict');
const output = ts.transpileModule(fs.readFileSync(process.argv[1], 'utf8'),
  {compilerOptions: {module: ts.ModuleKind.CommonJS}}).outputText;
const sandbox = {exports: {}};
vm.runInNewContext(output, sandbox);
for (const [input, expected] of [['pending','Pending'],['approved','Approved'],['rejected','Rejected'],
  ['','Unknown'],['PENDING','Unknown'],['other','Unknown']]) {
  assert.equal(sandbox.exports.requestStatusLabel(input), expected);
}
console.log('All six generated-code behavior checks passed.');
"""
    subprocess.run([shutil.which("node") or "node", "-e", verify, str(source)], cwd=ws / "src" / "frontend", check=True)
    bundle = client.get(f"/api/jobs/{job.id}/download")
    assert bundle.status_code == 200
    with zipfile.ZipFile(io.BytesIO(bundle.content)) as archive:
        assert archive.read("code/files/src/frontend/src/utils/requestStatusLabel.ts") == source.read_bytes()
        assert archive.read("code/changes.patch")
        assert archive.read(f"documents/CODE-{job.number}.md")
    assert client.post(f"/api/jobs/{job.id}/approve").status_code == 200
    runner.wait(120)
    assert client.get(f"/api/jobs/{job.id}").json()["status"] == "completed"
    print(f"Real code-generation evidence: {ws}")
