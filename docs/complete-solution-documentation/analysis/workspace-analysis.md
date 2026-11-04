# Workspace Analysis — SmartServe / AISDLC-V1

Repository `Deepankar-AICloud/AISDLC-V1`, branch `main`, commit `605e414` (2026-11-03). The analysis covered all 152 tracked files; source code was used as the primary source of truth. Secret values were never printed; only setting names are recorded.

## 1. Workspace summary

The workspace hosts:

- **SmartServe**, an IT service and access request portal (.NET 8 Web API + React/TypeScript SPA, Azure SQL, Entra ID, deployed to Azure App Service).
- **An Agentic SDLC platform** (Python orchestrator + GitHub Copilot CLI agents + GitHub Actions) that generated the SmartServe requirement and design artifacts for issue #23.
- **Legacy/auxiliary workflows** from an earlier Ticket Tracker (Flask) demo, whose application code is no longer present.

## 2. File and folder inventory

| Folder | Files | Notes |
|---|---|---|
| `src/backend/SmartServe.Api` | 11 | Program, 2 controllers, domain, DTOs, DbContext, WorkflowService, csproj, 2 appsettings |
| `src/backend/SmartServe.Tests` | 3 | csproj + 2 test classes (16 cases) |
| `src/backend` (root) | 3 | `SmartServe.sln`, `build-release.log`, `test-release.log` (stale) |
| `src/frontend` | 11 | Vite/React/TS app, ESLint, `.env.example` |
| `infra` | 4 | `main.bicep` + dev/staging/production parameters |
| `.github/workflows` | 20 | 19 YAML + 1 agentic-workflow source (`daily-repo-status.md`) |
| `.github/agents` | 18 | Agent definitions |
| `.github` (other) | 4 + skills | CODEOWNERS, copilot-instructions, copilot-setup-steps (legacy), `aw/actions-lock.json`; 6 skill files |
| `scripts` | 30 | `scripts/sdlc/**` orchestrator platform + `council_ci_runner.py` |
| `config` | 18 | Platform configuration + 8 artifact contracts |
| `docs` | 18 | Generated BRD/PRD/EPIC/ARCH/NFR/TASK artifacts + README (+ this documentation set) |
| root | 5 | README, step-by-step, LICENSE (MIT), .gitignore |

## 3. Technology stack

- **Languages:** C# (.NET 8), TypeScript 5.6 (React 18), Python 3.13, Bicep, YAML.
- **Frameworks and libraries:** ASP.NET Core Web API, EF Core 8.0.8, Microsoft.Identity.Web 3.8.2, Swashbuckle 6.7.3, App Insights 2.22.0, Azure.Identity 1.12.1, MSAL Browser 3.26 / React 2.2, Vite 5.4, Vitest 2.1, xUnit 2.9.2.
- **Data:** Azure SQL / EF In-Memory.
- **Identity:** Microsoft Entra ID.
- **Hosting:** Azure App Service (Linux) with a staging slot.
- **IaC:** Bicep.
- **CI/CD:** GitHub Actions with OIDC.
- **Security tooling:** CodeQL (default setup), gitleaks, OWASP ZAP, `dotnet list package --vulnerable`, `npm audit`.
- **AI:** GitHub Copilot CLI with gpt-5-mini, claude-haiku-4.5, gpt-5.5, claude-sonnet-4.6 and claude-sonnet-5 (SDLC platform only).

## 4. Detected application components

- **SmartServe:** C-01 SPA, C-02 MSAL module, C-03 API host, C-04 AccessRequestsController, C-05 AuditController, C-06 WorkflowService, C-07 DbContext, C-08 health endpoint, C-09 tests.
- **Infrastructure and delivery:** I-01 Bicep, I-02 CI, I-03 security scan, I-04 deploy workflows.
- **Agentic SDLC platform:** P-01 orchestrator/state, P-02 model router, P-03 QC/diagnosis, P-04 readiness/contracts/budget, P-05 LLM runner, P-06 telemetry/reporting/traceability, P-07 agent definitions, P-08 SDLC workflows.

Details are in `component-inventory.md`.

## 5. Application entry points

