# Workspace Analysis — SmartServe / AISDLC-V1

Repository `Deepankar-AICloud/AISDLC-V1`, branch `main`, commit `6429a22` (2026-11-04), plus three uncommitted fixes in the working tree (`appsettings.json` audience placeholder removed, `deploy-staging.yml` switch, `setup-dev.ps1` pre-authorization). Version 2.0 of this analysis re-inspected all application, infrastructure and workflow files changed since the version 1.0 baseline `605e414`, and the live DEV deployment. Source code is the primary source of truth. Secret values were never printed; only setting names and non-secret identifiers are recorded, and identifiers are masked in the main document.

## 1. Workspace summary

The workspace hosts:

- **SmartServe**, an IT service and access request portal (.NET 8 Web API + React/TypeScript SPA, Azure SQL, Entra ID, Microsoft Graph), deployed to Azure App Service in DEV.
- **An Agentic SDLC platform** (Python orchestrator + GitHub Copilot CLI agents + GitHub Actions) that generated the SmartServe requirements, design, task plan and code for issue #23 (PRs #24–#34).
- **Legacy/auxiliary workflows** from an earlier Ticket Tracker (Flask) demo, whose application code is no longer present.

## 2. File and folder inventory

| Folder | Tracked files | Notes |
|---|---|---|
| `src/backend/SmartServe.Api` | 28 | Program, 4 controllers, domain, DTOs, data + migration, services (workflow, notification, e-mail, directory), test auth handler, csproj, appsettings |
| `src/backend/SmartServe.Tests` | 11 | csproj, 6 test classes (26 methods, 32 cases), 4 test-support files |
| `src/frontend` | 16 | Vite/React/TS app, admin feature, 3 test files, `package-lock.json` |
| `infra` | 5 | `main.bicep`, 3 parameter files, `scripts/setup-dev.ps1` |
| `.github/workflows` | 20 | 19 YAML + 1 agentic-workflow source |
| `.github/agents` | 18 | Agent definitions |
| `scripts` | 33 | `scripts/sdlc/**` orchestrator platform + auxiliary runner |
| `config` | 17 | Platform configuration + artifact contracts |
| `docs` | 20 + documentation sets | Generated SDLC artifacts and README, plus this documentation set and the AISDLC overview |

## 3. Technology stack

- **Languages:** C# (.NET 8), TypeScript 5.6 (React 18), Python 3.13, Bicep, PowerShell 7, YAML.
- **Frameworks and libraries:** ASP.NET Core Web API, EF Core 8.0.8 (SqlServer, InMemory; SQLite in tests), Microsoft.Identity.Web 3.8.2, Swashbuckle 6.7.3, App Insights 2.22.0, Azure.Identity 1.12.1, MSAL Browser 3.26 / React 2.2, Vite 5.4, Vitest 2.1 + Testing Library, xUnit 2.9.2.
- **Data:** Azure SQL (Entra-only, private endpoint) / EF In-Memory locally.
- **Identity and directory:** Microsoft Entra ID; Microsoft Graph (REST) for manager lookup and e-mail.
- **Hosting:** Azure App Service (Linux) with VNet integration; Node 22 for the web app.
- **IaC:** Bicep + one-time PowerShell setup script.
- **CI/CD:** GitHub Actions with OIDC (user-assigned managed identity).
- **Security tooling:** CodeQL (default setup), gitleaks, OWASP ZAP (staging, not running), `dotnet list package --vulnerable`, `npm audit`.
- **AI:** GitHub Copilot CLI (SDLC platform only).

## 4. Detected application components

- **SmartServe:** C-01 SPA, C-02 MSAL module, C-03 API host, C-04 RequestsController, C-05 RequestTypesController, C-06 Audit/SecurityReview controllers, C-07 WorkflowService, C-08 DbContext + migration, C-09 notification services, C-10 directory service, C-11 health endpoint, C-12 tests.
- **Infrastructure and delivery:** I-01 Bicep, I-02 setup script, I-03 CI and security workflows, I-04 deploy workflows.
- **Agentic SDLC platform:** P-01 orchestrator/state (with CI/CD hand-off), P-02 model router, P-03 QC/diagnosis, P-04 readiness/contracts/budget, P-05 LLM runner, P-06 telemetry/reporting/traceability, P-07 agent definitions, P-08 SDLC workflows.

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

