# AISDLC Portal — Design Note

> Status: approved 2026-11-13 (mocked GitHub only, no Entra/GitHub App yet, overflow parts posted by the
> service identity). Implemented as described, with these changes found while building:
> - Readiness is substring matching, so fixed headings would always satisfy it. Empty-field headings are
>   omitted, "Request ID" is shown as "Portal reference ID", and "Pasted requirement text" as "Pasted text".
> - Team code owners are stored as teams and resolved when a reviewer looks, so people who connect GitHub
>   later are still assigned.
> - The release-evidence workflow names are configurable (`PRODUCTION_EVIDENCE_WORKFLOWS`).
> See [architecture.md](architecture.md) for the current design.

Repo inspected: `Deepankar-AICloud/AISDLC-V1` (read-only `gh api` GETs and local files).

## 1. Discovery: what the pipeline actually does

### Verified as you described
- `sdlc:start` label starts the run (`agentic-sdlc-codeql-gate.yml`). CodeQL must have succeeded on the current `main` SHA, otherwise the gate comments "queued" and waits.
- Readiness gate (`config/readiness.yml`, `scripts/sdlc/readiness/__init__.py`): **keyword matching only**, no section parsing. BRD mandatory: problem / objective / stakeholders. Optional: scope / constraints. Minimum 25 chars. Missing mandatory info gives `AWAITING_REQUIRED_INFORMATION`, which adds `sdlc:awaiting-info` and posts a comment listing questions.
- Context = `TITLE + BODY + comments`, where comments are dropped only if the author login is `github-actions` / `github-actions[bot]` or the body starts with `/model ` or `/agent `. **Any other bot or App (`my-app[bot]`) counts as human.**
- Stage PR branch is `sdlc/issue-<n>/<agent>`, label `sdlc:review`. Because only `COPILOT_GITHUB_TOKEN` is set as a secret, `GH_TOKEN` falls back to `GITHUB_TOKEN`, so PRs are authored by `github-actions[bot]`. A human can therefore approve them.
- `artifact-review.yml`: any `approved` review on a PR whose head starts with `sdlc/issue-` runs `approve.py` (state transition), then `gh pr merge --squash` (failure swallowed with `||`), then dispatches the next stage. **It never checks the approver.**
- `deploy-production.yml`: `workflow_dispatch` with `confirm == 'promote'`, job uses `environment: production`.

### Differences / surprises
| # | Finding | Impact on portal |
|---|---|---|
| D1 | The CodeQL gate **removes `sdlc:start`** when it dispatches (`--remove-label sdlc:start`). | Status tracking cannot rely on that label being present. The portal records "submitted" itself and infers "running" from workflow runs and the label's `labeled`/`unlabeled` events. |
| D2 | Resume needs **all** of: issue open, label `sdlc:awaiting-info`, saved state artifact, CodeQL green on current `main`, non-bot author, body not starting with `/agent` or `/model`. An **issue body edit** by a non-bot also triggers resume. | Overflow comments posted *before* the `sdlc:start` label are safe (no `awaiting-info` yet). Answers must not start with `/`. |
| D3 | **Approving does not depend on the merge succeeding.** If `gh pr merge` fails (e.g. branch protection), the state has already advanced and the next stage is dispatched. | Real risk: an approval from someone who should not count (e.g. read-only on a public repo) still advances the pipeline. The pre-check in the portal is necessary but not sufficient; GitHub-side fixes are listed in section 5. |
| D4 | `/model` allowlist is `approve\|select\|compare\|status`; `/agent` is `revise\|regenerate\|rerun-qc\|explain\|status\|impact`. README lists a shorter set (stale). | Portal allowlist mirrors the workflow. |
| D5 | **Script injection in `feedback-handler.yml`**: `BODY="${{ github.event.comment.body }}"` and `--reason "${{ steps.cmd.outputs.reason }}"` are interpolated into shell. A comment such as `/agent revise "; <cmd>; "` runs arbitrary shell with `contents: write` and `COPILOT_GITHUB_TOKEN` in the job. | **High severity, independent of the portal.** The portal must not pass free text through unescaped, and the workflow should be fixed (use `env:` indirection). I will not touch it (your instruction) but recommend a fix PR. |
| D6 | Neither comment handler checks who is commenting (only `actor != github-actions[bot]`). | Anyone who can comment can run `/model approve|select` and `/agent regenerate`. On a **public** repo that is anyone on GitHub. |
| D7 | Orchestrator passes the whole context to the prompt. QC truncates source at 200k chars, upstream docs at 80k, there is no explicit context cap, and the Copilot CLI argv limit is unverified (`common/llm.py`). | Overflow design should keep the context well under a few hundred KB; I will cap total issue-visible content (see section 3). |

