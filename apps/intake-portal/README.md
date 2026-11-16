# AISDLC Portal

A web front door and review desk for the AISDLC pipeline in this repository.

- **Requesters** paste a requirement, upload documents, preview the GitHub issue and submit. The portal
  creates the issue and then adds `sdlc:start`.
- **Requesters and assigned reviewers** answer AISDLC's questions (`sdlc:awaiting-info`) from the portal.
- **Reviewers** read the stage artifact (rendered Markdown and Mermaid), the diff, the QC scorecard and the
  model decision. They then approve, request changes, or send allowlisted `/agent` and `/model` commands.
- **Production reviewers** approve the protected `production` deployment with typed confirmation.

Every answer, review, approval and command is made with the signed-in person's **own GitHub account**. The
portal's service identity can only create the intake issue, add `sdlc:start`, post overflow continuation
comments, create `intake/*` branches, and read status. See [docs/architecture.md](docs/architecture.md)
for the design, data flow, two-token model, threat model and overflow decision.

```
apps/intake-portal/
  backend/    FastAPI app (app/), tests (tests/), pinned locks, scripts/
  frontend/   React + TypeScript (src/), Playwright e2e (e2e/)
  docs/       architecture.md, design-note.md
  Dockerfile  .env.example
```

## Quick start (local, no GitHub needed)

Development mode uses a built-in **fake GitHub** that simulates AISDLC (readiness questions, stage PRs,
approvals, production gate). Nothing touches a real repository.

```bash
cd apps/intake-portal/backend
python -m venv .venv && . .venv/bin/activate        # Windows: .venv\Scripts\activate
pip install -r requirements-dev.lock
export APP_ENV=development AUTH_MODE=dev GITHUB_MODE=fake BIND_HOST=127.0.0.1   # no .env file is read
export DEV_ADMIN_PASSWORD='choose-one'              # optional: enables the "admin" username/password sign-in
uvicorn app.main:create_app --factory --host 127.0.0.1 --port 8000 --reload
```

```bash
cd apps/intake-portal/frontend
npm ci
npm run dev                                          # http://127.0.0.1:5173 (proxies /api and /auth to :8000)
```

Settings come only from environment variables (see [`.env.example`](.env.example) for the full list).

Sign in as a development user (alice = Requester, bob = Reviewer and code owner, erin = production
reviewer), then use **Account → Connect GitHub** and pick the matching fake GitHub account.

## Tests

```bash
cd apps/intake-portal/backend && pytest                  # unit + API integration (GitHub mocked)
ruff check app tests && ruff format --check app tests && mypy app
pip-audit -r requirements.lock --require-hashes --strict
```

```bash
cd apps/intake-portal/frontend
npm run lint && npm run typecheck && npm test && npm run build
npx playwright install chromium && npm run e2e           # or PW_CHANNEL=msedge / chrome to use an installed browser
```

The Playwright run starts the backend itself (`backend/scripts/e2e_server.py`, fake GitHub, built
frontend). CI: [`.github/workflows/intake-portal-ci.yml`](../../.github/workflows/intake-portal-ci.yml).

## How the portal maps to AISDLC

| Portal action | GitHub effect | Identity | AISDLC workflow |
|---|---|---|---|
| Submit | create issue → `[Part k/n]` comments → add `sdlc:start` | service | `agentic-sdlc-codeql-gate.yml` → `agentic-sdlc.yml` |
| Answer questions | issue comment | **user** | gate resumes (needs `sdlc:awaiting-info`, CodeQL green) |
| Approve stage | `APPROVE` review on `sdlc/issue-N/<stage>` | **user** | `artifact-review.yml` merges the PR, starts the next stage |
| Request changes | `/agent revise <notes>` comment on the PR | **user** | `feedback-handler.yml` |
| Other commands | `/agent regenerate\|rerun-qc\|explain\|status\|impact` | **user** | `feedback-handler.yml` |
| Confirm model | `/model approve` or `/model select <model> <reason>` on the issue | **user** | `feedback-handler.yml` (model job) |
| Approve production | `POST actions/runs/{id}/pending_deployments` | **user** | `deploy-production.yml` (`production` environment) |

Note: the gate removes `sdlc:start` once it dispatches, so its absence does not mean the request stalled.

## Required GitHub protections (do this before using the portal for real)

These were checked against `Deepankar-AICloud/AISDLC-V1` on 2026-11-13. The portal is only as strong as
GitHub's own enforcement.