- SPA → API: REST/JSON (string enums) with a bearer token and an `x-correlation-id` header.
- API → SQL: EF Core over TDS through a private endpoint, user-assigned managed identity.
- API → Key Vault: configuration provider using `DefaultAzureCredential`, private endpoint.
- API → Microsoft Graph: REST with the managed identity (users, manager, sendMail).
- API → App Insights: telemetry SDK.
- SPA/API → Entra ID: OIDC/OAuth (redirect sign-in, JWT validation).
- Workflows → Azure: OIDC + ARM/Kudu.
- Orchestrator → Copilot CLI: stdin prompt.
- Orchestrator ↔ GitHub: issues, PRs and artifacts through `gh`.

## 7. External dependencies

- **Azure services:** Entra ID, App Service, Azure SQL, Key Vault, Storage, Virtual Network, Private DNS, Application Insights, Log Analytics.
- **Microsoft 365:** Microsoft Graph.
- **GitHub:** Actions, CodeQL, Issues/PRs, Copilot.
- **Package registries:** NuGet, npm, PyPI.
- **Third-party actions:** gitleaks, ZAP, docker, austenstone/copilot-cli (auxiliary).

## 8. Authentication and authorization findings

**Authentication (Entra ID JWT, Microsoft.Identity.Web).**

- A fallback policy requires an authenticated user on every endpoint, including `/health` (NFR-001 met).
- The SPA signs users in with `MsalAuthenticationTemplate` (redirect) and falls back to an interactive redirect when silent token renewal fails.
- A placeholder `AzureAd:Audience` in `appsettings.json` made the API reject every token in DEV; it has been removed (pending push) and DEV patched.
- The tenant restricts user consent; the SPA is pre-authorized on the API app registration.

**Authorization.** Nine named policies plus a fallback policy and an Auditor write-block middleware:

- Own-request reads only (`CanViewOwnRequests`, filtered by `RequesterId`).
- Read-all only for Auditor and AppAdmin; access-request read for SecurityReviewer.
- Several mappings marked *(proposed)*.
- Gap: decisions are not limited to the routed manager; no self-approval check.

## 9. Database and storage findings

- **Entities:** `PortalRequest`, `RequestType`, `RequestAudit`, `NotificationRecord`; enums stored as strings; GUID concurrency tokens.
- **Migration** `20261103093414_InitialPortalRequestModel` is committed and applied at startup; verified in DEV.
- **Only one foreign key** (`PortalRequests → RequestTypes`, restrict); audits and notification records reference requests by ID only.
- **SQL server provisioning:** Entra-only authentication with the API's user-assigned identity as admin; public network access disabled; private endpoint.
- **Storage account:** public access and shared keys disabled; Blob Data Contributor for the API identity, but no code uses it.

## 10. API findings

- **Endpoints:** 13 controller endpoints plus `/health` and Swagger (Development only).
- **OpenAPI:** no specification file is committed.
- **Contract:** enums as strings; tested on both sides.
- **Error handling:** no ProblemDetails or exception handler; concurrent transitions return 400.
- **Paging:** audit and security-review endpoints (default 50, max 200).
- **Rate limiting and API versioning:** none.

## 11. Deployment findings

- **Bicep** creates per environment: API identity, Log Analytics, App Insights, Key Vault, SQL server/DB, Storage, VNet, private endpoints and DNS zones, plan, API app (slot outside DEV), web app, and two role assignments.
- **DEV** is deployed in `rg-aisdlc-v1` (West US 3) by `deploy-dev.yml`, which reads app names and URLs from Bicep outputs and sets `VITE_*` values.
- **One-time setup** (`setup-dev.ps1`) creates the OIDC identity, Entra app registrations and GitHub settings.
- **Problems met during the first deployment and fixed:** subscription policy disabling public access (→ private networking), missing `Microsoft.Network` registration, GitHub's ID-based OIDC subject, SPA without sign-in, consent policy, placeholder audience.
- **STAGING and PRODUCTION** are not set up; `deploy-staging.yml` is skipped until `STAGING_ENABLED` is `true`.
- **Graph permissions** for the API identity and the sender mailbox are not configured.

## 12. CI/CD findings

