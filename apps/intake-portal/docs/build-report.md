# AISDLC Portal: build report (2026-11-13)

## What was built

- `apps/intake-portal/backend`: FastAPI service.
  - Extraction: PDF, DOCX, PPTX, XLSX, CSV, TXT, MD, HTML and RTF. OCR for images is behind a flag, off by
    default. Files run in a bounded worker with type and size limits, zip-bomb guards, removal of hidden
    content, injection flagging and a malware-scan hook.
  - Issue builder with the hybrid overflow plan.
  - Idempotent, resumable submit (issue first, `sdlc:start` last).
  - Status tracking: webhook receiver (HMAC, replay dedupe) plus a poller.
  - Sign-in: Entra OIDC with PKCE, and a dev bypass locked to development.
  - GitHub connect: App user OAuth, tokens encrypted at rest, refresh handling.
  - Two identity-guarded GitHub clients.
  - Review service: approve with pre-check, request changes, allowlisted `/agent` and `/model`, answers.
  - Production approval through the deployment-review API.
  - Audit log, rate limits, CSRF, security headers, body cap and structured, redacted logs.
- `backend/app/github/fake.py`: in-memory GitHub plus a simulation of the AISDLC workflows (gate,
  readiness, stage PRs, artifact review, feedback handler, production gate), used by all tests and local
  development.
- `apps/intake-portal/frontend`: React and TypeScript. Pages: intake (paste, drag-and-drop, structured
  fields, completeness hint, per-file preview and editing, issue body preview), requests list, request
  status (questions and answer, model gate, stage timeline, audit), stage review (artifact with Mermaid,
  diff, QC, model, checks, confirmation dialog, commands), production, and account (connect GitHub).
- Delivery: `Dockerfile` (multi-stage, non-root, health check), `.env.example`, `README.md`,
  `docs/architecture.md`, CI workflow `.github/workflows/intake-portal-ci.yml`.
- No existing AISDLC agent, config or `src/` file was modified. Afterwards, at your request,
  `.github/workflows/feedback-handler.yml` was hardened:
  - comment text now reaches shell only through `env:`;
  - `$GITHUB_OUTPUT` injection is closed;
  - a new `authorize` job requires write access for `/agent` and `/model`.
  `tests/test_feedback_workflow.py` runs the real step scripts against hostile comments. The same harness
  showed that the previous version executed an injected command and accepted forged outputs.
- `.github/workflows/agentic-sdlc-codeql-gate.yml`: resuming a paused run (comment or body edit) now
  requires triage access or more, and bots are refused. `tests/test_gate_workflow.py` runs the real
  dispatch script with a stubbed `gh`. The previous version resumed for a read-only outsider and for
  `dependabot[bot]`.
- `.github/workflows/agentic-sdlc.yml` ("Fetch requirement context"): only comments from
  triage-or-higher users reach the agents. Bots listed in the repository variable
  `SDLC_TRUSTED_CONTEXT_BOTS` contribute only `[Part k/n]` comments. `tests/test_context_workflow.py`
  runs the real step. Previously every comment not written by GitHub Actions was included.

## What was verified (on this machine, Windows, Python 3.12.12, Node 26)

```
backend$ ruff check app tests scripts            -> All checks passed!
backend$ ruff format --check app tests scripts   -> 58 files already formatted
backend$ mypy app                                -> Success: no issues found in 46 source files
backend$ pytest --cov=app                        -> 119 passed, TOTAL coverage 86%
backend$ pip-audit -r requirements.lock --require-hashes --strict -> No known vulnerabilities found
frontend$ tsc -b && eslint src e2e               -> no errors
frontend$ vitest run                             -> 3 passed
frontend$ vite build                             -> built
frontend$ PW_CHANNEL=msedge playwright test      -> 4 passed
  ok 1 paste, upload PDF/DOCX/PPTX, preview and submit creates the issue, then labels it
  ok 2 AISDLC asks a question and the requester answers as themself
  ok 3 a code-owner reviewer reviews the artifact and approves under their own login
  ok 4 an unassigned reviewer cannot see or act on the request
frontend$ npm audit --omit=dev                   -> found 0 vulnerabilities
```

Acceptance criteria and the tests that cover them (all run against the mocked GitHub):

