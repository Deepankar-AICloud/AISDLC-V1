"""Studio jobs: persistence, isolated workspaces and the background stage runner.

Each job is one requirement taken through BRD -> PRD -> Epics -> Architecture -> NFR ->
Tasks -> Code. The AISDLC orchestrator (scripts.sdlc) runs as a subprocess inside a
private shallow clone of the AISDLC repository, so generated artifacts and code never
touch the real working tree. Humans gate every stage (model choice, missing information,
approve / request changes), exactly as in the GitHub-driven flow.
"""

from __future__ import annotations

import contextlib
import io
import json
import logging
import os
import re
import shutil
import stat
import subprocess
import threading
import uuid
import zipfile
from dataclasses import asdict, dataclass, field
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import yaml

from ..logging_setup import log_event, redact
from .settings import StudioSettings

log = logging.getLogger("studio")

STAGES: list[tuple[str, str]] = [
    ("brd", "Business Requirements (BRD)"),
    ("prd", "Product Requirements (PRD)"),
    ("epic", "Epics & User Stories"),
    ("architecture", "Architecture"),
    ("nfr", "Non-Functional Requirements"),
    ("task", "Task Plan"),
    ("code", "Code"),
]
STAGE_LABELS = dict(STAGES)
STAGE_KEYS = [k for k, _ in STAGES]

# Job statuses shown to the user.
QUEUED, RUNNING = "queued", "running"
AWAITING_MODEL, AWAITING_INFO = "awaiting_model", "awaiting_info"
REVIEW, NEEDS_ATTENTION = "review", "needs_attention"
COMPLETED, FAILED = "completed", "failed"

# Which user actions are valid in which status.
ALLOWED: dict[str, set[str]] = {
    "confirm_model": {AWAITING_MODEL},
    "answer": {AWAITING_INFO},
    "approve": {REVIEW},
    "revise": {REVIEW, NEEDS_ATTENTION},
    "retry": {NEEDS_ATTENTION, FAILED},
}

_JOB_ID = re.compile(r"^[0-9a-f]{16}$")
_MAX_ARTIFACT_CHARS = 500_000
_MAX_ZIP_BYTES = 80 * 1024 * 1024

# Environment passed to the orchestrator: an allowlist, so Studio secrets
# (STUDIO_PASSWORD, SESSION_SECRET) never reach the generator or the AI agent.
_ENV_NAMES = {
    "PATH",
    "PATHEXT",
    "SYSTEMROOT",
    "SYSTEMDRIVE",
    "WINDIR",
    "COMSPEC",
    "TEMP",
    "TMP",
    "TMPDIR",
    "HOME",
    "USERPROFILE",
    "HOMEDRIVE",
    "HOMEPATH",
    "APPDATA",
    "LOCALAPPDATA",
    "PROGRAMDATA",
    "PROGRAMFILES",
    "PROGRAMFILES(X86)",
    "PROGRAMW6432",
    "COMMONPROGRAMFILES",
    "USERNAME",
    "USER",
    "LANG",
    "LC_ALL",
    "TZ",
    "NUMBER_OF_PROCESSORS",
    "PROCESSOR_ARCHITECTURE",
    "OS",
    "HTTP_PROXY",
    "HTTPS_PROXY",
    "NO_PROXY",
    "SSL_CERT_FILE",
    "SSL_CERT_DIR",
    "REQUESTS_CA_BUNDLE",
    "NODE_EXTRA_CA_CERTS",
    "MODEL_SELECTION_MODE",
}
_ENV_PREFIXES = ("COPILOT_", "DOTNET_", "NUGET_", "NPM_CONFIG_", "XDG_")


class JobError(Exception):
    def __init__(self, status: int, code: str, message: str) -> None:
        super().__init__(message)
        self.status = status
        self.code = code
        self.message = message


def _now() -> str:
    return datetime.now(UTC).isoformat(timespec="seconds")


