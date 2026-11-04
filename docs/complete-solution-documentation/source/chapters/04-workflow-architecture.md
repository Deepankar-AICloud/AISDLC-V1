# End-to-End Workflow {#end-to-end-workflow}

## High-level business workflow

![Figure 4 — High-level business workflow for an access/service request](diagrams/rendered/04-business-workflow.png)

The approval path is computed by `WorkflowService`:

- **Sensitive categories** (`ProductionAccess`, `DatabaseAccess`, `AzureAccess`, `VpnAccess`) follow Manager → Security → IT.
- **All other categories** follow Manager → IT.
- **Any rejection** ends the request as `Rejected`.
- **IT approval** sets `Provisioned`. The requester then calls `/confirm` to close the request.

![Figure 5 — Request lifecycle state machine (as implemented)](diagrams/rendered/05-request-state-machine.png)

The `RequestStatus` enum also contains `Draft`, `ManagerApproval` and `AwaitingConfirmation`. No endpoint sets these values: `Confirm` accepts `AwaitingConfirmation`, and `CurrentStage` maps `ManagerApproval` to the Manager stage.

## Detailed application workflow

![Figure 6 — Detailed application workflow (frontend → API → database → audit)](diagrams/rendered/06-detailed-application-workflow.png)

| # | Actor | Activity | Input | Processing | Component | Output | Data stored / retrieved | Security control | Possible failure | Recovery | Audit event |
|---|---|---|---|---|---|---|---|---|---|---|---|
| 1 | User | Open portal | URL | SPA bootstrap, MSAL init | `main.tsx`, `auth.ts` | Rendered page | MSAL cache (sessionStorage) | HTTPS (App Service `httpsOnly`) | Missing `VITE_*` config | Set build-time env, rebuild | — |
| 2 | User | Authenticate | Entra credentials | **Not implemented in SPA**: `acquireTokenSilent` only | `auth.ts`, `api.ts` | Access token (if a session exists) | Token in sessionStorage | Entra ID, PKCE public client | No account, so requests are sent without a token and return 401 | Implement sign-in (§33) | — |
| 3 | Employee | Submit request | Title, description, category | Model validation, `CanCreateRequest`, compute security flag | `AccessRequestsController.Create`, `WorkflowService` | 201 + request | INSERT `AccessRequests` | JWT, role policy, max lengths | 400 / 401 / 403; enum mismatch (§16.4) | Fix input or contract | `RequestCreated` |
| 4 | Any role | List / view | — / id | Ownership filter for plain employees | `List`, `GetById` | Request list / item | SELECT `AccessRequests` | `[Authorize]`, ownership | 403 / 404 | — | — (reads not audited) |
| 5 | Manager | Decide (Manager stage) | approved, notes | Self-approval block, stage role check, `Advance` | `Decide` | Updated request | INSERT `Approvals`, UPDATE status | `CanApprove`, stage role | 400 (not awaiting), 403, 404 | — | `Decision` |
| 6 | SecurityReviewer | Decide (Security stage, sensitive only) | approved, notes | as above | `Decide` | Updated request | as above | as above | as above | — | `Decision` |
| 7 | ItAdmin | Decide (IT stage), giving `Provisioned` | approved, notes | as above | `Decide` | Updated request | as above | as above | as above | — | `Decision` |
| 8 | Employee | Confirm provisioning | id | Requester-only check, status check | `Confirm` | Closed request | UPDATE status, `ClosedAt` | Ownership | 400 / 403 / 404 | — | `Closed` |
| 9 | Any participant | Comment | body | Ownership for plain employees | `AddComment` | 204 | INSERT `Comments` | `[Authorize]`, max length | 403 / 404 | — | `CommentAdded` |
| 10 | Auditor / AppAdmin | Read audit trail | optional requestId | Filter, newest 500 | `AuditController.List` | Audit entries | SELECT `AuditEntries` | `CanAudit` | Truncation beyond 500 | Add paging (§33) | — |
| 11 | System | Notify | status change | **Not implemented** | — | — | — | — | — | Implement (§33) | — |
| 12 | Platform | Monitor | requests, failures | App Insights SDK, `/health` | API, App Service | Telemetry | Log Analytics | — | Unconfigured connection string | Set via IaC | — |

Table: Table 10.1 — Workflow steps with controls, failures and audit events

