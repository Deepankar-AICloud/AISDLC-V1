# AISDLC Portal

A web front door and review desk for the AISDLC pipeline in this repository.

- **Requesters** enter the problem, objective, stakeholders, scope, constraints and success criteria in
  separate boxes, optionally add text or documents, preview the GitHub issue and submit. The portal creates
  the issue and then adds `sdlc:start`.
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
  Dockerfile  Dockerfile.studio  .env.example
```

Looking for a simple "sign in and generate documents" page with no GitHub accounts? See
[AISDLC Studio](#aisdlc-studio-shared-sign-in-no-github).

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

Requesters use **Requests → My requests** for their plain-language status and use the request ID page
for updates or follow-up information. Reviewer-only routes retain the technical workflow, audit log,
and GitHub details. Employee API responses are owner-scoped and omit engineering metadata.

## Shared login with the original GitHub Actions pipeline

The original, colourful portal also supports **username `admin` + a server-configured password**.
This is separate from Studio: it still creates a GitHub issue, adds `sdlc:start`, and follows the existing
GitHub Actions workflows. It does not run the Studio generator locally.

- The shared account is a **Requester**, not a privileged administrator. It can upload/paste requirements,
  and submit issues without a personal Microsoft/GitHub account.
- Named reviewers use **Sign in with GitHub** (or Microsoft if configured) for answers, model decisions,
  reviews and approvals. Repository access, CODEOWNERS, QC and production approval gates are unchanged.
- A personal GitHub account cannot be linked to the shared login. Requests share one owner and cannot be
  separated by employee; this is not customer/tenant isolation. Do not use it for unrelated customers'
  confidential data.
- Password-based shared sign-in cannot provide private employee request tracking; employee history and follow-up
  actions remain disabled for that mode. Use `AUTH_MODE=open` with per-request tracking keys, or configure
  individual Microsoft Entra sign-in for owner-scoped tracking.
- Password checks happen on the backend. Signed HttpOnly cookies, CSRF checks and sign-in rate limiting
  apply. No GitHub credentials or configured password are returned to the frontend.

### Local login with a real GitHub backend

First configure the GitHub App server-side as described below: `GITHUB_REPOSITORY`, `GITHUB_APP_ID`,
`GITHUB_APP_PRIVATE_KEY` or `GITHUB_APP_PRIVATE_KEY_PATH`, `GITHUB_APP_CLIENT_ID`, and
`GITHUB_APP_CLIENT_SECRET`. Install the App on the target repository. The installation ID is optional
(looked up if omitted). The workflows and repository protections must also be configured.
**Changing the login does not replace this backend authentication.** Missing settings stop startup;
there is no fallback to fake GitHub.

After those environment variables are available to the process:

```powershell
# Build the existing portal UI from the repository root.
Set-Location apps\intake-portal\frontend
npm run build
Set-Location ..\backend
$env:APP_ENV = 'development'
$env:AUTH_MODE = 'password'
$env:PORTAL_ADMIN_PASSWORD = 'admin'  # localhost-only demo; never deploy this password
$env:BIND_HOST = '127.0.0.1'
$env:PUBLIC_BASE_URL = 'http://localhost:8000'
$env:GITHUB_MODE = 'app'
$env:GITHUB_SIGNIN_ENABLED = 'true'
$env:SERVE_FRONTEND_DIR = (Resolve-Path ..\frontend\dist).Path
# Use a separate data directory from the fake-GitHub demo and Studio.
$env:DATA_DIR = '.\var\github-portal'
$env:DATABASE_URL = 'sqlite:///./var/github-portal/portal.db'
.\.venv\Scripts\python.exe -m uvicorn app.main:create_app --factory --host 127.0.0.1 --port 8000
```

Stop only the old original-portal server if port 8000 is occupied; **do not stop Studio on port 8001**.
Open http://localhost:8000 and sign in with `admin / admin`. The GitHub App callback for reviewers is
`http://localhost:8000/auth/github/callback`. Set `DEFAULT_REVIEWERS` if needed so a named reviewer can
handle the first model/information gate before a stage PR exists.