@dataclass
class Job:
    id: str
    number: int
    title: str
    created_at: str
    updated_at: str
    status: str = QUEUED
    stage: str = "brd"
    busy: bool = False
    message: str = ""
    approved: list[str] = field(default_factory=list)
    comments: list[str] = field(default_factory=list)
    questions: list[str] = field(default_factory=list)
    result: dict[str, Any] = field(default_factory=dict)
    sources: list[dict[str, Any]] = field(default_factory=list)
    events: list[dict[str, str]] = field(default_factory=list)

    def note(self, text: str) -> None:
        self.events.append({"ts": _now(), "text": text})
        del self.events[:-100]


def child_env() -> dict[str, str]:
    env: dict[str, str] = {}
    for name, value in os.environ.items():
        upper = name.upper()
        if upper in _ENV_NAMES or upper.startswith(_ENV_PREFIXES):
            env[name] = value
    env.update({"PYTHONIOENCODING": "utf-8", "PYTHONUTF8": "1", "PYTHONDONTWRITEBYTECODE": "1"})
    return env


def parse_summary(stdout: str) -> dict[str, Any] | None:
    """run.py prints one indented JSON object last; find the last line that opens it."""
    lines = stdout.splitlines()
    for i in range(len(lines) - 1, -1, -1):
        if lines[i].rstrip() == "{":
            try:
                data = json.loads("\n".join(lines[i:]))
            except json.JSONDecodeError:
                continue
            if isinstance(data, dict):
                return data
    return None


def _rmtree(path: Path) -> None:
    def onexc(func: Any, p: str, _exc: BaseException) -> None:
        # git marks pack files read-only, which blocks deletion on Windows.
        os.chmod(p, stat.S_IWRITE)
        func(p)

    shutil.rmtree(path, onexc=onexc)