### GitHub protections (live state)
- **Repo is public**, user-owned (not an org), one collaborator (the owner, admin).
- **`main` has no branch protection and no rulesets.** Reviews are not required; owner/admin can bypass.
- **CODEOWNERS is all placeholders**: `@smartserve/architects|platform|backend|frontend|security`. `codeowners/errors` reports "Unknown owner" on every rule. A user-owned repo **cannot have teams at all**, so CODEOWNERS currently protects nothing.
- **No `production` environment exists** (only `dev`, `staging`, no protection rules). The production job would run **without any approval**, which contradicts the README and `environments.yml`. The portal's production approval cannot work until it is created with required reviewers.
- Workflow default permissions are `read`; "Allow Actions to create and approve PRs" is `true`.
- Secrets present: only `COPILOT_GITHUB_TOKEN`.

### Must be configured before the portal is safe
1. Make the repo private, or at least restrict who can comment/open issues (D6).
2. Fix the injection in `feedback-handler.yml` (D5), and add an `author_association` / permission check for `/agent` and `/model` (D6).
3. Create real CODEOWNERS (individual logins, or move the repo to an org with teams).
4. Branch protection / ruleset on `main`: require PR, ≥1 approval, require review from code owners, dismiss stale approvals, no admin bypass, require status checks.
5. Create the `production` environment with required reviewers (and "prevent self-review" if wanted).
6. Optionally make `artifact-review.yml` verify the reviewer's permission and abort before advancing state when merge fails (D3).
7. Install the GitHub App with a minimum permission set (section 2.4).

## 2. Design

### 2.1 Folder layout
```
apps/intake-portal/
  backend/  app/{api,core,auth,github,extract,intake,review,repo,audit}/ ; tests/
  frontend/ src/{pages,components,api}/ ; e2e/ (Playwright)
  docs/ (this note, architecture, threat model)
  Dockerfile  .env.example  README.md
  .github/ is NOT used; CI lives in .github/workflows/intake-portal-ci.yml (new file; existing workflows untouched)
```

### 2.2 Data model (SQLAlchemy, SQLite dev / Postgres or Azure SQL, repository layer)
- `users(id, entra_oid, email, display_name, role)`
- `github_links(user_id UNIQUE, github_id UNIQUE, github_login, token_enc, refresh_enc, expires_at, connected_at)`: one Entra user ↔ one GitHub account, both unique.
- `requests(id, requester_id, idempotency_key UNIQUE, repo, issue_number, status, stage, created_at, ...)`
- `request_files(request_id, name, size, sha256, pages, warnings_json)`: metadata only; extracted text is held transiently (or encrypted with TTL per retention policy).
- `assignments(request_id, reviewer_id)`
- `status_snapshots(request_id, labels, runs, prs, qc, awaiting_questions, updated_at)`
- `audit_log(id, ts, entra_oid, github_login, action, target_type, target_ref, github_status, portal_request_id, detail)`: no token values.
- `webhook_deliveries(delivery_id UNIQUE)` for replay protection.

### 2.3 API surface (all server-side authz)
`GET /healthz` · `POST /api/intake/preview` · `POST /api/requests` (Idempotency-Key) · `GET /api/requests` · `GET /api/requests/{id}` · `POST /api/requests/{id}/answer` · `GET /api/requests/{id}/stages/{pr}` (artifact, diff, QC, permission pre-check) · `POST …/approve` · `POST …/request-changes` · `POST …/command` (allowlist enum) · `POST …/model` · `GET/POST /api/production/{run}/…` · `GET /auth/login|callback`, `GET /auth/github/connect|callback` · `POST /webhooks/github` (HMAC verified) · pollers as background tasks.

### 2.4 Two-token model (one GitHub App)
- **Service (installation token)** → module `github/service_client.py` exposing only: `create_issue`, `add_label`, `commit_overflow_to_branch`, and read methods. It has **no** comment/review/approve methods. A test imports both clients and statically asserts that the service client class lacks those methods and that `/agent` / `/model` strings are only constructed in `user_client.py`.
- **User (user-to-server token via OAuth web flow)** → `github/user_client.py`: comment, review (`APPROVE`/`REQUEST_CHANGES`), `/agent`, `/model`, deployment review. Tokens encrypted at rest (Fernet / Key Vault key), short-lived with refresh, never leave the server.
- App permissions (minimum): Issues RW, Pull requests RW, Contents R (+W only for overflow branch, restricted to the `intake/*` prefix by app-side code), Actions R, Deployments RW, Metadata R, Checks/Statuses R. Webhooks: issues, issue_comment, pull_request, pull_request_review, workflow_run, deployment_status.
- Important: user-to-server tokens are bounded by both the App's permissions and the user's own access, so GitHub still applies write-access / CODEOWNERS / branch-protection normally.

### 2.5 Identity mapping
Entra `oid` is bound to the GitHub numeric `id` returned by `GET /user` at OAuth callback (not a typed-in login). Both columns unique. If the Entra user has no link, or the stored token is expired/revoked, every user-token action returns `409 github_not_linked` with a reason shown in the UI. No fallback identity exists in code.

