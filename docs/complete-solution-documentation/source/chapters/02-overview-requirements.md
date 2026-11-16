# Application Overview {#application-overview}

The repository contains two cooperating systems.

| System | Purpose | Main locations |
|---|---|---|
| SmartServe application | IT service and access request portal | `src/backend/SmartServe.Api`, `src/backend/SmartServe.Tests`, `src/frontend`, `infra/` |
| Agentic SDLC platform | AI-assisted, human-governed delivery from requirement to code | `scripts/sdlc/`, `config/`, `.github/agents/`, `.github/workflows/agentic-sdlc*.yml`, `artifact-review.yml`, `feedback-handler.yml`, `docs/` |
| Legacy and auxiliary automation | Earlier Ticket Tracker (Flask) auto-healing demo, council/gatekeeper analysis, CAST imaging, Azure resource analysis | `.github/workflows/deploy.yml`, `automate_pr.yml`, `gatekeeper.yml`, `council-query.yml`, `cast-*.yml`, `azure-resource-analysis.yml`, `daily-repo-status.*` |

Table: Table 3.1 — Systems in the workspace

The legacy Ticket Tracker application code is **not present**. `src/app.py` and the `Dockerfile` do not exist, although `deploy.yml` and `.github/copilot-setup-steps.yaml` still refer to them. This document therefore focuses on SmartServe and the Agentic SDLC platform, and covers the auxiliary workflows only in the CI/CD inventory (§21).

![Figure 2 — Conceptual architecture: capability layers and cross-cutting concerns](diagrams/rendered/02-conceptual-architecture.png)

# Scope and Capabilities {#scope-and-capabilities}

## Capability matrix

| # | Capability | Backend | Frontend | Status |
|---|---|---|---|---|
| C1 | Sign in with Entra ID | JWT validation (`AddMicrosoftIdentityWebApi`) | MSAL redirect sign-in gate (`main.tsx`) | [IMPLEMENTED]{.badge .ok} |
| C2 | Submit an access or service request against an active request type | `POST /api/requests` | Form in `App.tsx` | [IMPLEMENTED]{.badge .ok} |
| C3 | List and view **own** requests | `GET /api/requests`, `GET /api/requests/{id}` | Table in `App.tsx` | [IMPLEMENTED]{.badge .ok} |
| C4 | Route access requests to the requester's manager (Entra ID) | `WorkflowService.TryRouteToManagerAsync`, `GraphDirectoryService` | — (automatic) | [IMPLEMENTED]{.badge .ok} · needs Graph permission in Azure |
| C5 | Manager approves or rejects an access request | `POST /api/requests/{id}/decision` | `api.ts` only, no screen | [PARTIAL]{.badge .partial} |
| C6 | IT administrator fulfils an approved request | `POST /api/requests/{id}/fulfil` | `api.ts` only, no screen | [PARTIAL]{.badge .partial} |
| C7 | IT administrator retries manager routing | `POST /api/requests/{id}/retry-routing` | `api.ts` only, no screen | [PARTIAL]{.badge .partial} |
| C8 | Administer request types (create, edit, deactivate one-way) | `/api/request-types` | `AdminRequestTypesPage.tsx` | [IMPLEMENTED]{.badge .ok} |
| C9 | Auditor reads all requests and each request's status history (paged) | `/api/audit/requests`, `/api/audit/requests/{id}/history` | `api.ts` only, no screen | [PARTIAL]{.badge .partial} |
| C10 | Security reviewer reads access requests (paged, read-only) | `/api/security/access-requests` | `api.ts` only, no screen | [PARTIAL]{.badge .partial} |
| C11 | E-mail notifications to requester and manager | `NotificationService`, `GraphEmailSender`, reconciliation job | — | [IMPLEMENTED]{.badge .ok} · needs Graph permission and sender mailbox in Azure |
| C12 | Health probe including database connectivity | `GET /health` (requires a token) | — | [IMPLEMENTED]{.badge .ok} |
| C13 | Service-request workflow beyond submission | — | — | [NOT CONFIRMED]{.badge .nc} (open question) |
| C14 | File attachments in Blob Storage | — (storage provisioned, no code) | — | [NOT CONFIRMED]{.badge .nc} |

Table: Table 4.1 — Capabilities and implementation status

## Out of scope (current workspace)

The workspace contains none of the following: a mobile client, offline mode, integrations with ITSM tools (e.g. ServiceNow), automatic provisioning into GitHub/Azure/VPN, reporting dashboards, or multi-tenancy. These are **not confirmed from the current workspace**.

# User Roles and Personas {#user-roles}

Roles are string constants in `src/backend/SmartServe.Api/Domain/Enums.cs` (class `Roles`). Entra ID issues them as **app roles** in the `roles` claim. For DEV, the roles are defined on the *SmartServe API (dev)* app registration by `infra/scripts/setup-dev.ps1`, which also assigns the person running it the Employee role.

