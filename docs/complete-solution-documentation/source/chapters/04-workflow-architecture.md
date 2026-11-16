# End-to-End Workflow {#end-to-end-workflow}

## High-level business workflow

![Figure 4 — High-level business workflow for an access/service request](diagrams/rendered/04-business-workflow.png)

The lifecycle is implemented in `Services/WorkflowService.cs`:

- **Submission** creates the request as *Submitted* (only against an active request type of the same kind) and notifies the requester.
- **Access requests** are then routed immediately: the requester's manager is looked up in Entra ID. If found, the request moves to *UnderReview* and the manager and requester are notified. If the manager cannot be resolved, or the directory is unavailable, the request stays *Submitted*, the manager notification is recorded as *NotSent* or *Failed*, and an IT administrator can retry routing.
- **Manager decision** moves an *UnderReview* access request to *Approved* or *Rejected* and notifies the requester.
- **Fulfilment** by an IT administrator moves an *Approved* request to *Fulfilled* and notifies the requester.
- **Service requests** stay *Submitted*; their onward workflow is an open question (§34).

Every transition writes its `RequestAudit` row in the same `SaveChanges` as the status change, and uses a concurrency token so that two simultaneous decisions cannot both succeed.

![Figure 5 — Request lifecycle state machine (as implemented)](diagrams/rendered/05-request-state-machine.png)

## Detailed application workflow

![Figure 6 — Detailed application workflow (frontend → API → database → audit)](diagrams/rendered/06-detailed-application-workflow.png)

| # | Actor | Activity | Input | Processing | Component | Output | Data stored / retrieved | Security control | Possible failure | Recovery | Audit event |
|---|---|---|---|---|---|---|---|---|---|---|---|
| 1 | User | Open portal | URL | SPA bootstrap, MSAL init | `main.tsx`, `auth.ts` | Redirect to sign-in | MSAL cache (sessionStorage) | HTTPS (App Service `httpsOnly`) | Missing `VITE_*` build values | Pipeline sets them from GitHub variables | — |
| 2 | User | Sign in | Entra credentials | `MsalAuthenticationTemplate` redirect; token for `api://<API_CLIENT_ID>/access_as_user` | `main.tsx`, `api.ts` | Access token | Token in sessionStorage | Entra ID, PKCE, SPA pre-authorized on the API | Consent blocked by tenant policy | Pre-authorization; admin consent if still required | — |
| 3 | Employee | Submit request | Kind, request type, title, description | Validation, `CanCreateRequest`, active-type check | `RequestsController.Create`, `WorkflowService.SubmitAsync` | 201 + request | INSERT `PortalRequests` + `RequestAudits` (one transaction) | JWT, role policy, max lengths | 400 / 401 / 403 | Fix input | null → Submitted |
| 4 | System | Notify requester | Request | Resolve requester e-mail, send | `NotificationService`, `GraphEmailSender` | NotificationRecord | INSERT/UPDATE `NotificationRecords` | Managed identity to Graph | Graph permission missing → *Failed* | Grant permission; reconciliation marks stale sends *Failed* | — |
| 5 | System | Route access request | Requester ID | Manager lookup in Entra ID | `TryRouteToManagerAsync`, `GraphDirectoryService` | UnderReview, or stays Submitted | UPDATE `PortalRequests` + audit | Managed identity to Graph | Manager unresolved / directory unavailable | IT admin `retry-routing` | Submitted → UnderReview |
| 6 | Employee | List / view own | — / id | Ownership filter | `List`, `GetById` | Own requests | SELECT `PortalRequests` | `CanViewOwnRequests` | 404 for others' requests | — | — (reads not audited) |
| 7 | Manager | Decide | approved, notes | Kind and status checks, concurrency token | `Decide` | Approved / Rejected | UPDATE + audit | `CanApprove` | 400 (not awaiting), 404, concurrent change | Retry | UnderReview → Approved/Rejected |
| 8 | ItAdmin | Fulfil | id | Status must be Approved | `Fulfil` | Fulfilled | UPDATE + audit | `CanFulfil` | 400, 404, concurrent change | Retry | Approved → Fulfilled |
| 9 | AppAdmin | Manage request types | name, description, kind | Create, edit, deactivate (one-way) | `RequestTypesController` | Request type | `RequestTypes` | `CanAdminister` | 400 / 404 | — | — |
| 10 | Auditor / AppAdmin | Read requests and history | page, pageSize | Paged read-all | `AuditController` | Paged results | SELECT | `CanAudit`; Auditor writes blocked | — | — | — |
| 11 | SecurityReviewer | Read access requests | page, pageSize | Access kind only | `SecurityReviewController` | Paged results | SELECT | `CanSecurityReview` | — | — | — |
| 12 | Platform | Monitor | Requests, failures | App Insights SDK, `/health` | API, App Service | Telemetry | Log Analytics | `/health` requires a token | No alert rules | Add alerts (§33) | — |

