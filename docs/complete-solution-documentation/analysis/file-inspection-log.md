# File Inspection Log

Version 1.0 analysis 2026-11-03 at commit `605e414`. Version 2.0 update 2026-11-04 at commit `6429a22` (342 tracked files, including the documentation sets) plus the uncommitted working-tree fixes noted in the main document. Rows below reflect version 2.0; platform and documentation rows were re-checked against the diff and unchanged files kept their version 1.0 inspection.

**Inspection depth:**
- **Full:** the file was read in full and verified by hand.
- **Research:** the file was read by a read-only research pass, with key facts re-verified.
- **Listed:** the file was inventoried only (generated or third-party content).

## Application — `src/`

| File | Depth | Key facts used |
|---|---|---|
| `src/backend/SmartServe.Api/Program.cs` | Full | Key Vault provider, App Insights, JWT/Test auth, fallback + 9 policies, DbContextFactory rule, Graph vs in-memory services, CORS, migrations, seeding, reconciliation, Auditor write-block, authorized `/health` |
| `src/backend/SmartServe.Api/Controllers/RequestsController.cs` | Full | 6 actions, own-request filter, workflow delegation, no routed-manager check |
| `src/backend/SmartServe.Api/Controllers/RequestTypesController.cs` | Full | List/create/update/deactivate, one-way deactivation |
| `src/backend/SmartServe.Api/Controllers/AuditController.cs`, `SecurityReviewController.cs` | Full / research | Paging (50/200), read-all, access-only |
| `src/backend/SmartServe.Api/Services/WorkflowService.cs` | Full | Transitions, audit in the same SaveChanges, concurrency, routing, notes unused |
| `src/backend/SmartServe.Api/Services/NotificationService.cs`, `NotificationReconciliationService.cs`, `Email/*`, `Directory/*` | Research + targeted reads | Outcomes, 15-minute lease, 5-minute reconciliation, Graph endpoints, sender default |
| `src/backend/SmartServe.Api/Domain/*.cs`, `Dtos/RequestDtos.cs` | Research | Entities, enums, roles, DTO limits |
| `src/backend/SmartServe.Api/Data/*.cs`, `Migrations/20261103093414_InitialPortalRequestModel.cs` | Research + targeted reads | Indexes, conversions, concurrency tokens, seed data, single foreign key |
| `src/backend/SmartServe.Api/SmartServe.Api.csproj`, `appsettings.json`, `appsettings.Development.json` | Research + full (`appsettings.json`) | Package versions; setting names; audience placeholder (removed) |
| `src/backend/SmartServe.Tests/*` | Research + executed | 26 methods / 32 cases listed and run |
| `src/backend/SmartServe.sln`, `build-release.log`, `test-release.log` | Research | Solution; stale logs |
| `src/frontend/src/main.tsx`, `api.ts`, `auth.ts` | Full | Sign-in gate, token fallback, scope |
| `src/frontend/src/App.tsx`, `features/admin-request-types/AdminRequestTypesPage.tsx` | Research + targeted reads | Screens and API calls used |
| `src/frontend/src/**/__tests__/*` | Research | 5 tests |
| `src/frontend/package.json`, `package-lock.json`, `tsconfig.json`, `vite.config.ts`, `.eslintrc.cjs`, `.env.example` | Research | Dependency versions, scripts, proxy, variable names |

## Infrastructure and CI/CD

| File | Depth | Key facts used |
|---|---|---|
| `infra/main.bicep` | Full | All resources, private networking, identity, settings, RBAC, outputs |
| `infra/*.parameters.json` | Full | Environment name and base name only (Entra IDs from the pipeline) |
| `infra/scripts/setup-dev.ps1` | Full | One-time identity, Entra and GitHub setup |
| `.github/workflows/ci.yml`, `security.yml`, `deploy-dev.yml`, `deploy-staging.yml`, `deploy-production.yml`, `test.yml` | Full | Stages, gates, permissions, secret and variable names, `STAGING_ENABLED` switch |
| `.github/workflows/agentic-sdlc.yml`, `agentic-sdlc-codeql-gate.yml`, `artifact-review.yml`, `feedback-handler.yml` | Research + targeted reads | SDLC flow, hand-off comment, `[skip ci]` rule, interpolation finding (feedback-handler L34/L98, still present) |
| `.github/workflows/deploy.yml`, `automate_pr.yml`, `gatekeeper.yml`, `council-query.yml`, `feature-requirement-analysis.yml`, `cast-feature-impact.yml`, `cast-imaging-analyzer.yml`, `azure-resource-analysis.yml`, `daily-repo-status.lock.yml`, `daily-repo-status.md` | Research + targeted pattern scan | Legacy/auxiliary classification; interpolation and pinning scan |
| `.github/CODEOWNERS` | Full | Placeholder teams |
| `.github/copilot-instructions.md`, `.github/copilot-setup-steps.yaml`, `.github/aw/actions-lock.json` | Research | Project context; legacy setup steps |