| Entry point | Location |
|---|---|
| API | `src/backend/SmartServe.Api/Program.cs` (top-level statements, `public partial class Program`) |
| SPA | `src/frontend/index.html` → `src/main.tsx` |
| Tests | `dotnet test SmartServe.sln` |
| SDLC orchestrator | `python -m scripts.sdlc.run` |
| Other SDLC CLIs | `approve`, `feedback`, `model_confirm`, `dashboard`, `release_evidence`, `deployment_status`, `impact_cli` |
| Workflows | `.github/workflows/*.yml` |

## 6. Interfaces between components

- SPA → API: REST/JSON with a bearer token and an `x-correlation-id` header.
- API → SQL: EF Core over TDS, managed-identity connection string.
- API → Key Vault: configuration provider using `DefaultAzureCredential`.
- API → App Insights: telemetry SDK.
- SPA/API → Entra ID: OIDC/OAuth.
- Workflows → Azure: OIDC + ARM/Kudu.
- Orchestrator → Copilot CLI: stdin prompt.
- Orchestrator ↔ GitHub: issues, PRs and artifacts through `gh`.

## 7. External dependencies

- **Azure services:** Entra ID, App Service, Azure SQL, Key Vault, Storage, Application Insights, Log Analytics.
- **GitHub:** Actions, CodeQL, Issues/PRs, Copilot.
- **Package registries:** NuGet, npm, PyPI.
- **Third-party actions:** gitleaks, ZAP, docker, austenstone/copilot-cli (auxiliary).

## 8. Authentication and authorization findings

**Authentication (Entra ID JWT, Microsoft.Identity.Web).**

- `[Authorize]` on both controllers.
- `/health` is anonymous, which contradicts NFR-001.
- The SPA has no interactive sign-in. It uses `acquireTokenSilent` only, with a sessionStorage cache.

**Authorization.** Four policies (`CanCreateRequest`, `CanApprove`, `CanAudit`, `CanAdminister`; the last is unused) plus controller checks:

- Plain-employee ownership.
- Requester-only confirmation.
- No self-approval.
- Stage-specific roles.

Non-employee roles can read all requests. The six roles are string constants and must be defined as Entra app roles; the manifest is not in the workspace.

## 9. Database and storage findings

- **Entities:** `AccessRequest` (aggregate), `ApprovalStep`, `RequestComment`, `AuditEntry`.
- **Enums** are stored as strings in SQL.
- **Indexes:** `RequesterId`, `Status`, `AuditEntry.AccessRequestId`, `Timestamp`.
- **No migrations are committed**, yet `Database.Migrate()` runs at startup for relational providers. In Azure SQL this creates no tables.
- **SQL server provisioning:** SQL admin login, public network access and an `AllowAzureServices` rule. No Entra admin and no managed-identity database user are created.
- **Storage account:** provisioned with Blob Data Contributor for the API identity, but no code uses it.

## 10. API findings

- **Endpoints:** seven controller endpoints plus `/health` and Swagger (Development only).
- **OpenAPI:** no specification file is committed.
- **Enum contract mismatch:** no `JsonStringEnumConverter`, while the SPA sends and expects strings.
- **Error handling:** no ProblemDetails or exception handler.
- **Paging:** none; audit is capped at 500 rows.
- **Rate limiting and API versioning:** none.

## 11. Deployment findings

- **Bicep** creates per environment: Log Analytics, App Insights, Key Vault, SQL server/DB/firewall, Storage, plan, API app + `staging` slot, web app, and two role assignments.
- **DEV** runs Bicep and deploys the API and web app.
- **STAGING** deploys the API to the slot only.
- **PRODUCTION** performs a slot swap only.
- `staging.parameters.json` and `production.parameters.json` are unused by any workflow.
- **Missing settings:** the web app has no app settings or managed identity, and the `VITE_*` build variables are not supplied.
- **Missing API settings:** `Cors__AllowedOrigins` and `AzureAd__Audience`.
- **Slot identity** lacks a Key Vault role.

## 12. CI/CD findings