class JobStore:
    """Jobs persisted as JSON under DATA_DIR/jobs/<id>/ (single instance; use one replica)."""

    def __init__(self, settings: StudioSettings) -> None:
        self.s = settings
        self.root = settings.data_dir.resolve() / "jobs"
        self.root.mkdir(parents=True, exist_ok=True)
        self.lock = threading.RLock()
        self._recover()

    # -- paths ------------------------------------------------------------
    def job_dir(self, job_id: str) -> Path:
        if not _JOB_ID.match(job_id):
            raise JobError(404, "not_found", "Request not found.")
        return self.root / job_id

    def workspace(self, job: Job) -> Path:
        return self.job_dir(job.id) / "workspace"

    # -- persistence ------------------------------------------------------
    def _next_number(self) -> int:
        counter = self.root / "counter.txt"
        current = int(counter.read_text(encoding="utf-8").strip()) if counter.exists() else self.s.first_job_number - 1
        number = current + 1
        counter.write_text(str(number), encoding="utf-8")
        return number

    def create(self, title: str, requirement: str, sources: list[dict[str, Any]]) -> Job:
        with self.lock:
            job_id = uuid.uuid4().hex[:16]
            d = self.root / job_id
            d.mkdir(parents=True)
            (d / "requirement.txt").write_text(requirement, encoding="utf-8")
            now = _now()
            job = Job(
                id=job_id, number=self._next_number(), title=title, created_at=now, updated_at=now, sources=sources
            )
            job.note("Requirement received.")
            self.save(job)
            return job

    def save(self, job: Job) -> None:
        with self.lock:
            job.updated_at = _now()
            path = self.job_dir(job.id) / "job.json"
            tmp = path.with_suffix(".tmp")
            tmp.write_text(json.dumps(asdict(job), indent=2), encoding="utf-8")
            os.replace(tmp, path)

    def get(self, job_id: str) -> Job:
        path = self.job_dir(job_id) / "job.json"
        with self.lock:
            if not path.is_file():
                raise JobError(404, "not_found", "Request not found.")
            return Job(**json.loads(path.read_text(encoding="utf-8")))

    def all(self) -> list[Job]:
        jobs: list[Job] = []
        with self.lock:
            for d in self.root.iterdir():
                if d.is_dir() and _JOB_ID.match(d.name) and (d / "job.json").is_file():
                    jobs.append(Job(**json.loads((d / "job.json").read_text(encoding="utf-8"))))
        return sorted(jobs, key=lambda j: j.created_at, reverse=True)

    def delete(self, job_id: str) -> None:
        with self.lock:
            job = self.get(job_id)
            if job.busy:
                raise JobError(409, "busy", "This request is still running. Wait for it to finish.")
            _rmtree(self.job_dir(job_id))

    def _recover(self) -> None:
        for job in self.all():
            if job.busy:
                job.busy = False
                job.status = NEEDS_ATTENTION
                job.message = "The previous run was interrupted (the server restarted). Select Retry."
                job.note("Run interrupted by a restart.")
                self.save(job)

    # -- requirement / context ------------------------------------------------
    def requirement(self, job: Job) -> str:
        return (self.job_dir(job.id) / "requirement.txt").read_text(encoding="utf-8")

    def context(self, job: Job) -> str:
        # Same shape as the GitHub workflow's issue context (TITLE / BODY / HUMAN COMMENTS).
        return f"TITLE: {job.title}\n\nBODY:\n{self.requirement(job)}\n\nHUMAN COMMENTS:\n" + "\n---\n".join(
            job.comments
        )

    # -- artifacts ----------------------------------------------------------
    def agents_config(self, job: Job) -> dict[str, Any]:
        cfg_path = self.workspace(job) / "config" / "agents.yml"
        if not cfg_path.is_file():
            return {}
        data = yaml.safe_load(cfg_path.read_text(encoding="utf-8")) or {}
        return data.get("agents", {}) if isinstance(data, dict) else {}

    def artifact_path(self, job: Job, stage: str) -> Path | None:
        if stage not in STAGE_LABELS:
            return None
        agent = self.agents_config(job).get(stage) or {}
        produces, prefix = agent.get("produces"), agent.get("artifact_prefix")
        if not produces or not prefix:
            return None
        ws = self.workspace(job).resolve()
        path = (ws / str(produces) / f"{prefix}-{job.number}.md").resolve()
        return path if path.is_relative_to(ws) and path.is_file() else None

    def artifact_text(self, job: Job, stage: str) -> str:
        path = self.artifact_path(job, stage)
        if path is None:
            raise JobError(404, "not_found", "That document has not been generated yet.")
        text = path.read_text(encoding="utf-8", errors="replace")
        if len(text) > _MAX_ARTIFACT_CHARS:
            text = text[:_MAX_ARTIFACT_CHARS] + "\n\n_[truncated — download the bundle for the full document]_\n"
        return text

    def available_stages(self, job: Job) -> list[str]:
        return [k for k in STAGE_KEYS if self.artifact_path(job, k) is not None]

    # -- download bundle ---------------------------------------------------
    def _changed_code_files(self, job: Job) -> tuple[list[str], str]:
        ws = self.workspace(job)
        writes = [str(p) for p in (self.agents_config(job).get("code") or {}).get("writes_files") or []]
        if not writes or not (ws / ".git").exists():
            return [], ""
        status = _git(ws, "status", "--porcelain=v1", "-z", "-uall", "--", *writes)
        entries = status.split("\0")
        files: list[str] = []
        i = 0
        while i < len(entries):
            entry = entries[i]
            i += 1
            if len(entry) < 4:
                continue
            code, path = entry[:2], entry[3:]
            if code[0] in "RC":
                i += 1  # skip the rename source
            if "D" not in code:
                files.append(path)
        patch = _git(ws, "diff", "--no-ext-diff", "--binary", "HEAD", "--", *writes)
        return files, patch

    def bundle(self, job: Job) -> bytes:
        buf = io.BytesIO()
        total = 0
        ws = self.workspace(job).resolve()
        with zipfile.ZipFile(buf, "w", zipfile.ZIP_DEFLATED) as zf:
            zf.writestr("requirement.txt", self.requirement(job))
            for stage in STAGE_KEYS:
                path = self.artifact_path(job, stage)
                if path is not None:
                    zf.write(path, f"documents/{path.name}")
            if self.artifact_path(job, "code") is not None:
                files, patch = self._changed_code_files(job)
                if patch:
                    zf.writestr("code/changes.patch", patch)
                for rel in files:
                    src = (ws / rel).resolve()
                    if not src.is_relative_to(ws) or not src.is_file():
                        continue
                    total += src.stat().st_size
                    if total > _MAX_ZIP_BYTES:
                        zf.writestr("code/TRUNCATED.txt", "Bundle size limit reached; remaining files omitted.\n")
                        break
                    zf.write(src, f"code/files/{rel}")
        return buf.getvalue()