For hosted use, `APP_ENV=production` requires a password of at least 12 characters, HTTPS, a 32+ character
`SESSION_SECRET`, GitHub secrets, a token-encryption key, and process-isolated extraction. Entra credentials
are optional in password mode when GitHub reviewer sign-in is enabled. Use a strong unique password and
restrict ingress; do not expose `admin/admin` publicly. Supply secrets through the host's secure settings,
not this example file. Without `SESSION_SECRET` in local password mode, restarting invalidates sessions.

Validation: `pytest tests/test_password_signin.py` covers the login, shared/named identity boundary, and
the real App-authentication/API path with a mocked GitHub HTTP transport (not a live Actions run).

#### No sign-in page (`AUTH_MODE=open`)

To skip the login page entirely, use the same commands as above but set `AUTH_MODE=open` (and drop
`PORTAL_ADMIN_PASSWORD`; `GITHUB_SIGNIN_ENABLED` can be `false`). The page opens straight on
**New requirement**: the SPA calls `POST /auth/open-session`, which issues the normal signed session and
CSRF token for the shared `Requester` identity. No credentials or secrets reach the browser; GitHub
stays authenticated server-side by the App. Each submission receives a random private tracking key.
The browser saves that key locally to show **My requests** and load request details without exposing a
shared list to other visitors. Clearing browser data loses that list; only share a tracking key with
someone who should be able to view and respond to that request. Follow-up comments are posted by the
requester's linked GitHub identity; when using open access, contact IT with the request ID if a follow-up
is required. Reviews and approvals still happen on GitHub by named reviewers.

Open mode is rejected unless `APP_ENV` is `development`/`test` on loopback or, in production, the
operator confirms that an upstream IP allow-list restricts access. Anyone allowed through that
network restriction can submit requests; tracking details still require each request's private key.

For the isolated browser test (fake GitHub only):

```powershell
# From frontend after npm run build:
$env:E2E_AUTH_MODE = 'password'
npm run e2e -- password-login.spec.ts
Remove-Item Env:\E2E_AUTH_MODE
```

## AISDLC Studio (shared sign-in, no GitHub)

A separate, self-contained web app (`backend/app/studio`) for teammates and customers who just want to
paste or upload a requirement and get documents and code. There is one shared username/password, no
GitHub account, no issues and no pull requests.

1. Sign in, create a requirement (title + text and/or files: PDF, DOCX, Markdown, text…).
2. For each stage — **BRD → PRD → Epics & stories → Architecture → NFR → Tasks → Code** — Studio
   proposes a model, runs the matching AISDLC agent and shows the document with its QC score.
3. **Approve & continue**, **Request changes** (the stage is regenerated with your notes) or answer the
   agent's questions when it needs more information. Nothing advances without an approval, and a stage
   that fails QC cannot be approved (retry or request changes instead).
4. Read every document in the browser or **Download bundle** (ZIP of all artifacts and generated code).

How it works: each requirement gets its own shallow `git clone` of this repository under `DATA_DIR`.
The application template comes from committed `HEAD`; the generator is copied from the server's
`scripts/sdlc` directory when the workspace is created, including local runtime fixes. Existing jobs
retain their captured version. Studio runs the real orchestrator (`python -m scripts.sdlc.run` /
`approve`) in that workspace. Normal generation does not edit the source checkout, but a workspace
copy is not an OS security boundary. The AI calls go through the Copilot CLI (`copilot`) on the server;
the browser is not sent backend credentials.

The ZIP contains the requirement, generated Markdown documents, changed source files under
`code/files`, and a Git patch under `code/changes.patch`. It is a change bundle against the job's
application template, not a standalone copy of the entire application.

### Run locally (Windows PowerShell)

Requires the backend venv from the Quick start, git, and the Copilot CLI signed in (`copilot` → `/login`).
Code generation also needs the .NET 8 SDK and Node/npm for the SmartServe template's builds and tests.

```powershell
cd apps/intake-portal/backend
$env:STUDIO_PASSWORD = 'admin'          # shared sign-in password (username defaults to "admin")
$env:APP_ENV = 'development'
$env:PUBLIC_BASE_URL = 'http://localhost:8001'
.venv\Scripts\python -m uvicorn app.studio.main:create_studio_app --factory --host 127.0.0.1 --port 8001
```