## User authentication workflow

![Figure 7 — Authentication and token validation sequence](diagrams/rendered/07-authentication-sequence.png)

## Frontend-to-backend request workflow — submitting a request

![Figure 8 — Submit request sequence, including failure paths](diagrams/rendered/08-submit-request-sequence.png)

## Approval workflow

![Figure 9 — Stage decision (approval) sequence with authorization branches](diagrams/rendered/09-approval-sequence.png)

## Data-processing workflow

![Figure 10 — Data-processing flow: DTOs → validation → authorization → workflow → tables](diagrams/rendered/10-data-processing-workflow.png)

## Other workflows

The other workflows are covered in their own chapters:

- AI agent and document-generation workflows: §17.
- Error and retry: §24.
- CI/CD and deployment: §21.

# Solution Architecture {#solution-architecture}

SmartServe is a classic **three-tier web application**. The tiers are:

- A browser SPA.
- A stateless REST API on Azure App Service.
- A relational database in Azure SQL.

Identity is delegated to Microsoft Entra ID, configuration secrets come from Key Vault through managed identity, and telemetry goes to Application Insights.

![Figure 11 — Logical architecture of SmartServe](diagrams/rendered/03-logical-architecture.png)

| Decision | Choice in code | Rationale / evidence | Status |
|---|---|---|---|
| Architecture style | Single SPA + single modular API (monolith) | ARCH-23 labels the consolidation *(proposed)*; implemented as one project | [IMPLEMENTED]{.badge .ok} |
| Communication | Synchronous REST/JSON over HTTPS | `api.ts`, controllers | [IMPLEMENTED]{.badge .ok} |
| AuthN | Entra ID OAuth 2.0 / OIDC, JWT bearer | `AddMicrosoftIdentityWebApi` | [IMPLEMENTED]{.badge .ok} |
| AuthZ | Role policies + resource checks in controllers | `Program.cs`, `AccessRequestsController` | [IMPLEMENTED]{.badge .ok} |
| Persistence | EF Core code-first; schema applied at startup with `Migrate()` / `EnsureCreated()` | `Program.cs` (no migrations committed) | [PARTIAL]{.badge .partial} |
| Configuration | `appsettings` + environment app settings + Key Vault provider | `Program.cs`, `main.bicep` | [IMPLEMENTED]{.badge .ok} |
| Asynchronous processing | None (no queues, workers or background jobs) | — | [NOT CONFIRMED]{.badge .nc} as a need |

Table: Table 11.1 — Key architecture decisions

# Component Architecture {#component-architecture}

![Figure 12 — Component diagram across application, infrastructure and platform](diagrams/rendered/29-component-diagram.png)

