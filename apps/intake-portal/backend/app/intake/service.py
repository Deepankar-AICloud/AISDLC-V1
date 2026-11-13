"""Preview and submit.

Submit order (resumable; each step is recorded so a retry continues where it stopped):
  1. intake branch (only when needed; never main)
  2. create the issue (service identity; recovery searches for the hidden ref marker first)
  3. overflow `[Part k/n]` comments, in order
  4. add `sdlc:start` as a separate, final call, so the pipeline starts only after all content exists
"""

from __future__ import annotations

import hashlib
import json
import logging
import secrets
import shutil
from datetime import timedelta
from pathlib import Path
from typing import Any

from sqlalchemy import select, update
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from ..audit import record
from ..container import Container
from ..db import Draft, IntakeRequest, User, utcnow
from ..errors import ApiError
from ..extract import ExtractionError, Limits, run_extraction, scan_file
from ..github.http import GitHubError
from .issue_builder import ContentTooLargeError, DocumentText, IntakeContent, build_issue
from .readiness import completeness

log = logging.getLogger(__name__)
FIELDS = ["title", "business_problem", "objective", "stakeholders", "scope", "constraints", "target_repository"]


def new_id(prefix: str) -> str:
    return f"{prefix}_{utcnow().strftime('%y%m%d')}{secrets.token_hex(6)}"


def clean_fields(raw: dict[str, Any]) -> dict[str, str]:
    out: dict[str, str] = {}
    for k in FIELDS:
        v = str(raw.get(k) or "").replace("\r\n", "\n").strip()
        limit = 200 if k in ("title", "target_repository") else 4000
        if len(v) > limit:
            raise ApiError(422, "field_too_long", f"'{k.replace('_', ' ')}' is limited to {limit} characters.")
        out[k] = v
    return out