| Role | Persona | Allowed actions in code | Policy | Mapping status |
|---|---|---|---|---|
| Employee | Any staff member | Submit requests; list/read **own** requests only | `CanCreateRequest`, `CanViewOwnRequests` | Confirmed |
| Manager | Line manager | Submit; approve or reject access requests that are *UnderReview* | `CanCreateRequest`, `CanApprove` | *(proposed)* |
| SecurityReviewer | Information security | Read access requests only (paged); no decisions | `CanSecurityReview` | Confirmed |
| ItAdmin | IT operations | Submit; fulfil approved requests; retry manager routing | `CanCreateRequest`, `CanFulfil`, `CanRetryRouting` | *(proposed)* |
| AppAdmin | Portal administrator | Submit; administer request types; read all requests and histories | `CanCreateRequest`, `CanAdminister`, `CanAudit` | *(proposed)* |
| Auditor | Compliance | Read all requests and histories; **any write is blocked**, even with another role | `CanAudit` + Auditor write-block middleware | Confirmed |

Table: Table 5.1 — Roles and permissions as implemented

> **Note.** Reading requests is strictly scoped: `GET /api/requests` returns only the caller's own requests, and only Employees may call it. Other roles see requests only through their dedicated endpoints (audit, security review). The decision endpoint accepts any user with the Manager role; it does not check that the caller is the manager the request was routed to (§30, R-05).

![Figure 3 — Authorization model: roles → policies → actions](diagrams/rendered/18-authorization-model.png)

# Functional Requirements {#functional-requirements}

Requirements come from the approved artifacts for issue #23 (`docs/brd/BRD-23.md`, `docs/prd/PRD-23.md`, `docs/epic/EPIC-23.md`, `docs/tasks/TASK-23.md`) and are mapped to code.

| Requirement | Summary | Implementation evidence | Status |
|---|---|---|---|
| BRD-REQ-001 / PRD-FR-001 | Employee request submission | `RequestsController.Create`, `WorkflowService.SubmitAsync`, `App.tsx` form | [IMPLEMENTED]{.badge .ok} |
| BRD-REQ-002 / PRD-FR-002 | Review, approval, rejection, fulfilment, tracking | `Decide`, `Fulfil`, `RetryRouting`, `List`, `GetById` | [IMPLEMENTED]{.badge .ok} (API) · [PARTIAL]{.badge .partial} (no approver UI) |
| BRD-REQ-003 / PRD-FR-003 | Role permissions for six roles | `Program.cs` policies, Auditor write-block, `RoleScopeTests`, `EndpointAuthorizationTests` | [IMPLEMENTED]{.badge .ok} (several mappings *(proposed)*) |
| BRD-REQ-004 / PRD-FR-004 | Notifications | `NotificationService`, `EmailTemplates`, `GraphEmailSender`, `NotificationReconciliationService` | [IMPLEMENTED]{.badge .ok} (DEV needs Graph permission) |
| BRD-REQ-009 / PRD-NFR-005 | Request history and audit information | `RequestAudit` (old/new status) in the same `SaveChanges`; paged `AuditController` | [IMPLEMENTED]{.badge .ok} |
| TASK-012 | Request-type management (AppAdmin) | `RequestTypesController`, `AdminRequestTypesPage.tsx` | [IMPLEMENTED]{.badge .ok} |
| TASK-015 | Service-request submit-only workflow | Service requests stop at *Submitted*; onward flow open | [PARTIAL]{.badge .partial} |

Table: Table 6.1 — Functional requirement traceability

# Non-Functional Requirements {#non-functional-requirements}

`docs/nfr/NFR-23.md` defines five verifiable NFRs. Performance, availability, scalability, retention and DR targets are deliberately recorded there as open questions; none are invented here.

| NFR | Requirement | Evidence | Status |
|---|---|---|---|
| NFR-001 | Every API endpoint requires a valid Entra ID token; no anonymous endpoint | Fallback policy requires an authenticated user; `/health` uses `RequireAuthorization()`; `EndpointAuthorizationTests` checks every endpoint | [IMPLEMENTED]{.badge .ok} |
| NFR-002 | Role-based authorization enforced server-side | Policies, ownership filter, Auditor write-block; `RoleScopeTests` | [IMPLEMENTED]{.badge .ok} |
| NFR-003 | Secrets via managed identity and Key Vault; none in source control | User-assigned identity; Key Vault provider with `DefaultAzureCredential`; Entra-only SQL (no password); gitleaks | [IMPLEMENTED]{.badge .ok} |
| NFR-004 | Users reach Azure SQL only through the API (EF Core) | SQL public access disabled; reachable only through a private endpoint from the API's VNet | [IMPLEMENTED]{.badge .ok} |
| NFR-005 | One audit record per status change with actor, timestamp, old and new status | `RequestAudit` written in the same `SaveChanges` as each transition; `RelationalAtomicityTests` | [IMPLEMENTED]{.badge .ok} |

Table: Table 7.1 — Non-functional requirements and compliance

Quality attributes that are not quantified in the workspace are performance, availability SLO, RPO/RTO, data retention, accessibility and localisation. They are listed in §34 and must not be assumed.