def _git(cwd: Path, *args: str) -> str:
    proc = subprocess.run(  # noqa: S603
        ["git", *args],  # noqa: S607
        cwd=cwd,
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
        check=False,
        env=child_env(),
        timeout=120,
    )
    if proc.returncode != 0:
        log.error("git operation failed", extra={"fields": {"stderr": redact(proc.stderr[-2000:])}})
        raise JobError(500, "git_failed", "Could not read the generated code. Check the server logs and retry.")
    return proc.stdout


class Runner:
    """Runs stage actions in background threads, at most MAX_CONCURRENT_RUNS at a time."""

    def __init__(self, store: JobStore, settings: StudioSettings) -> None:
        self.store = store
        self.s = settings
        self.slots = threading.BoundedSemaphore(settings.max_concurrent_runs)
        self.threads: list[threading.Thread] = []

    def submit(self, job_id: str, action: str, **kw: Any) -> Job:
        with self.store.lock:
            job = self.store.get(job_id)
            if job.busy:
                raise JobError(409, "busy", "This request is already running. Wait for it to finish.")
            if action in ALLOWED and job.status not in ALLOWED[action]:
                raise JobError(409, "invalid_state", "That action is not available at this step.")
            job.busy = True
            job.status = QUEUED
            job.message = "Waiting for a free generator slot…"
            self.store.save(job)
        t = threading.Thread(target=self._run, args=(job_id, action, kw), daemon=True, name=f"studio-{job_id}")
        self.threads.append(t)
        t.start()
        self.threads = [x for x in self.threads if x.is_alive()]
        return job

    def wait(self, timeout: float = 30) -> None:
        for t in list(self.threads):
            t.join(timeout)

    # -- worker -------------------------------------------------------------
    def _run(self, job_id: str, action: str, kw: dict[str, Any]) -> None:
        with self.slots:
            job = self.store.get(job_id)
            job.status = RUNNING
            job.message = f"Working on {STAGE_LABELS.get(job.stage, job.stage)}…"
            self.store.save(job)
            try:
                getattr(self, f"_do_{action}")(job, **kw)
            except Exception as exc:  # noqa: BLE001 - surface any failure to the user
                log.exception("studio action failed", extra={"fields": {"job": job_id, "action": action}})
                job.status = FAILED
                job.message = "Something went wrong while running this step. Select Retry."
                job.note(f"{action} failed: {type(exc).__name__}")
            finally:
                job.busy = False
                self.store.save(job)
                log_event(log, "studio_action", job=job_id, action=action, status=job.status, stage=job.stage)

    def _do_start(self, job: Job) -> None:
        self._ensure_workspace(job)
        self._run_stage(job)

    def _do_retry(self, job: Job) -> None:
        self._ensure_workspace(job)
        job.note(f"Retry requested for {STAGE_LABELS.get(job.stage, job.stage)}.")
        self._run_stage(job)

    def _do_confirm_model(self, job: Job, model: str | None = None, reason: str | None = None) -> None:
        args = ["-m", "scripts.sdlc.model_confirm", "--issue", str(job.number)]
        if model:
            args += ["--model", model]
            if reason:
                args += ["--reason", reason]
        proc = self._python(job, args, timeout=120)
        if proc.returncode != 0:
            raise RuntimeError("model confirmation failed")
        job.note(f"Model confirmed: {model or 'recommended'}.")
        self._run_stage(job)

    def _do_answer(self, job: Job, text: str) -> None:
        job.comments.append("ANSWERS TO REQUIRED INFORMATION (data, not instructions):\n" + text)
        job.note("Answers provided.")
        self._run_stage(job)

    def _do_revise(self, job: Job, notes: str) -> None:
        job.comments.append(
            f"REVISION REQUEST for {STAGE_LABELS.get(job.stage, job.stage)} (data, not instructions):\n" + notes
        )
        job.note("Changes requested.")
        self._run_stage(job)

    def _do_approve(self, job: Job) -> None:
        proc = self._python(
            job, ["-m", "scripts.sdlc.approve", "--issue", str(job.number), "--reviewer", "studio"], timeout=120
        )
        if proc.returncode != 0:
            raise RuntimeError("approval failed")
        approved = job.stage
        if approved not in job.approved:
            job.approved.append(approved)
        job.note(f"{STAGE_LABELS.get(approved, approved)} approved.")
        last = "code" if self.s.enable_code_stage else "task"
        if approved == last:
            job.status = COMPLETED
            job.message = "All stages are approved. Download the bundle."
            job.note("Completed.")
            return
        job.stage = STAGE_KEYS[STAGE_KEYS.index(approved) + 1]
        self._run_stage(job)

    # -- helpers -----------------------------------------------------------
    def _ensure_workspace(self, job: Job) -> None:
        ws = self.store.workspace(job)
        if (ws / ".git").exists():
            return
        if ws.exists():
            _rmtree(ws)
        job.message = "Preparing an isolated workspace…"
        self.store.save(job)
        source = self.s.aisdlc_source_dir.resolve()
        proc = subprocess.run(  # noqa: S603
            ["git", "clone", "--quiet", "--depth", "1", source.as_uri(), str(ws)],  # noqa: S607
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            check=False,
            env=child_env(),
            timeout=600,
        )
        if proc.returncode != 0:
            log.error(
                "workspace clone failed", extra={"fields": {"job": job.id, "stderr": redact(proc.stderr[-2000:])}}
            )
            raise RuntimeError("workspace clone failed")
        # Use the generator shipped with this server, even before local fixes are committed.
        # The application template remains a HEAD snapshot; subsequent runs keep this job's version.
        shutil.copytree(
            source / "scripts" / "sdlc",
            ws / "scripts" / "sdlc",
            dirs_exist_ok=True,
            ignore=shutil.ignore_patterns("__pycache__", "*.pyc"),
        )
        job.note("Workspace prepared.")

    def _python(self, job: Job, args: list[str], timeout: int) -> subprocess.CompletedProcess[str]:
        ws = self.store.workspace(job)
        proc = subprocess.run(  # noqa: S603
            [self.s.orchestrator_python, *args],
            cwd=ws,
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            check=False,
            env=child_env(),
            timeout=timeout,
        )
        log_path = self.store.job_dir(job.id) / "last-run.log"
        log_path.write_text(
            redact(f"$ {' '.join(args)}\n--- stdout ---\n{proc.stdout}\n--- stderr ---\n{proc.stderr}"),
            encoding="utf-8",
        )
        return proc

    def _run_stage(self, job: Job) -> None:
        label = STAGE_LABELS.get(job.stage, job.stage)
        if job.stage == "code" and not self.s.enable_code_stage:
            job.status = COMPLETED
            job.message = "Code generation is disabled on this Studio."
            return
        job.status = RUNNING
        job.message = f"Generating {label}… this can take several minutes."
        self.store.save(job)
        ctx_file = self.store.job_dir(job.id) / "context.txt"
        ctx_file.write_text(self.store.context(job), encoding="utf-8")
        args = ["-m", "scripts.sdlc.run", "--issue", str(job.number), "--context-file", str(ctx_file)]
        if not self.s.use_llm:
            args.append("--no-llm")
        try:
            proc = self._python(job, args, timeout=self.s.stage_timeout_seconds)
        except subprocess.TimeoutExpired:
            job.status = NEEDS_ATTENTION
            job.message = f"{label} took longer than {self.s.stage_timeout_seconds // 60} minutes and was stopped."
            job.note(f"{label} timed out.")
            return
        if proc.returncode != 0:
            job.status = FAILED
            job.message = f"The generator exited unsuccessfully (exit {proc.returncode}). Check the server run log."
            job.note(f"{label}: generator process failed.")
            return
        summary = parse_summary(proc.stdout)
        if summary is None:
            job.status = FAILED
            job.message = "The generator did not return a result. Select Retry."
            job.note(f"{label}: no result from the generator.")
            return
        self._apply(job, summary)

    def _apply(self, job: Job, summary: dict[str, Any]) -> None:
        agent = summary.get("agent")
        if agent in STAGE_LABELS:
            job.stage = agent
        label = STAGE_LABELS.get(job.stage, job.stage)
        rec = summary.get("recommendation") or {}
        diag = summary.get("diagnosis") or {}
        job.result = {
            "qc_score": summary.get("qc_score"),
            "qc_status": summary.get("qc_status"),
            "qc_issues": [str(i) for i in (summary.get("qc_issues") or [])][:25],
            "selected_model": summary.get("selected_model"),
            "recommendation": {
                "model": rec.get("recommended_model"),
                "reason": rec.get("reason"),
                "estimated_cost": (rec.get("estimates") or {}).get("estimated_total_cost"),
                "alternatives": [
                    {"model": a.get("model"), "profile": a.get("profile")} for a in rec.get("alternatives") or []
                ],
            }
            if rec
            else None,
            "diagnosis": diag.get("rationale"),
        }
        job.questions = []
        status = summary.get("status")
        if status == "AWAITING_MODEL_CONFIRMATION":
            job.status = AWAITING_MODEL
            job.message = f"Choose the AI model for {label}."
        elif status == "AWAITING_REQUIRED_INFORMATION":
            job.status = AWAITING_INFO
            job.questions = self._pending_questions(job, summary)
            job.message = f"{label} needs more information before it can be generated."
        elif status == "GENERATED":
            if summary.get("qc_status") != "PASS" or self.store.artifact_path(job, job.stage) is None:
                job.status = NEEDS_ATTENTION
                job.message = f"{label} has no verified, QC-passing artifact. Select Retry."
            else:
                job.status = REVIEW
                job.message = f"{label} is ready for review. Approve it to continue, or request changes."
        elif status == "NEEDS_HUMAN":
            job.status = NEEDS_ATTENTION
            job.message = (
                f"{label} did not pass the quality check. Request changes with guidance, or Retry."
                if summary.get("qc_status")
                else f"{label} could not be generated. Select Retry."
            )
        elif status == "HANDED_OFF":
            job.status = COMPLETED
            job.message = "All stages are complete. Download the bundle."
        else:
            job.status = FAILED
            job.message = f"{label} was blocked by the workflow configuration."
        job.note(f"{label}: {status}" + (f" (QC {summary.get('qc_score')})" if summary.get("qc_score") else ""))

    def _pending_questions(self, job: Job, summary: dict[str, Any]) -> list[str]:
        state_file = self.store.workspace(job) / ".sdlc" / f"issue-{job.number}.json"
        with contextlib.suppress(OSError, ValueError):
            state = json.loads(state_file.read_text(encoding="utf-8"))
            questions = (state.get("pending_information") or {}).get("questions") or []
            if questions:
                return [str(q) for q in questions][:20]
        return [str(q) for q in ((summary.get("readiness") or {}).get("questions") or [])][:20]
