from __future__ import annotations

import re
from pathlib import Path

import pytest
import yaml

from app.intake.issue_builder import (
    PART_HEADER_RE,
    ContentTooLargeError,
    DocumentText,
    IntakeContent,
    build_issue,
)

GITHUB_BODY_LIMIT = 65_536
REPO_ROOT = Path(__file__).resolve().parents[4]
BLOCK_RE = re.compile(r"\*\*UNTRUSTED SOURCE MATERIAL\*\* \((.+?), [\d,]+ characters\)\n\n(~{4,})text\n(.*?)\n\2", re.S)


def content(**kw) -> IntakeContent:
    base = dict(request_id="req_01TEST", title="Access portal", submitted_by="Alice Example")
    base.update(kw)
    return IntakeContent(**base)


def blocks(text: str) -> list[tuple[str, str]]:
    return [(m.group(1), m.group(3)) for m in BLOCK_RE.finditer(text)]


def reconstruct(plan, label: str) -> str:
    out = ""
    for lbl, txt in blocks(plan.body):
        if lbl == label:
            out += txt
    for c in plan.comments:
        for lbl, txt in blocks(c):
            if lbl == label:
                out += txt
    return out


def test_all_sections_when_fields_filled():
    plan = build_issue(
        content(
            business_problem="Tickets get lost.",
            objective="Track every ticket.",
            stakeholders="Service desk",
            scope="Phase 1 only",
            constraints="EU hosting",
            target_repository="org/app",
            pasted_text="Some pasted notes",
            documents=[DocumentText("a.pdf", "pdf", "pdf text", pages=1, warnings=["w1"])],
        )
    )
    for h in [
        "## Business problem",
        "## Objective",
        "## Stakeholders",
        "## Scope",
        "## Constraints",
        "## Target repository",
        "## Pasted text",
        "## Source documents",
        "### 1. a.pdf (PDF, 1 pages)",
        "## Submitted by",
        "## Portal reference ID",
    ]:
        assert h in plan.body, h
    assert "- w1" in plan.body
    assert plan.comments == [] and not plan.needs_branch
    assert "<!-- aisdlc-portal ref: req_01TEST -->" in plan.body
    labels = [lbl for lbl, _ in blocks(plan.body)]
    assert labels == [
        "business problem",
        "objective",
        "stakeholders",
        "scope",
        "constraints",
        "pasted text",
        "a.pdf (PDF, 1 pages)",
    ]


def test_empty_fields_are_omitted():
    plan = build_issue(content(pasted_text="hello"))
    assert "## Business problem" not in plan.body and "## Stakeholders" not in plan.body


def test_fence_cannot_be_broken_by_content():
    nasty = "start\n~~~~text\n~~~~~~\n## Fake heading\n```\nend"
    plan = build_issue(content(pasted_text=nasty))
    assert blocks(plan.body) == [("pasted text", nasty)]


def test_boilerplate_does_not_satisfy_readiness_gate():
    """With no business fields, the real readiness config must still find mandatory items missing."""
    cfg = yaml.safe_load((REPO_ROOT / "config" / "readiness.yml").read_text(encoding="utf-8"))
    plan = build_issue(
        content(
            title="Lorem ipsum",
            pasted_text="Lorem ipsum dolor sit amet, consectetur adipiscing elit.",
            documents=[DocumentText("notes.txt", "txt", "Lorem ipsum dolor.", warnings=[])],
        ),
        branch_name="intake/req_01TEST",
        originals={"notes.txt": b"x"},
    )
    ctx = f"TITLE: {plan.title}\n\nBODY:\n{plan.body}\n\nHUMAN COMMENTS:\n".lower()
    for item, kws in cfg["artifacts"]["brd"]["mandatory"].items():
        hits = [k for k in kws if k in ctx]
        assert hits == [], f"boilerplate satisfies readiness '{item}' via {hits}"


def test_two_hundred_page_document_overflows_without_loss():
    pages = [f"### Page {i}\n\n" + (f"Line of text for page {i}. " * 80) for i in range(1, 201)]
    text = "\n\n".join(pages)
    assert len(text) > 300_000
    doc = DocumentText("big.pdf", "pdf", text, pages=200)
    plan = build_issue(content(pasted_text="short", documents=[doc]), branch_name="intake/req_01TEST")
    assert len(plan.body) <= 60_000 < GITHUB_BODY_LIMIT
    assert plan.comments, "expected overflow comments"
    n = len(plan.comments)
    for k, c in enumerate(plan.comments, start=1):
        m = PART_HEADER_RE.match(c)
        assert m and int(m.group(1)) == k and int(m.group(2)) == n
        assert len(c) <= 60_000 < GITHUB_BODY_LIMIT
        assert not c.startswith("/")
    assert reconstruct(plan, "big.pdf (PDF, 200 pages)") == text
    assert reconstruct(plan, "pasted text") == "short"
    assert plan.needs_branch
    assert plan.branch_files["intake/req_01TEST/extracted/02-big.pdf__PDF__200_pages_.md"].decode() == text
    assert "Continued in comment part 1-" in plan.body


def test_many_documents_share_body_budget():
    docs = [DocumentText(f"d{i}.txt", "txt", f"doc {i} " * 3000) for i in range(10)]
    plan = build_issue(content(documents=docs), branch_name="intake/x")
    assert len(plan.body) <= 60_000
    for d in docs:
        assert reconstruct(plan, f"{d.filename} (TXT)") == d.text


def test_visible_cap_moves_rest_to_branch_only():
    doc = DocumentText("huge.txt", "txt", "word " * 100_000)
    plan = build_issue(content(documents=[doc]), max_visible_chars=150_000, branch_name="intake/x")
    assert plan.visible_chars <= 150_000
    assert plan.branch_only and plan.branch_only[0].branch_only_chars > 0
    assert "only in the intake branch" in plan.body
    assert plan.branch_files["intake/req_01TEST/extracted/01-huge.txt__TXT_.md"].decode() == doc.text


def test_visible_cap_without_branch_refuses_instead_of_losing_content():
    doc = DocumentText("huge.txt", "txt", "word " * 100_000)
    with pytest.raises(ContentTooLargeError):
        build_issue(content(documents=[doc]), max_visible_chars=150_000, branch_allowed=False)


def test_originals_are_placed_on_branch_when_allowed():
    plan = build_issue(
        content(documents=[DocumentText("a.docx", "docx", "t")]),
        branch_name="intake/req_01TEST",
        originals={"a.docx": b"PK.."},
    )
    assert plan.branch_files["intake/req_01TEST/originals/a.docx"] == b"PK.."
    assert "branch" in plan.body and all(p.startswith("intake/req_01TEST/") for p in plan.branch_files)


def test_title_is_trimmed():
    assert len(build_issue(content(title="x" * 500)).title) == 200