### 2.6 Permission pre-check (before showing Approve)
For (PR, user): `GET /repos/.../collaborators/{login}/permission` (needs write/maintain/admin); PR author ≠ user; changed files via `GET pulls/{n}/files` matched against parsed CODEOWNERS (individual logins, or team membership when teams exist); branch-protection rules read via `branches/main/protection` and rulesets; result is a list of `{rule, satisfied, explanation}` so the UI explains hiding. The check is advisory, the real call is still made with the user's token and GitHub's error is surfaced verbatim. Note: with no protection today, "required code owner" checks degrade to "write access + not author". The UI will state that explicitly.

### 2.7 Production approval
`GET /repos/.../actions/runs/{id}/pending_deployments` → shows if `production` is pending and whether the user is among `reviewers`. Approve via `POST …/pending_deployments` with the **user token**, typed `promote`, evidence panel (CI/CodeQL/STAGING+DAST results pulled from workflow runs). Blocked outright if the environment does not exist (currently true).

### 2.8 Overflow strategy (decision)
Options: (A) split across follow-up human comments; (B) commit full text + originals to a non-`main` branch and link.

**Pick: hybrid, B-for-originals, A-for-extracted text.**
- Why not B-only: the orchestrator reads *only* issue title/body/comments (`gh issue view`), so a link is never fetched by the agent. Content in a branch is invisible to generation, i.e. effectively lost to the pipeline.
- Why not A-only: originals (binary files) can't go in comments, and very large documents bloat the prompt (D7).
- Design: body holds the structured sections plus per-file summary and first N chars of each file (budget ~60k chars). The rest of the extracted Markdown goes into numbered, human-attributed comments `[Part k/n of <file>]` (each ≤ 60k chars), posted **before** `sdlc:start`. Originals and full Markdown are committed to branch `intake/<request-id>` (never `main`, so CodeQL does not restart and no intake issue is created) and linked. Hard ceiling on total issue-visible text (default 400k chars, configurable); above it, the user is told which files to trim and the full text stays in the branch only, clearly flagged in the body.
- Comment author: the overflow comments are posted by the **service identity**, and the workflow accepts them as human context, which is what we want. This is the one case where a service comment is intended, and it stays on a separate method (`post_overflow_part`) that is hard-coded to the `[Part k/n …]` format, so it cannot carry `/agent`, `/model` or answers. Alternative if you prefer zero service comments: post them as the submitting user (requires connected GitHub at submit time). **Decision for you, see Q3.**
- Caveat: because filtering lets any non-`github-actions` bot through, the service bot's comments are "human". I flag this in the docs rather than patching the workflow.

### 2.9 Extraction & hardening (summary)
Bounded worker (subprocess pool, timeout, memory/size caps), extension + magic-byte allowlist, zip/OOXML decompression limits (ratio, entry count, total bytes), no macros/embedded objects executed, hidden text/comments/metadata stripped where feasible, injection-phrase detection as warnings only, pluggable malware-scan hook (no-op), OCR behind `FEATURE_OCR=false`. CSRF (double-submit token), strict CORS, security headers, per-user rate limit, request size limits, structured JSON logs with correlation id and secret redaction.

### 2.10 Auth
Entra ID OIDC (server-side session cookie, HttpOnly, SameSite=Lax). Roles from Entra app roles claims. `DEV_AUTH_BYPASS` is accepted only when `APP_ENV=development` **and** the bind address is loopback; the app refuses to start otherwise (tested).

## 3. Assumptions I could not verify
1. Whether the Copilot CLI/LLM can handle context larger than ~100–200k chars; `llm.py` is not read in full.
2. That `gh issue view --json comments` returns *all* comments (pagination) for very long threads.
3. Exact output shape of `outcome.json` and where QC scores/findings are stored for display (I assume PR body "AI Generation Summary" plus `reports/<run-id>/quality-report.md` on the PR branch; to be confirmed against a real run on a test repo).
4. How the questions for `awaiting-info` can be read: assumed from the orchestrator's bot comment `## ⛔ Generation blocked …` (parsed as data, rendered as plain text).
5. App registration details (Entra tenant, GitHub App) don't exist yet.
6. Whether stage PRs created by `GH_TOKEN` fallback stay bot-authored in your real setup (true today).

## 4. Constraints from the target repo to decide
- Public, personal repo, so no teams for CODEOWNERS and no one else to be a second reviewer. I recommend building and testing against **a separate private test repo** (or an org) with 2 collaborators.

## 5. Build order (each increment tested)
1 backend skeleton + extractors → 2 issue builder + service client → 3 status tracking → 4 frontend intake → 5 Entra sign-in → 6 GitHub connect + user client → 7 review/approval → 8 production approval → 9 hardening → 10 CI/docs → final report.