- **`ci.yml`:** backend build, test and coverage collection; frontend lint, build and tests. Tests and dependency audits are non-blocking, and the coverage threshold is not enforced.
- **`security.yml`:** gitleaks.
- **CodeQL:** default setup.
- **Deploy workflows:** OIDC, environments `dev`/`staging`/`production`, a production confirmation input, mandatory reviewers, and a release evidence pack.
- **Agentic SDLC workflows:** a CodeQL gate, the orchestrator, artifact review, the feedback handler and Python validation.
- **Legacy workflows** use the `AZURE_CREDENTIALS` service-principal JSON.

## 13. Security findings

| Severity | Finding |
|---|---|
| **Critical** | Script injection through `github.event.comment.body` in `feedback-handler.yml` (L34, L98), with write permissions on a public repository. |
| High | No SPA sign-in. |
| High | SQL managed-identity login not provisioned and SQL password admin enabled. |
| High | Public SQL network access. |
| High | Slot identity without a Key Vault role. |
| Medium | No rate limiting, HSTS or CSP. |
| Medium | Broad read access. |
| Medium | Non-blocking SCA; tag-pinned actions; placeholder CODEOWNERS. |

**Strengths:**

- Managed identity and Key Vault RBAC.
- OIDC deployments.
- TLS 1.2 and HTTPS-only.
- Security headers.
- Server-side policies.
- Tokens stripped from the LLM environment.
- Allowlisted commands.
- CodeQL gate.

## 14. Monitoring findings

- **In place:** the App Insights SDK in the API (workspace-based, 30/90-day retention), `/health` with a DB check, App Service health check, and workflow smoke tests.
- **Missing:** alerts, dashboards, availability tests, diagnostic settings and SPA telemetry.
- **Audit trail:** kept in SQL.

## 15. Testing findings

- **Backend:** 16 xUnit tests (2 integration, 14 unit) — **executed: 16/16 passed** on SDK 8.0.427.
- **Frontend:** no tests.
- **Missing test types:** role/endpoint matrix, persistence and contract tests, performance tests.
- **Stale log:** the committed `test-release.log` shows 14 tests.

## 16. Confirmed facts

All statements in the main document marked [IMPLEMENTED] are traceable to files listed in `file-inspection-log.md`. The backend build and tests were executed. All 30 diagrams were rendered successfully.

## 17. Assumptions

See `assumptions.md`. Every assumption is labelled in the document.

## 18. Missing information

See `open-questions.md` (14 questions): ownership, app registrations, environment separation, `/health` policy, role scoping, notifications, submission fields, service workflow, NFR targets, retention, storage purpose, branch protection, Front Door, region.

## 19. Potential inconsistencies

| # | Inconsistency |
|---|---|
| 1 | README "16 tests" vs committed log with 14 tests (README is correct) |
| 2 | NFR-001 (no anonymous endpoint) vs anonymous `/health` |
| 3 | ARCH-23 permission decisions vs broader reads in code |
| 4 | `deploy-production.yml` header comment says it "Deploys to the staging slot", but it only swaps |
| 5 | `config/environments.yml` `front_door_enabled: true` vs no Front Door in IaC |
| 6 | `quality-gates.yml` `coverage_min`/`lint_must_pass` and `ci.yml` `COVERAGE_THRESHOLD` are not enforced |
| 7 | `model-routing.yml` weights only appear in text |
| 8 | `pricing.yml` lists models that are not configured |
| 9 | `copilot-setup-steps.yaml` and `deploy.yml` reference Flask files and a Dockerfile that do not exist |
| 10 | `test.yml` uses Python 3.11 vs 3.13 elsewhere |

## 20. Documentation-generation plan (executed)

1. Discovery with three parallel read-only research passes, then direct verification of key files (`Program.cs`, controllers, DTOs, `WorkflowService`, `main.bicep`, parameters, all deploy/CI/security workflows, `config/*`, `CODEOWNERS`).
2. Execute the backend tests for evidence.
3. Author 30 Mermaid diagrams; render them to SVG and PNG with workspace-local Mermaid CLI using the installed Chrome.
4. Write 11 chapter files, assembled into the master Markdown with metadata, a custom HTML template and print CSS.
5. Convert with Pandoc to self-contained HTML; print to PDF with Chrome (puppeteer) with headers, footers, page numbers and bookmarks.
6. Validate sections, links, paths, Mermaid, secrets and the PDF, and record the results in `documentation-validation.md`.