1. **Command injection in `feedback-handler.yml`: fixed in this change, pending merge.** Comment text
   used to be expanded into shell (`BODY="${{ github.event.comment.body }}"`, `--reason "${{ ... }}"`), and
   a multi-line comment could forge step outputs. It now reaches shell only through `env:`, only the first
   line is parsed, and only validated values are written to `$GITHUB_OUTPUT`.
   `backend/tests/test_feedback_workflow.py` runs the real scripts against hostile comments. Once this
   is on `main`, you can set `BLOCK_SHELL_METACHARACTERS=false`.
2. **Who can run `/agent` and `/model`: fixed in this change for `feedback-handler.yml`, pending merge.**
   A new `authorize` job requires write, maintain or admin access, checked through the permission API.
   Failures deny, and bots are refused. The CodeQL gate's resume path (`agentic-sdlc-codeql-gate.yml`)
   now requires **triage or higher** (`role_name`), so requesters with triage access can still answer
   questions, while outsiders, read-only users and bots cannot resume a run
   (`backend/tests/test_gate_workflow.py`). Give requesters who answer questions on GitHub at least triage
   access. `agentic-sdlc.yml` now adds only comments from **triage-or-higher** users to the AI's context
   (`backend/tests/test_context_workflow.py`), so outsiders cannot add text to a requirement.
   **Required:** set the repository variable `SDLC_TRUSTED_CONTEXT_BOTS` to the portal App's bot login
   (for example `aisdlc-portal[bot]`). Otherwise the portal's `[Part k/n]` continuation comments are
   dropped from the context. Only those comments are accepted from the bot.
3. **The repository is public.** Every submission is public. Make it private, or accept that, and keep `ALLOW_PUBLIC_REPO_UPLOADS=false`.
4. **Replace placeholder CODEOWNERS.** Every `@smartserve/*` team is reported as an unknown owner
   (`GET /repos/.../codeowners/errors`). A user-owned repository cannot have teams, so use individual
   logins or move the repository to an organisation. With `CODEOWNERS_POLICY=strict`, nobody gets an
   Approve button until this is fixed.
5. **Protect `main`** (branch protection or a ruleset): require a pull request with at least 1 approval,
   require review from Code Owners, dismiss stale approvals, require the CI status checks, and do not allow
   bypass (enforce for admins). Currently `main` has no protection, so GitHub enforces nothing.
6. **Create the `production` environment** with required reviewers (and "prevent self-review"). It does
   not exist today, so `deploy-production.yml` would run without any approval. The portal refuses
   production approvals until it exists.
7. **Harden `artifact-review.yml` (recommended).** It advances state and starts the next stage even when
   the merge fails, and never checks the approver. Check the reviewer's permission and stop when
   `gh pr merge` fails.
8. Keep "Allow GitHub Actions to create and approve pull requests" only if needed. Stage PRs are opened
   by `github-actions[bot]`, so a human can approve them.

## Create the GitHub App

GitHub → Settings → Developer settings → GitHub Apps → New GitHub App (for an organisation: Organisation
settings → GitHub Apps).

- **Homepage URL:** your portal URL. **Callback URL:** `https://<portal>/auth/github/callback`.
- Turn on **Expire user authorization tokens** (gives refresh tokens). Leave "Request user authorization
  during installation" off.
- **Webhook:** active, URL `https://<portal>/webhooks/github`, secret = `GITHUB_WEBHOOK_SECRET`.
- **Repository permissions:** Issues *read & write*; Pull requests *read & write* (user reviews need
  write, and the service token is down-scoped to read at runtime); Contents *read & write* (intake
  branches); Actions *read* (runs, environments, pending deployments); Deployments *read & write* (users
  approve the production deployment; the service token is down-scoped to read); Metadata *read*.
  Optional: Administration *read* (lets the pre-check read branch protection). Confirm these against
  GitHub's endpoint docs when you create the App; the deployment-review permission was not exercised
  against real GitHub.
- **Organisation permissions (optional):** Members *read* (team CODEOWNERS membership).
- **Subscribe to events:** Issues, Issue comment, Pull request, Pull request review, Workflow run,
  Deployment status.
- Install the App on the AISDLC repository only. Download a private key, and note the App ID, Client ID
  and Client secret.
- In the AISDLC repository, set the Actions variable `SDLC_TRUSTED_CONTEXT_BOTS` to `<app-slug>[bot]`
  (Settings → Secrets and variables → Actions → Variables), so continuation parts reach the agents.

User tokens are always limited to the intersection of the App's permissions and the user's own access,
so GitHub still enforces write access, CODEOWNERS and branch protection for every person.

## Sign in with GitHub (optional)

People without a Microsoft work account can sign in with GitHub when `GITHUB_SIGNIN_ENABLED=true`.
It is off by default; Entra ID remains the primary sign-in. The flow reuses the GitHub App's OAuth
settings (same callback URL). The rules:

- The GitHub user needs at least `GITHUB_SIGNIN_MIN_ROLE` (default **triage**) on the AISDLC repository,
  checked with the read-only service identity. Everyone else is refused with an explanation.
- Portal roles come from that repository role: everyone is a **Requester**, and users with **write** or
  more are also **Reviewers**. Roles are refreshed at every sign-in.
- The GitHub account becomes the portal identity and stays connected, so it cannot be disconnected.
- A GitHub account already linked to a Microsoft (Entra) user cannot be used to sign in to that account.
- Sign-ins and refusals are written to the audit log (`github_signin`).

## Register the portal in Entra ID

1. Entra admin center → App registrations → New registration. Single tenant. Redirect URI (Web):
   `https://<portal>/auth/callback`.
2. Certificates & secrets → New client secret (`ENTRA_CLIENT_SECRET`).
3. App roles → create `Requester` and `Reviewer` (allowed member types: Users/Groups). Assign them under
   Enterprise applications → the app → Users and groups.
4. Token configuration: the default ID token claims (`oid`, `name`, `preferred_username`, `roles`) are
   enough. No API permissions beyond `openid profile email`.
5. Set `ENTRA_TENANT_ID`, `ENTRA_CLIENT_ID`, `ENTRA_CLIENT_SECRET`. Users without either role are
   refused at sign-in.

## Secrets: GitHub Secrets, never files

The portal never reads a `.env` file and no secret is written in the code. For Azure, store secrets as
**environment secrets** in GitHub (Settings → Environments → `intake-portal`) and run
[`deploy-intake-portal.yml`](../../.github/workflows/deploy-intake-portal.yml). It checks they are all
present, then copies them into App Service settings. The workflow header lists every secret and variable it needs.
GitHub Secrets can only be read by workflows, so a portal running on your own machine cannot use them: set
the values you need in your shell instead.

## Environment variables

Every variable is documented in [`.env.example`](.env.example). In production the app refuses to start
without `SESSION_SECRET` (32+ characters), the Entra settings, `GITHUB_REPOSITORY`, the GitHub App ID,
key, client ID and secret, `GITHUB_WEBHOOK_SECRET` and `TOKEN_ENCRYPTION_KEY`, an `https`
`PUBLIC_BASE_URL`, and `EXTRACTION_ISOLATION=process`. `AUTH_MODE=dev` and `GITHUB_MODE=fake` cannot be
enabled in production.

## Deploy to Azure App Service (reference)

```bash
docker build -t <registry>.azurecr.io/aisdlc-portal:<tag> apps/intake-portal
docker push <registry>.azurecr.io/aisdlc-portal:<tag>
```

1. Create a Linux App Service plan (P1v3 or higher; extraction runs in child processes) and a Web App for
   Containers that pulls the image (managed identity with AcrPull).
2. Enable a system-assigned managed identity, grant it *Key Vault Secrets User*, and put secrets in Key
   Vault: `SESSION_SECRET`, `ENTRA_CLIENT_SECRET`, `GITHUB_APP_PRIVATE_KEY`, `GITHUB_APP_CLIENT_SECRET`,
   `GITHUB_WEBHOOK_SECRET`, `TOKEN_ENCRYPTION_KEY`, and the database password. Reference them from app
   settings as `@Microsoft.KeyVault(SecretUri=...)`.
3. App settings: `WEBSITES_PORT=8000`, `PUBLIC_BASE_URL=https://<app>.azurewebsites.net` (or your custom
   domain), `DATABASE_URL` (Azure Database for PostgreSQL recommended; the `postgres` extra is in the
   image), the Entra and GitHub values, and `GITHUB_REPOSITORY`.
4. Health check path: `/healthz`. HTTPS only: on. Minimum TLS 1.2. FTP: off.
5. Scaling out: drafts and pending submissions live in `DATA_DIR`. Either keep ARR affinity on (sticky
   sessions), or mount Azure Files at `DATA_DIR`. The in-memory rate limiter is per instance.
6. Point the GitHub App webhook at `https://<host>/webhooks/github`.

## Safety notes

- Do not upload secrets, credentials or regulated personal data unless that is approved for the
  repository. The UI shows this notice on the intake page.
- Use a **test repository** for the GitHub App until the protections above are in place. The portal's
  automated tests and e2e run only against the fake GitHub.
- Uploaded content is untrusted. It is extracted in a bounded worker, nothing embedded is executed,
  hidden text, comments and metadata are dropped where feasible, and likely prompt-injection phrases are
  flagged (not altered).
- Malware scanning is a hook (`MALWARE_SCAN_HOOK`), a no-op by default. Wire a real scanner for
  production.