class IntakeService:
    def __init__(self, c: Container) -> None:
        self.c = c
        self.s = c.settings
        self.limits = Limits.from_settings(self.s)

    # ------------------------------------------------------------ drafts
    def _draft_dir(self, draft_id: str) -> Path:
        return self.s.data_dir / "drafts" / draft_id

    def purge_expired_drafts(self, db: Session) -> int:
        expired = db.scalars(select(Draft).where(Draft.expires_at < utcnow())).all()
        for d in expired:
            shutil.rmtree(self._draft_dir(d.id), ignore_errors=True)
            db.delete(d)
        db.commit()
        return len(expired)

    def _load_draft(self, db: Session, user: User, draft_id: str) -> tuple[Draft, dict[str, Any]]:
        d = db.get(Draft, draft_id)
        if d is None or d.user_id != user.id:
            raise ApiError(404, "draft_not_found", "This preview has expired. Upload the files again.")
        if d.expires_at < utcnow():
            raise ApiError(410, "draft_expired", "This preview has expired. Upload the files again.")
        return d, json.loads(self.c.cipher.decrypt(d.payload_enc))

    def preview(
        self, db: Session, user: User, fields_raw: dict[str, Any], pasted: str, uploads: list[tuple[str, bytes]]
    ) -> dict[str, Any]:
        self.purge_expired_drafts(db)
        fields = clean_fields(fields_raw)
        if len(pasted) > self.s.max_pasted_chars:
            raise ApiError(422, "pasted_too_long", f"Pasted text is limited to {self.s.max_pasted_chars:,} characters.")
        if len(uploads) > self.s.max_files:
            raise ApiError(422, "too_many_files", f"Upload at most {self.s.max_files} files at a time.")
        total = sum(len(d) for _, d in uploads)
        if total > self.s.max_total_bytes:
            raise ApiError(
                413,
                "total_too_large",
                f"Files total {total // (1024 * 1024)} MB; the limit is {self.s.max_total_bytes // (1024 * 1024)} MB.",
            )
        draft_id = new_id("drf")
        ddir = self._draft_dir(draft_id)
        ddir.mkdir(parents=True, exist_ok=True)
        files: list[dict[str, Any]] = []
        for idx, (name, data) in enumerate(uploads):
            fid = f"f{idx + 1}"
            entry: dict[str, Any] = {
                "id": fid,
                "filename": name[:200],
                "size": len(data),
                "sha256": hashlib.sha256(data).hexdigest(),
            }
            try:
                scan_file(self.s.malware_scan_hook, name, data)
                res = run_extraction(
                    name,
                    data,
                    self.limits,
                    isolation=self.s.extraction_isolation,
                    timeout=self.s.extraction_timeout_seconds,
                    memory_mb=self.s.extraction_memory_mb,
                )
                entry.update(res.to_dict())
                entry["filename"] = res.filename
                entry["error"] = None
                (ddir / fid).write_bytes(self.c.cipher.encrypt(data))
            except ExtractionError as exc:
                entry.update(
                    {
                        "error": {"code": exc.code, "message": exc.message},
                        "text": "",
                        "warnings": [],
                        "injection_flags": [],
                        "kind": "",
                        "chars": 0,
                    }
                )
            files.append(entry)
        payload = {"fields": fields, "pasted": pasted, "files": files}
        db.add(
            Draft(
                id=draft_id,
                user_id=user.id,
                payload_enc=self.c.cipher.encrypt(json.dumps(payload).encode()),
                expires_at=utcnow() + timedelta(minutes=self.s.draft_ttl_minutes),
            )
        )
        db.commit()
        result = self._preview_response(user, draft_id, fields, pasted, files, None)
        return result

    def _content(
        self, user: User, ref: str, fields: dict[str, str], pasted: str, files: list[dict[str, Any]]
    ) -> IntakeContent:
        docs = [
            DocumentText(
                f["filename"],
                f["kind"],
                f["text"],
                f.get("pages"),
                f.get("slides"),
                f.get("sheets"),
                list(f.get("warnings") or []),
            )
            for f in files
            if not f.get("error")
        ]
        return IntakeContent(
            request_id=ref,
            title=fields.get("title") or self._title(fields, pasted, docs),
            submitted_by=user.display_name or user.email or "portal user",
            business_problem=fields.get("business_problem", ""),
            objective=fields.get("objective", ""),
            stakeholders=fields.get("stakeholders", ""),
            scope=fields.get("scope", ""),
            constraints=fields.get("constraints", ""),
            target_repository=fields.get("target_repository", ""),
            pasted_text=pasted,
            documents=docs,
        )

    @staticmethod
    def _title(fields: dict[str, str], pasted: str, docs: list[DocumentText]) -> str:
        for candidate in (fields.get("business_problem", ""), pasted, docs[0].filename if docs else ""):
            line = candidate.strip().splitlines()[0] if candidate.strip() else ""
            if line:
                return line[:120]
        return "Untitled submission"

    def _branch_allowed(self) -> bool:
        if not self.s.overflow_branch_enabled:
            return False
        info = self.c.repo_info()
        return info.get("private") is True or self.s.allow_public_repo_uploads

    def _plan(self, content: IntakeContent, originals: dict[str, bytes]) -> Any:
        branch = f"intake/{content.request_id}"
        allowed = self._branch_allowed()
        url = f"{self.s.github_web_url.rstrip('/')}/{self.c.repository}/tree/{branch}"
        return build_issue(
            content,
            body_budget=self.s.issue_body_budget,
            comment_budget=self.s.issue_comment_budget,
            max_visible_chars=self.s.max_issue_visible_chars,
            branch_name=branch if allowed else "",
            branch_url=url,
            branch_allowed=allowed,
            originals=originals if (allowed and self.s.upload_originals) else {},
        )

    def _preview_response(
        self,
        user: User,
        draft_id: str,
        fields: dict[str, str],
        pasted: str,
        files: list[dict[str, Any]],
        included: list[dict[str, Any]] | None,
    ) -> dict[str, Any]:
        ok_files = [f for f in files if not f.get("error")]
        content = self._content(user, "PREVIEW", fields, pasted, included if included is not None else ok_files)
        plan_error = None
        plan_info: dict[str, Any] = {}
        try:
            plan = self._plan(content, {f["filename"]: b"" for f in ok_files})
            plan_info = {
                "title": plan.title,
                "body": plan.body,
                "overflow_comments": len(plan.comments),
                "overflow_preview": [c[:1500] for c in plan.comments[:3]],
                "visible_chars": plan.visible_chars,
                "uses_branch": plan.needs_branch,
                "placements": [p.__dict__ for p in plan.placements],
            }
        except ContentTooLargeError as exc:
            plan_error = str(exc)
        joined = "\n".join([*fields.values(), pasted, *[f["text"] for f in ok_files]])
        return {
            "draft_id": draft_id,
            "files": files,
            "issue": plan_info,
            "plan_error": plan_error,
            "completeness": completeness(fields, joined),
            "repository": self.c.repo_info(),
        }

    # ------------------------------------------------------------ submit
    def submit(self, db: Session, user: User, body: dict[str, Any], client_key: str) -> tuple[IntakeRequest, bool]:
        if not client_key or len(client_key) > 100:
            raise ApiError(400, "idempotency_key_required", "Missing Idempotency-Key header.")
        draft, payload = self._load_draft(db, user, str(body.get("draft_id", "")))
        fields = clean_fields(body.get("fields") or payload["fields"])
        pasted = body.get("pasted_text")
        pasted = str(payload["pasted"] if pasted is None else pasted)
        if len(pasted) > self.s.max_pasted_chars:
            raise ApiError(422, "pasted_too_long", "Pasted text is too long.")
        edits = {e["id"]: e for e in body.get("files", []) if isinstance(e, dict) and "id" in e}
        chosen: list[dict[str, Any]] = []
        for f in payload["files"]:
            e = edits.get(f["id"], {})
            if f.get("error") or e.get("include") is False:
                continue
            f = dict(f)
            if isinstance(e.get("text"), str):
                if len(e["text"]) > self.s.max_extracted_chars_per_file:
                    raise ApiError(422, "text_too_long", f"Edited text for {f['filename']} is too long.")
                if e["text"] != f["text"]:
                    f["warnings"] = [*f.get("warnings", []), "Text was edited by the submitter before sending."]
                f["text"] = e["text"]
            chosen.append(f)
        if not pasted.strip() and not chosen and not any(fields[k] for k in FIELDS if k != "title"):
            raise ApiError(422, "empty_submission", "Paste some text, fill a field or upload a document.")

        key = hashlib.sha256(f"{user.id}:{client_key}".encode()).hexdigest()
        content_hash = hashlib.sha256(
            json.dumps(
                {"f": fields, "p": pasted, "d": [(f["sha256"], f["text"]) for f in chosen]}, sort_keys=True
            ).encode()
        ).hexdigest()
        existing = db.scalar(select(IntakeRequest).where(IntakeRequest.idempotency_key == key))
        if existing:
            return existing, False
        window = utcnow() - timedelta(minutes=self.s.idempotency_window_minutes)
        dup = db.scalar(
            select(IntakeRequest).where(
                IntakeRequest.requester_id == user.id,
                IntakeRequest.content_hash == content_hash,
                IntakeRequest.created_at >= window,
            )
        )
        if dup:
            return dup, False

        req_id = new_id("req")
        content = self._content(user, req_id, fields, pasted, chosen)
        originals = {
            f["filename"]: self.c.cipher.decrypt((self._draft_dir(draft.id) / f["id"]).read_bytes())
            for f in chosen
            if (self._draft_dir(draft.id) / f["id"]).exists()
        }
        try:
            plan = self._plan(content, originals)
        except ContentTooLargeError as exc:
            raise ApiError(422, "content_too_large", str(exc)) from exc

        req = IntakeRequest(
            id=req_id,
            requester_id=user.id,
            idempotency_key=key,
            content_hash=content_hash,
            title=plan.title,
            repository=self.c.repository,
            status="submitting",
            submit_step="pending",
            overflow_parts_total=len(plan.comments),
            overflow_branch=f"intake/{req_id}" if plan.needs_branch else "",
            files_meta=[
                {
                    k: f.get(k)
                    for k in ("filename", "kind", "size", "sha256", "pages", "slides", "sheets", "chars", "warnings")
                }
                for f in chosen
            ],
        )
        db.add(req)
        try:
            db.commit()
        except IntegrityError:
            db.rollback()  # a concurrent double-click won the race
            winner = db.scalar(select(IntakeRequest).where(IntakeRequest.idempotency_key == key))
            if winner is None:
                raise
            return winner, False
        self._stash_plan(req_id, plan)
        self.run_submit(db, user, req)
        if req.status != "submit_failed":
            db.delete(draft)
            db.commit()
            shutil.rmtree(self._draft_dir(draft.id), ignore_errors=True)
        return req, True

    # The plan is kept (encrypted) until submit completes so a retry can resume.
    def _plan_path(self, req_id: str) -> Path:
        return self.s.data_dir / "pending" / f"{req_id}.bin"

    def _stash_plan(self, req_id: str, plan: Any) -> None:
        p = self._plan_path(req_id)
        p.parent.mkdir(parents=True, exist_ok=True)
        data = {
            "title": plan.title,
            "body": plan.body,
            "comments": plan.comments,
            "branch_files": {k: v.hex() for k, v in plan.branch_files.items()},
        }
        p.write_bytes(self.c.cipher.encrypt(json.dumps(data).encode()))

    def _load_plan(self, req_id: str) -> dict[str, Any]:
        p = self._plan_path(req_id)
        if not p.exists():
            raise ApiError(409, "plan_missing", "The submission content is no longer available; submit again.")
        return json.loads(self.c.cipher.decrypt(p.read_bytes()))

    def run_submit(self, db: Session, user: User, req: IntakeRequest) -> None:
        is_retry = req.submit_step != "pending"
        result = db.execute(
            update(IntakeRequest)
            .where(
                IntakeRequest.id == req.id,
                IntakeRequest.submit_step != "running",
                IntakeRequest.status.in_(["submitting", "submit_failed"]),
            )
            .values(submit_step="running", status="submitting")
        )
        claimed = getattr(result, "rowcount", 0)  # atomic claim: only one submit pipeline runs at a time
        db.commit()
        if not claimed:
            return
        db.refresh(req)
        plan = self._load_plan(req.id)
        svc = self.c.service
        step = "branch"
        try:
            if req.overflow_branch and plan["branch_files"]:
                files = {k: bytes.fromhex(v) for k, v in plan["branch_files"].items()}
                svc.create_intake_branch(
                    req.overflow_branch,
                    self.s.github_base_branch,
                    files,
                    f"chore(intake): source material for {req.id} [skip ci]",
                )
                plan["branch_files"] = {}
            step = "issue"
            if req.issue_number is None:
                # On a retry, an earlier attempt may have created the issue before failing.
                found = svc.find_issue_by_ref(req.id) if is_retry else None
                issue = found or svc.create_issue(plan["title"], plan["body"])
                req.issue_number = int(issue["number"])
                req.issue_url = issue.get("html_url", "")
                db.commit()
                record(
                    db,
                    user=user,
                    github_login="(service)",
                    identity="service",
                    action="issue_create",
                    target_type="issue",
                    target_ref=f"#{req.issue_number}",
                    outcome="ok",
                    github_status=201,
                    request_id=req.id,
                )
            step = "overflow"
            for i in range(req.overflow_parts_posted, len(plan["comments"])):
                svc.post_overflow_part(req.issue_number, plan["comments"][i])
                req.overflow_parts_posted = i + 1
                db.commit()
            if plan["comments"]:
                record(
                    db,
                    user=user,
                    github_login="(service)",
                    identity="service",
                    action="overflow_parts",
                    target_type="issue",
                    target_ref=f"#{req.issue_number}",
                    outcome="ok",
                    request_id=req.id,
                    detail=f"{len(plan['comments'])} part(s)",
                )
            step = "label"
            svc.add_start_label(req.issue_number)
            record(
                db,
                user=user,
                github_login="(service)",
                identity="service",
                action="label_sdlc_start",
                target_type="issue",
                target_ref=f"#{req.issue_number}",
                outcome="ok",
                request_id=req.id,
            )
            req.submit_step = "done"
            req.status = "submitted"
            req.error = ""
            req.updated_at = utcnow()
            db.commit()
            self._plan_path(req.id).unlink(missing_ok=True)
        except GitHubError as exc:
            req.submit_step = step
            req.status = "submit_failed"
            req.error = f"GitHub refused the {step} step: {exc.message}"
            req.updated_at = utcnow()
            db.commit()
            record(
                db,
                user=user,
                github_login="(service)",
                identity="service",
                action=f"submit_{step}",
                target_type="issue",
                target_ref=f"#{req.issue_number or '-'}",
                outcome="error",
                github_status=exc.status,
                request_id=req.id,
                detail=exc.message,
            )