Open http://localhost:8001 and sign in. Without `SESSION_SECRET` the cookie key is random per process,
so restarting Studio signs everyone out; set it (32+ random characters) to keep sessions across restarts.

### Container image and Azure

Build from the **repository root** (the image bakes the agents, config and orchestrator in as the job
source, plus git, Node 22, the .NET 8 SDK and the Copilot CLI for the Code stage):

```bash
docker build -f apps/intake-portal/Dockerfile.studio -t aisdlc-studio .
# Local container check; existing server-side environment variables supply credentials.
docker run --rm -p 127.0.0.1:8002:8000 -e APP_ENV=development \
  -e STUDIO_PASSWORD -e SESSION_SECRET -e COPILOT_GITHUB_TOKEN \
  -e PUBLIC_BASE_URL=http://localhost:8002 aisdlc-studio
```

Open http://localhost:8002 for this local container check. Do not use production HTTPS settings with
a plain-HTTP browser URL: the production session cookie requires HTTPS.
If your network requires package mirrors, pass credential-free `NPM_CONFIG_REGISTRY` and
`PIP_INDEX_URL` build arguments pointing at your approved mirrors. Do not disable TLS or hash checks.

- **Secrets** (`STUDIO_PASSWORD`, `SESSION_SECRET`, `COPILOT_GITHUB_TOKEN`) are runtime settings: App
  Service app settings (set by `azd up`, below), Key Vault references or a Kubernetes secret (AKS). Never
  bake them into the image or commit them.
  `COPILOT_GITHUB_TOKEN` is a fine-grained PAT of a user with a Copilot licence; Studio passes it only to
  the agent subprocess, and strips `STUDIO_PASSWORD`, `SESSION_SECRET` and `GITHUB_TOKEN` from it.
- **Single instance.** Jobs are files plus an in-process runner: run one App Service instance / one AKS
  replica, and keep `DATA_DIR` on persistent storage (App Service `/home`, an AKS persistent volume).
- **App Service:** use a Linux custom container, target port `8000` (`WEBSITES_PORT=8000` for the
  classic container configuration), Always On and health path `/healthz`. Restrict ingress before
  publishing the URL. Storage must be writable by the image's UID `10001`.
- **AKS:** use one replica, a persistent volume writable by UID `10001`, readiness/liveness probes on
  `/healthz:8000`, and a TLS ingress with a network allowlist. Never mount the Docker socket.
- Production (`APP_ENV=production`, the image default) refuses to start without an https
  `PUBLIC_BASE_URL` and a 32+ character `SESSION_SECRET`. TLS is terminated by App Service / ingress.
- Long stages (especially Code) can take many minutes; `STAGE_TIMEOUT_SECONDS` (default 3600) stops a
  run. The timeout kills the orchestrator process; tools it started may finish on their own.

### Deploy Studio to Azure App Service (azd)

[`azure.yaml`](../../azure.yaml) and [`infra/`](infra/) deploy Studio as a Linux custom container on App
Service (P1v3, one instance), with a Basic container registry that the app pulls from using a
user-assigned managed identity (no registry passwords) and a Log Analytics workspace for container,
HTTP and platform logs. The repository's root `infra/` folder belongs to SmartServe and is not used.

```powershell
# From the repository root. azd must be signed in to the subscription's tenant
# (azd auth login --tenant-id <tenant-id>, or reuse the Azure CLI: azd config set auth.useAzCliAuth true).
azd env new aisdlc-studio --subscription <subscription-id> --location centralindia
azd up    # builds Dockerfile.studio locally, pushes it, provisions rg-aisdlc-studio and deploys
```

- **Sign-in:** username `admin`. On first provision azd generates a 24-character password and the session
  key, keeps them only in `.azure/<env>/config.json` (gitignored) and sets them as App Service app
  settings. Read the password yourself rather than pasting it anywhere:
  `az webapp config appsettings list -g rg-aisdlc-studio -n <app-name> --query "[?name=='STUDIO_PASSWORD'].value" -o tsv`