Table: Table 10.1 — Workflow steps with controls, failures and audit events

## User authentication workflow

![Figure 7 — Authentication and token validation sequence](diagrams/rendered/07-authentication-sequence.png)

## Frontend-to-backend request workflow — submitting a request

![Figure 8 — Submit request sequence, including failure paths](diagrams/rendered/08-submit-request-sequence.png)

## Approval workflow

![Figure 9 — Manager decision sequence with authorization and concurrency branches](diagrams/rendered/09-approval-sequence.png)

## Data-processing workflow

![Figure 10 — Data-processing flow: DTOs → validation → authorization → workflow → tables](diagrams/rendered/10-data-processing-workflow.png)

## Other workflows

The other workflows are covered in their own chapters:

- AI agent and document-generation workflows: §17.
- Error and retry: §24.
- CI/CD and deployment: §21.

# Solution Architecture {#solution-architecture}

SmartServe is a classic **three-tier web application** with two outbound integrations. The tiers are:

- A browser SPA.
- A stateless REST API on Azure App Service, integrated into a virtual network.
- A relational database in Azure SQL, reachable only through a private endpoint.

Identity is delegated to Microsoft Entra ID, configuration secrets come from Key Vault (also behind a private endpoint) through a user-assigned managed identity, manager lookup and e-mail use Microsoft Graph, and telemetry goes to Application Insights.

![Figure 11 — Logical architecture of SmartServe](diagrams/rendered/03-logical-architecture.png)

| Decision | Choice in code | Rationale / evidence | Status |
|---|---|---|---|
| Architecture style | Single SPA + single modular API (monolith) | ARCH-23 labels the consolidation *(proposed)*; implemented as one project | [IMPLEMENTED]{.badge .ok} |
| Communication | Synchronous REST/JSON over HTTPS; enums as strings (`JsonStringEnumConverter`) | `api.ts`, `Program.cs`, `EnumJsonSerializationTests` | [IMPLEMENTED]{.badge .ok} |
| AuthN | Entra ID OAuth 2.0 / OIDC, JWT bearer; SPA redirect sign-in | `AddMicrosoftIdentityWebApi`, `MsalAuthenticationTemplate` | [IMPLEMENTED]{.badge .ok} |
| AuthZ | Fallback policy (authenticated) + role policies + ownership filter + Auditor write-block | `Program.cs`, controllers | [IMPLEMENTED]{.badge .ok} |
| Persistence | EF Core code-first with a committed migration applied at startup (`MigrateAsync`); short-lived contexts via `IDbContextFactory` | `Program.cs`, `Migrations/` | [IMPLEMENTED]{.badge .ok} |
| Consistency | Status change + audit row in one `SaveChanges`; app-managed GUID concurrency tokens | `WorkflowService`, `SmartServeDbContext` | [IMPLEMENTED]{.badge .ok} |
| Notifications | Synchronous Graph `sendMail` after commit; outcome recorded; background reconciliation every 5 minutes | `NotificationService`, `NotificationReconciliationService` | [IMPLEMENTED]{.badge .ok} |
| Configuration | `appsettings` + App Service settings from Bicep + Key Vault provider | `Program.cs`, `main.bicep` | [IMPLEMENTED]{.badge .ok} |
| Network | VNet integration for the API; private endpoints for SQL and Key Vault; public access disabled on data services | `main.bicep` | [IMPLEMENTED]{.badge .ok} |

Table: Table 11.1 — Key architecture decisions

# Component Architecture {#component-architecture}

![Figure 12 — Component diagram across application, infrastructure and platform](diagrams/rendered/29-component-diagram.png)