- **`ci.yml`:** backend build, test and coverage collection; frontend lint, build and tests. Tests and dependency audits are non-blocking, and the coverage threshold is not enforced.
- **`security.yml`:** gitleaks.
- **CodeQL:** default setup.
- **Deploy workflows:** DEV fully automated; staging/production defined but not set up; production approval and release evidence pack designed.
- **Agentic SDLC workflows:** CodeQL gate, orchestrator (now hands off to CI/CD after the code stage), artifact review, feedback handler and Python validation. Code-stage commits no longer carry `[skip ci]`.
- **Legacy workflows** use the `AZURE_CREDENTIALS` service-principal JSON.

## 13. Security findings

| Severity | Finding |
|---|---|
| **Critical** | Script injection through `github.event.comment.body` in `feedback-handler.yml` (L34, L98), with write permissions on a public repository. |
| High | Graph permissions not granted in DEV (routing and e-mail fail). |
| High | API identity is SQL Entra admin and will also hold Graph application permissions. |
| Medium | Decisions not limited to the routed manager; no self-approval check. |
| Medium | `/health` requires a token, so the App Service probe receives 401. |
| Medium | No rate limiting, HSTS or CSP. |
| Medium | Non-blocking SCA; tag-pinned actions; placeholder CODEOWNERS. |

**Strengths:**

- Private networking for data services; Entra-only SQL; no passwords anywhere.
- User-assigned managed identity; Key Vault RBAC; OIDC deployments.
- TLS 1.2 and HTTPS-only; security headers.
- Server-side policies, strict read scoping and Auditor write-block, with authorization tests per endpoint.
- Transactional audit and concurrency tokens.
- Tokens stripped from the LLM environment; allowlisted commands; CodeQL gate.

## 14. Monitoring findings

- **In place:** App Insights SDK in the API (workspace-based, 30/90-day retention), `/health` with a DB check, notification outcome records with a reconciliation job, DEV smoke test.
- **Missing:** alerts, dashboards, availability tests, diagnostic settings and SPA telemetry.

## 15. Testing findings

- **Backend:** 26 test methods (32 cases) across integration, authorization, workflow/audit and SQLite atomicity tests — **executed: 32/32 passed**.
- **Frontend:** 5 Vitest tests (navigation, contract fixture, request-type admin).
- **Missing test types:** SQL Server persistence, end-to-end, performance.
- **Stale log:** the committed `test-release.log` predates the current suite.

## 16. Confirmed facts

All statements in the main document marked [IMPLEMENTED] are traceable to files listed in `file-inspection-log.md`. The backend build and tests were executed. All 30 diagrams were rendered successfully.

## 17. Assumptions

See `assumptions.md`. Every assumption is labelled in the document.

## 18. Missing information

See `open-questions.md` (14 questions): ownership, role assignment and Graph consent, staging/production design, health-probe approach, role mappings, sender mailbox, submission fields, service workflow, NFR targets, retention, storage purpose, branch protection, Front Door, region.

## 19. Potential inconsistencies

| # | Inconsistency |
|---|---|
| 1 | NFR-001 (no anonymous endpoint) vs App Service health probe on `/health` (receives 401) |
| 2 | `deploy-staging.yml` and `deploy-production.yml` health checks expect 200 from `/health`, which now requires a token |
| 3 | `deploy-production.yml` header comment says it "Deploys to the staging slot", but it only swaps |
| 4 | `config/environments.yml` `front_door_enabled: true` vs no Front Door in IaC |
| 5 | `quality-gates.yml` `coverage_min`/`lint_must_pass` and `ci.yml` `COVERAGE_THRESHOLD` are not enforced |
| 6 | `model-routing.yml` weights only appear in text; `pricing.yml` lists models that are not configured |
| 7 | `copilot-setup-steps.yaml` and `deploy.yml` reference Flask files and a Dockerfile that do not exist |
| 8 | Version skew: `test.yml` Python 3.11 vs 3.13; CI frontend Node 20 vs DEV Node 22 |
| 9 | `DecisionDto.Notes` accepted but not stored |
| 10 | Committed `build-release.log` / `test-release.log` predate the current code |

## 20. Documentation-generation plan (executed)

1. Version 1.0 (2026-11-03): discovery, test execution, 30 diagrams, 11 chapters, HTML/PDF build and validation at commit `605e414`.
2. Version 2.0 (2026-11-04): diff review from `605e414` to `6429a22`; read-only inventory of all new and changed application files; direct verification of controllers, `WorkflowService`, migration, `main.bicep`, workflows and the live DEV configuration; backend tests re-run (32/32); chapters, 27 diagrams and analysis files updated; rebuilt and re-validated.