- **AI mode:** without a token Studio runs in dry-run mode (`USE_LLM=false`): the pipeline, readiness
  questions and QC all work, but the offline placeholder documents fail QC by design, so real BRD/PRD/code
  needs a token. Run `azd env set COPILOT_GITHUB_TOKEN <token>` in your own terminal (a fine-grained PAT
  of a Copilot-licensed user with the *Copilot Requests* permission), then `azd up` again.
- **Blocked package registries:** if `registry.npmjs.org` or `files.pythonhosted.org` is blocked where you
  build, point the image build at approved credential-free mirrors (pip still verifies the lock-file
  hashes): `azd env set STUDIO_NPM_REGISTRY https://<mirror>/npm/` and
  `azd env set STUDIO_PIP_INDEX_URL https://<mirror>/pypi/simple/`.
- **Storage:** jobs, workspaces and the agent's `HOME` live on App Service's persistent `/home` share
  (`DATA_DIR=/home/studio-data`, and `STUDIO_HOME=/home/studio`, which the container start command exports
  as `HOME` because App Service doesn't allow an app setting named `HOME`), which counts toward the plan's 250 GB. There is
  no storage account or Key Vault: this subscription's policy turns off shared-key and public network
  access for them, so secrets are encrypted App Service app settings instead.
- **First deploy of a new environment:** the first provision has no image yet, so the site starts with a
  placeholder image that never passes the warm-up probe on port 8000. Studio can take up to 10 minutes
  (`WEBSITES_CONTAINER_START_TIME_LIMIT=600`) to come up after that first `azd up`; later deploys switch
  over in seconds.
- **Redeploying:** `azd deploy` rebuilds and pushes the image after code changes; use `azd up` (or
  `azd provision`) after changing `infra/` or `azd env` values.
- The image includes the working tree as it is when you run `azd up` (minus the ignored files above).
- `azd down` deletes the resource group, including every Studio job and download.

### Studio settings

| Variable | Default | Purpose |
|---|---|---|
| `STUDIO_USERNAME` | `admin` | Shared sign-in username |
| `STUDIO_PASSWORD` | *(required)* | Shared sign-in password — no default |
| `SESSION_SECRET` | random per process | Cookie signing key; required (32+ chars) in production |
| `PUBLIC_BASE_URL` | `http://localhost:8001` | Public URL; https enables `Secure` cookies |
| `DATA_DIR` | `var/studio` | Jobs, workspaces and artifacts (persistent storage in Azure) |
| `AISDLC_SOURCE_DIR` | this repository | Git repo with `scripts/sdlc` and `config` that jobs clone |
| `USE_LLM` | `true` | `false` runs the orchestrator's offline templates (no AI) |
| `ENABLE_CODE_STAGE` | `true` | `false` stops after Tasks (documents only) |
| `MAX_CONCURRENT_RUNS` | `1` | Stages run at the same time; others queue |
| `STAGE_TIMEOUT_SECONDS` | `3600` | Per-stage time limit |
| `COPILOT_GITHUB_TOKEN` | — | Copilot CLI auth on servers (locally the CLI uses your `/login`) |

### Studio safety notes

- **A shared password like `admin/admin` is only for your own machine.** Anyone who can reach Studio can
  sign in and spend the Copilot quota of the account behind it. Before exposing it, set a strong
  `STUDIO_PASSWORD` and restrict access (App Service access restrictions / private endpoint, AKS ingress
  allowlist, or Entra ID Easy Auth in front). Studio logs a warning at start-up when the password is weak.
- Everyone who signs in sees every requirement, so do not mix customers on one instance.
- The Code stage runs a tool-enabled AI agent with the server's OS identity. Workspace copies and the
  subprocess environment filter are not isolation from other files, jobs or processes. Use a disposable,
  access-restricted instance for trusted demo inputs. Public/untrusted multi-user hosting requires
  isolated workers and separate credentials; do not treat this shared-login demo as tenant isolation.
- Sign-in and actions are rate-limited; cookies are `HttpOnly`, `SameSite=Strict`, and every change needs
  a CSRF header (except sign-in and sign-out). Uploaded files are size-limited and parsed in a separate process.

Tests: `pytest tests/test_studio.py` covers both documents-only and code-enabled flows, login, server-only
credentials, quality gates and code downloads without AI calls. An opt-in live test consumes Copilot quota:

```powershell
# From backend, with Copilot CLI signed in and Node/npm available:
$env:RUN_STUDIO_LIVE_TEST = '1'
.venv\Scripts\python -m pytest tests\test_studio.py -k live_code_stage
Remove-Item Env:\RUN_STUDIO_LIVE_TEST
```

The live test seeds explicitly synthetic, pre-approved Architecture/Task fixtures in a disposable
workspace, then uses the real model gate, generator, build/test checks, QC, code download and approval
API. It verifies six behaviors in the generated TypeScript helper and exact source bytes in the ZIP.
It does not approve or modify customer jobs, and is not an end-to-end AI run of all document stages.

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
| Approve stage | `APPROVE` review on `sdlc/issue-N/<stage>`, or merge the PR | **user** | `artifact-review.yml` merges the PR (if needed), starts the next stage |
| Request changes | `/agent revise <notes>` comment on the PR | **user** | `feedback-handler.yml` |
| Other commands | `/agent regenerate\|rerun-qc\|explain\|status\|impact` | **user** | `feedback-handler.yml` |
| Confirm model | `/model approve` or `/model select <model> <reason>` on the issue | **user** | `feedback-handler.yml` (model job) |
| Approve production | `POST actions/runs/{id}/pending_deployments` | **user** | `deploy-production.yml` (`production` environment) |

Note: the gate removes `sdlc:start` once it dispatches, so its absence does not mean the request stalled.

### GitHub email notifications and stage progression

The workflow posts milestone updates as comments on the original issue: model recommendations, model
decisions and resumes, artifact pull requests ready for review, and stage approvals/next-stage starts.
GitHub generates the email wrapper and layout, like the notification in the example; SMTP settings are
not needed. GitHub sends these notifications according to each user's issue subscription and notification
settings. Because the portal bot opens the issue, the owner is not subscribed automatically, so the
model-confirmation comment @mentions the repository owner. Set the repository variable
`SDLC_NOTIFY_USERS` (for example `@alice @org/reviewers`) to mention different people. To receive the
email, enable **Email** for "Participating, @mentions and custom" at
https://github.com/settings/notifications and verify the default notification email address.

The generation sequence is BRD → PRD → EPIC → Architecture → NFR → Tasks → Code. It does not advance
immediately after generating the BRD. The BRD artifact pull request is the human gate: approving it
approves and merges that stage, then queues PRD. Merging the PR without an approving review is also
treated as approval and queues PRD. A PR that was approved and then merged advances only once. The same
approval gate applies to subsequent stages
that require review. Model confirmation is a separate gate before that stage's generation begins.

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

### Demo deploy with azd (no sign-in page, IP allow-list)

The root `azure.yaml` service `portal` deploys the portal to `aisdlc-studio-io` on the Studio plan, using
`AUTH_MODE=open` plus `OPEN_MODE_NETWORK_RESTRICTED=true`. The second setting is only safe because App
Service access restrictions deny every IP outside `PORTAL_ALLOWED_IPS`. Set values in the gitignored azd
environment (never commit them):

```powershell
azd env set PORTAL_ALLOWED_IPS "203.0.113.10/32,198.51.100.0/24"
azd env set PORTAL_GITHUB_REPOSITORY <owner>/<repo>
azd env set PORTAL_GITHUB_APP_ID <id>
azd env set PORTAL_GITHUB_APP_CLIENT_ID <client-id>
azd env set PORTAL_GITHUB_APP_CLIENT_SECRET <client-secret>
azd env set PORTAL_GITHUB_APP_PRIVATE_KEY_B64 ([Convert]::ToBase64String([IO.File]::ReadAllBytes("<key>.pem")))
azd env set PORTAL_TOKEN_ENCRYPTION_KEY <Fernet key>
azd provision; azd deploy portal
```

`SESSION_SECRET` and `GITHUB_WEBHOOK_SECRET` are generated by azd. To allow another IP, update
`PORTAL_ALLOWED_IPS` and run `azd provision` again.

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