| ID | Component | Purpose | Technology | Source | Entry point | Inputs → Outputs | Dependencies | AuthN / AuthZ | Logging | Error handling | Deployment unit | Status |
|---|---|---|---|---|---|---|---|---|---|---|---|---|
| C-01 | React SPA | Request form, own-request list, request-type admin | React 18, Vite | `App.tsx`, `features/admin-request-types/` | `index.html` → `main.tsx` | User input → REST calls | C-02, API | Token from C-02 | none | Alert box with error text | Web App Service | [PARTIAL]{.badge .partial} (no approver/auditor screens) |
| C-02 | MSAL auth module | Redirect sign-in and token acquisition | MSAL Browser 3, MSAL React 2 | `auth.ts`, `main.tsx`, `api.ts` | `MsalAuthenticationTemplate` | Account → access token | Entra ID | Public client, sessionStorage; interactive fallback | none | Redirect on `InteractionRequiredAuthError` | Web App Service | [IMPLEMENTED]{.badge .ok} |
| C-03 | API host and pipeline | Startup, DI, middleware, migrations | ASP.NET Core 8 | `Program.cs` | `Program` | HTTP → endpoints | Entra, KV, AI, EF, Graph | JWT + fallback policy + role policies + Auditor write-block | ILogger, App Insights | Framework defaults | API App Service | [IMPLEMENTED]{.badge .ok} |
| C-04 | RequestsController | Submit, own reads, decision, fulfilment, retry routing | ASP.NET Core MVC | `Controllers/RequestsController.cs` | `api/requests` | DTOs → `RequestResponse` | C-07, C-08 | Policies + ownership filter | — | `NotFound` / `BadRequest` | API | [IMPLEMENTED]{.badge .ok} |
| C-05 | RequestTypesController | Request-type administration | ASP.NET Core MVC | `Controllers/RequestTypesController.cs` | `api/request-types` | DTOs → `RequestTypeResponse` | C-08 | `CanReadRequestTypes`, `CanAdminister` | — | `NotFound` / `BadRequest` | API | [IMPLEMENTED]{.badge .ok} |
| C-06 | Audit and SecurityReview controllers | Paged read-all with history; access-request review | ASP.NET Core MVC | `AuditController.cs`, `SecurityReviewController.cs` | `api/audit`, `api/security` | page → `PagedResult` | C-08 | `CanAudit`, `CanSecurityReview` | — | — | API | [IMPLEMENTED]{.badge .ok} |
| C-07 | WorkflowService | Lifecycle transitions with audit and concurrency | C# | `Services/WorkflowService.cs` | DI (scoped) | Request + action → status | C-08, C-09, C-10 | n/a | — | `ConcurrentTransitionException`, `RoutingResult` | API | [IMPLEMENTED]{.badge .ok} |
| C-08 | SmartServeDbContext + migration | Persistence model and schema | EF Core 8 | `Data/`, `Migrations/` | `IDbContextFactory` | Entities ↔ SQL | Azure SQL (private endpoint) / In-Memory | Managed identity (Entra-only SQL) | EF logging | Exceptions propagate (500) | API | [IMPLEMENTED]{.badge .ok} |
| C-09 | Notification services | E-mail with outcome records; stale-send reconciliation | C#, Graph REST | `Services/NotificationService.cs`, `NotificationReconciliationService.cs`, `Services/Email/` | DI, hosted service | Template + request → NotificationRecord | C-10, Graph | Managed identity → Graph `Mail.Send` | — | Outcome *NotSent*/*Failed* with reason | API | [IMPLEMENTED]{.badge .ok} |
| C-10 | Directory service | User and manager lookup | C#, Graph REST | `Services/Directory/` | DI | User ID → user/manager | Graph | Managed identity → Graph directory read | — | `DirectoryUnavailableException` | API | [IMPLEMENTED]{.badge .ok} |
| C-11 | Health endpoint | Readiness including DB | Minimal API | `Program.cs` | `/health` | — → Healthy / 503 | C-08 | **Requires a token** | — | 503 when the DB is unreachable | API | [IMPLEMENTED]{.badge .ok} |
| C-12 | Test suite | Integration, authorization, workflow, atomicity tests | xUnit, SQLite | `src/backend/SmartServe.Tests` | `dotnet test` | — → results | C-03…C-10 | `TestAuthHandler` | trx (CI) | — | n/a | [IMPLEMENTED]{.badge .ok} |
| I-01 | Bicep template | Environment resources, network and RBAC | Bicep | `infra/main.bicep` | `azure/arm-deploy` | Parameters → resources | Azure RM | OIDC deployer | ARM | Deployment fails | Resource group | [IMPLEMENTED]{.badge .ok} |
| I-02 | One-time setup script | Deploy identity, Entra apps, GitHub secrets | PowerShell, Azure CLI, GitHub CLI | `infra/scripts/setup-dev.ps1` | Manual, once | — → identities and settings | Entra ID, Azure, GitHub | Run by a privileged user | Console | Stops on first error; idempotent | n/a | [IMPLEMENTED]{.badge .ok} |
| I-03..05 | CI, security and deploy workflows | Build/test/scan/deploy | GitHub Actions | `.github/workflows/` | triggers | Code → artifacts/deployments | Azure, GitHub | OIDC, environments | Actions logs | Fail job / smoke gate | GitHub | [IMPLEMENTED]{.badge .ok} |
| P-01..08 | Agentic SDLC platform | Requirement → code automation, then hand-off to CI/CD | Python, Copilot CLI | `scripts/sdlc`, `config`, `.github/agents` | `python -m scripts.sdlc.run` | Issue → artifacts/PRs | GitHub, Copilot | Env-stripped tokens, allowlists | Structured JSON logs, reports | QC, diagnosis, fail-safe | GitHub Actions | [IMPLEMENTED]{.badge .ok} |