| Criterion | Test(s) |
|---|---|
| Paste + PDF/DOCX/PPTX → issue with all sections; `sdlc:start` added after content | `test_api_intake::test_paste_pdf_docx_pptx_submit_creates_issue_then_labels`, e2e 1 |
| Double submit → one issue | `test_double_submit_same_key…`, `test_concurrent_double_click…`, `test_same_content_different_key…`, e2e 1 (double-click) |
| 200-page document within 65,536 chars, no loss | `test_issue_builder::test_two_hundred_page_document_overflows_without_loss`, `test_api_intake::test_200_page_pdf_uses_overflow_without_loss` |
| Encrypted PDF, corrupt DOCX, oversized → clear errors | `test_extractors` (encrypted, corrupt, too_large, zip bomb, type mismatch…), `test_bad_files_give_clear_errors_without_crashing` |
| No cross-user access | `test_user_cannot_see_or_act_on_another_users_request`, `test_draft_belongs_to_its_owner`, e2e 4 |
| No token in responses, logs or bundle | `test_security::test_no_github_token_in_any_response_or_log`, `test_frontend_source_has_no_tokens_or_secrets`, `test_redaction` |
| Awaiting-info questions shown; answer posted as the user and resumes | `test_awaiting_info_questions_and_answer_posted_as_user`, e2e 2 |
| Approval shows artifact, diff, QC; needs confirmation; review under the user's login | `test_codeowner_reviewer_sees_artifact_and_approves_as_self`, e2e 3 |
| Non-owner, author or no write access → no Approve; forced call rejected | `test_non_qualifying_users_get_no_approve_and_forced_call_rejected` (3 cases), `test_github_rejection_is_relayed_verbatim_and_not_retried`, `test_github_rejects_self_approval_even_if_precheck_were_wrong` |
| Service token never comments, reviews, approves or sends commands | `test_github_clients` (guard denials, method absence, AST scan), `assert_bot_only_posted_parts` in review tests |
| Production: required reviewers only, typed confirmation, never the service identity | `test_production_approval_only_by_required_reviewer_with_typed_confirmation`, `test_production_blocked_when_environment_missing` |
| Audit entry for every action | audit assertions in the review and production tests (`entra_oid`, GitHub login, target, outcome, request id) |

## What was not verified

- **Real GitHub and real Entra ID.** No GitHub App or Entra registration exists yet, and per your
  instruction nothing ran against a real repository. Unexercised against real services:
  - the App JWT and installation-token exchange, including the down-scoped `permissions` request;
  - user OAuth and refresh;
  - real webhook payloads;
  - the exact App permissions needed for deployment review;
  - GitHub's real error texts;
  - search-index lag for the retry recovery path;
  - Entra's token endpoint.
  Entra ID token validation is unit-tested with locally signed tokens.
- **Docker image build.** The Docker daemon was not running here. The CI `container` job builds the image
  and checks that production settings fail closed without secrets.
- **CI workflow.** Not run (not pushed). `npm ci` from the public registry was not exercised locally: the
  lock's download URLs were rewritten from the local mirror to `registry.npmjs.org`, and the integrity
  hashes are unchanged.
- **The process-isolation memory cap** (`RLIMIT_AS`) only applies on Linux. On Windows only the timeout
  applies (tested).
- **OCR path** (feature flag off; Tesseract not installed).
- **PostgreSQL / Azure SQL.** Only SQLite was exercised. No migrations: tables are created at startup.

## Known limitations

- The readiness gate's substring matching means that real document content (for example the word
  "request") often satisfies it. The portal keeps its own boilerplate neutral, but cannot make the gate
  stricter. Consider section-aware readiness in AISDLC.
- With today's repository settings (no branch protection, placeholder CODEOWNERS, no `production`
  environment, public repo; the workflow fixes in this change are not merged yet),
  GitHub enforces nothing. See README "Required GitHub protections". With `CODEOWNERS_POLICY=strict`,
  nobody gets an Approve button until CODEOWNERS names real owners.
- Rate limiting and the webhook dedupe table are per instance. Drafts and pending plans live on local disk:
  use sticky sessions or Azure Files when scaling out.
- `artifact-review.yml` advances the pipeline on any approval even if the merge fails. The portal's
  pre-check cannot fix that.
- The issue-body preview does not re-render live after editing extracted text. Edits are applied on submit
  and noted in the issue.
- 7 moderate npm advisories remain in the dev-only `typescript-eslint` toolchain (minimatch). Runtime
  dependencies have none.
- The package mirror used here returned MD5 hashes. `scripts/lock.py` regenerates the Python locks with
  SHA-256 hashes only.