## Agentic SDLC platform

| File | Depth | Key facts used |
|---|---|---|
| `config/agents.yml`, `config/models.yml`, `config/quality-gates.yml`, `config/budgets.yml`, `config/environments.yml`, `config/model-routing.yml`, `config/pricing.yml`, `config/impact-rules.yml`, `config/readiness.yml` | Full | Agent registry, routing, gates, budgets, environments |
| `config/contracts/*.yml` (8 files) | Research (`code.yml` full) | Required outputs and ID prefixes |
| `scripts/sdlc/orchestrator/__init__.py`, `states.py`, `state_store.py` | Full / research | Stage loop, prompt build, Code-stage tooling, state fields, state mapping, `PIPELINE_STATES` hand-off |
| `scripts/sdlc/quality/__init__.py`, `diagnosis.py` | Full | QC prompt, parsing, diagnosis rules |
| `scripts/sdlc/model_router/__init__.py` (L175–L215), `decision.py`, `history.py` | Targeted / research | Weights only in text; decisions |
| `scripts/sdlc/common/llm.py`, `config.py`, `logging_util.py` | Research | CLI invocation, env stripping, fallback |
| `scripts/sdlc/*.py` CLIs, `telemetry/`, `traceability/`, `impact/`, `readiness/`, `contracts/`, `budget/`, `classify/` | Research + argument scan | Entry points and arguments |
| `scripts/requirements.txt`, `scripts/council_ci_runner.py` | Research | PyYAML; auxiliary runner |
| `.github/agents/*.agent.md` (18 files) | Research (`engineer`, `nfr`, `task`, `arch_document` full in session) | Agent purposes and rules |
| `.github/skills/**` (6 files) | Listed | Copilot skills (not runtime) |

## Documentation and root

| File | Depth | Key facts used |
|---|---|---|
| `README.md`, `step-by-step.md`, `docs/README.md`, `LICENSE`, `.gitignore` | Full / research | Overview, run commands, MIT licence, ignored folders |
| `docs/brd/BRD-23.md`, `docs/prd/PRD-23.md`, `docs/epic/EPIC-23.md`, `docs/architecture/ARCH-23.md`, `docs/nfr/NFR-23.md`, `docs/tasks/TASK-23.md` | Research + targeted extraction | Requirement IDs, NFRs, task list |
| `docs/brd/BRD-15.md`, `BRD-17.md`, `BRD-19.md`, `docs/prd/PRD-19.md`, `docs/epic/EPIC-19.md` | Listed | Earlier SDLC runs |

## Commands executed (non-destructive)

| Command | Purpose | Result |
|---|---|---|
| `git ls-files`, `git log`, `git rev-parse`, `git diff --stat 605e414` | Inventory, commit metadata, change review | 342 files, `6429a22` |
| `dotnet test SmartServe.sln -c Release` | Test evidence | 32 passed, 0 failed |
| `az deployment group validate`, `az resource list`, `az webapp config appsettings list` (names only), `gh run view` | Read-only Azure and pipeline evidence for DEV | DEV deployed; settings and policy effects confirmed |
| `Select-String` pattern scans over workflows and sources | Injection, pinning, test names | See findings |
| `npm install` in `docs/complete-solution-documentation/tools` (with `PUPPETEER_SKIP_DOWNLOAD=true`) | Local documentation toolchain (Mermaid CLI) | Local only |
| `npm run build`, `npm run validate`, `npm run qa` | Generate and validate outputs | See `documentation-validation.md` |

## Generated files

- `docs/complete-solution-documentation/` contains:
    - `README.md`
    - `final/` — PDF and HTML
    - `source/` — master Markdown, 11 chapter files, `document-metadata.yaml`, `references.md`
    - `diagrams/` — 30 `.mmd` sources, 30 SVG and 30 PNG renderings
    - `analysis/` — 7 files
    - `guides/` — 5 files, extracted from the master document
    - `tools/` — `package.json`, `build.mjs`, `validate.mjs`, `qa-screens.mjs`, template, CSS, Mermaid and puppeteer configuration
- **The documentation update itself modified no application source, configuration or workflow files.** Application and infrastructure changes described in version 2.0 were made separately during the DEV deployment work.