Table: Table 12.1 — Component inventory (full version in `analysis/component-inventory.md`)

# Application Architecture {#application-architecture}

## Frontend

![Figure 13 — Frontend architecture](diagrams/rendered/12-frontend-architecture.png)

- **Sign-in gate** (`main.tsx`): when `VITE_ENTRA_CLIENT_ID` is set, the app is wrapped in `MsalAuthenticationTemplate` with a redirect sign-in for the API scope, so nothing renders until the user is signed in. Without that setting (local demo) the app renders without sign-in and the API returns 401.
- **Screens:** a *Requests* tab (new-request form filtered to active request types of the chosen kind, and a table of the user's own requests) and a *Manage request types* tab (`AdminRequestTypesPage.tsx`: create, edit, deactivate). There is no router, global store or UI library.
- **HTTP wrapper** (`api.ts`): adds `Content-Type`, a random `x-correlation-id` and the bearer token from `acquireTokenSilent`; on `InteractionRequiredAuthError` it starts an interactive redirect. Any non-2xx response throws and is shown in an alert region (`role="alert"`). It also defines calls for decisions, fulfilment, retry routing, audit and security review that no screen uses yet.
- **Configuration**: build-time `VITE_*` variables, supplied by the DEV pipeline from GitHub variables. The dev server proxies `/api` and `/health` to `http://localhost:5000`.
- **Tests:** 5 Vitest tests (`App.test.tsx`, `apiFixture.test.ts`, `AdminRequestTypesPage.test.tsx`).
- **Gaps:**
    - No screens for decisions, fulfilment, retry routing, audit or security review.
    - No App Insights browser telemetry.

## Backend

![Figure 14 — Backend architecture: startup configuration and request pipeline](diagrams/rendered/13-backend-architecture.png)

- **Startup** (`Program.cs`), in order:
    1. Optional Key Vault configuration provider (`DefaultAzureCredential`; the user-assigned identity is selected through the `AZURE_CLIENT_ID` app setting).
    2. App Insights.
    3. Authentication: Entra ID JWT, or `TestAuthHandler` in the *Testing* environment only.
    4. Authorization: a fallback policy requiring an authenticated user, plus nine named policies.
    5. `IDbContextFactory<SmartServeDbContext>`: SQL Server when a connection string is set; In-Memory only in Development/Testing. Outside those environments a missing connection string stops startup.
    6. Directory and e-mail services: Graph-based outside Development/Testing, in-memory/unconfigured inside.
    7. `NotificationService`, `WorkflowService`, and `NotificationReconciliationService` (hosted, every 5 minutes).
    8. Controllers with `JsonStringEnumConverter`; Swagger; CORS policy `spa` (origins from `Cors:AllowedOrigins`; Bicep sets the deployed web origin).
    9. `MigrateAsync` (relational) or `EnsureCreatedAsync` (In-Memory), request-type seeding, and one reconciliation pass.
- **Pipeline order:**
    1. Swagger (Development only).
    2. HTTPS redirection.
    3. Security headers middleware.
    4. CORS.
    5. Authentication.
    6. Auditor write-block (403 for POST/PUT/PATCH/DELETE when the caller has the Auditor role).
    7. Authorization.
    8. Controllers, plus `/health` (requires authorization; checks database connectivity).
- **Not configured:** global exception handler / ProblemDetails, rate limiting, HSTS, response compression, output caching, API versioning.