| ID | Component | Purpose | Technology | Source | Entry point | Inputs → Outputs | Dependencies | AuthN / AuthZ | Logging | Error handling | Deployment unit | Status |
|---|---|---|---|---|---|---|---|---|---|---|---|---|
| C-01 | React SPA | Request form and list UI | React 18, Vite | `src/frontend/src/App.tsx` | `index.html` → `main.tsx` | User input → REST calls | C-02, API | Token from C-02 | none | Alert box with error text | Web App Service | [PARTIAL]{.badge .partial} |
| C-02 | MSAL auth module | Token acquisition for API scope | MSAL Browser 3 | `src/frontend/src/auth.ts` | `msalInstance` | Account → access token | Entra ID | Public client, sessionStorage | none | `authConfigured` flag | Web App Service | [PARTIAL]{.badge .partial} |
| C-03 | API host and pipeline | Startup, DI, middleware | ASP.NET Core 8 | `Program.cs` | `Program` | HTTP → endpoints | Entra, KV, AI, EF | JWT + policies | ILogger, App Insights | Framework defaults | API App Service | [IMPLEMENTED]{.badge .ok} |
| C-04 | AccessRequestsController | Request lifecycle API | ASP.NET Core MVC | `Controllers/AccessRequestsController.cs` | `api/requests` | DTOs → `RequestResponse` | C-06, C-07 | `[Authorize]`, policies, ownership, stage | `LogInformation` on create | `NotFound` / `Forbid` / `BadRequest` | API | [IMPLEMENTED]{.badge .ok} |
| C-05 | AuditController | Read audit trail | ASP.NET Core MVC | `Controllers/AuditController.cs` | `api/audit` | requestId → entries | C-07 | `CanAudit` | — | — | API | [IMPLEMENTED]{.badge .ok} |
| C-06 | WorkflowService | Approval path rules | C# | `Services/WorkflowService.cs` | DI (scoped) | Request + decision → status | — | n/a | — | Unknown stage keeps status | API | [IMPLEMENTED]{.badge .ok} |
| C-07 | SmartServeDbContext | Persistence model | EF Core 8 | `Data/SmartServeDbContext.cs` | DI | Entities ↔ SQL | Azure SQL / In-Memory | MI connection string | EF logging | Exceptions propagate (500) | API | [IMPLEMENTED]{.badge .ok} |
| C-08 | Health endpoint | Liveness/readiness incl. DB | Health checks | `Program.cs` | `/health` | — → Healthy/Unhealthy | C-07 | Anonymous | — | 503 when unhealthy | API | [IMPLEMENTED]{.badge .ok} |
| C-09 | Test suite | Unit + integration tests | xUnit | `src/backend/SmartServe.Tests` | `dotnet test` | — → results | C-03, C-06 | — | trx (CI) | — | n/a | [IMPLEMENTED]{.badge .ok} |
| I-01 | Bicep template | Environment resources and RBAC | Bicep | `infra/main.bicep` | `azure/arm-deploy` | Parameters → resources | Azure RM | OIDC deployer | ARM | Deployment fails | Resource group | [IMPLEMENTED]{.badge .ok} |
| I-02..04 | CI, security and deploy workflows | Build/test/scan/deploy | GitHub Actions | `.github/workflows/` | triggers | Code → artifacts/deployments | Azure, GitHub | OIDC, environments | Actions logs | Fail job / smoke gate | GitHub | [IMPLEMENTED]{.badge .ok} |
| P-01..08 | Agentic SDLC platform | Requirement → code automation | Python, Copilot CLI | `scripts/sdlc`, `config`, `.github/agents` | `python -m scripts.sdlc.run` | Issue → artifacts/PRs | GitHub, Copilot | Env-stripped tokens, allowlists | Structured JSON logs, reports | QC, diagnosis, fail-safe | GitHub Actions | [IMPLEMENTED]{.badge .ok} |

Table: Table 12.1 — Component inventory (full version in `analysis/component-inventory.md`)

# Application Architecture {#application-architecture}

## Frontend

![Figure 13 — Frontend architecture](diagrams/rendered/12-frontend-architecture.png)

- **Single component** (`App.tsx`) holding React state (`useState`/`useEffect`). There is no router, global store or UI library.
- **HTTP wrapper** (`api.ts`): adds `Content-Type`, a random `x-correlation-id` (UUID) and a bearer token when available. Any non-2xx response throws, and the error is shown in an alert region (`role="alert"`).
- **Configuration**: build-time `VITE_*` variables (`.env.example`). The dev server proxies `/api` and `/health` to `http://localhost:5000`.
- **Gaps**:
    - No sign-in UI.
    - No screens for decisions, confirmation, comments or audit.
    - No frontend tests.
    - No App Insights browser telemetry.

## Backend

![Figure 14 — Backend architecture: startup configuration and request pipeline](diagrams/rendered/13-backend-architecture.png)

- **Startup** (`Program.cs`), in order:
    1. Optional Key Vault configuration provider.
    2. App Insights.
    3. Entra ID JWT.
    4. Four authorization policies.
    5. DbContext (SQL Server, or In-Memory when no connection string is set).
    6. Scoped `WorkflowService`.
    7. Controllers.
    8. Swagger.
    9. Health checks.
    10. CORS policy `spa` (origins from `Cors:AllowedOrigins`, default `http://localhost:5173`).
- **Pipeline order:**
    1. Swagger (Development only).
    2. HTTPS redirection.
    3. Security headers middleware.
    4. CORS.
    5. Authentication.
    6. Authorization.
    7. Controllers, plus `/health` (anonymous).
- **Schema management:** `Database.Migrate()` for relational providers, `EnsureCreated()` for In-Memory. **No migrations are committed**, so the Azure SQL schema is never created (§30, R-04).
- **Not configured:** global exception handler / ProblemDetails, rate limiting, HSTS, response compression, output caching, API versioning, JSON enum converter.
