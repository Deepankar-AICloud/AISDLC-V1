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
| C1 | Submit a request (title, description, category) | `POST /api/requests` | Form in `App.tsx` | [IMPLEMENTED]{.badge .ok} (see enum contract gap, §16.4) |
| C2 | List requests (own for plain employees, all for other roles) | `GET /api/requests` | Table in `App.tsx` | [IMPLEMENTED]{.badge .ok} |
| C3 | View a request by ID with ownership enforcement | `GET /api/requests/{id}` | `api.get` defined, no UI | [PARTIAL]{.badge .partial} |
| C4 | Stage decision (Manager / Security / IT) | `POST /api/requests/{id}/decision` | `api.decide` defined, no UI | [PARTIAL]{.badge .partial} |
| C5 | Requester confirms provisioning and closes the request | `POST /api/requests/{id}/confirm` | `api.confirm` defined, no UI | [PARTIAL]{.badge .partial} |
| C6 | Add comments | `POST /api/requests/{id}/comments` | `api.comment` defined, no UI | [PARTIAL]{.badge .partial} |
| C7 | Read audit trail (≤ 500 newest, optional request filter) | `GET /api/audit` | none | [PARTIAL]{.badge .partial} |
| C8 | Health probe | `GET /health` (anonymous) | — | [IMPLEMENTED]{.badge .ok} |
| C9 | E-mail notifications on status change and to managers | — | — | [PLANNED]{.badge .planned} (ARCH-23, TASK-010/011) |
| C10 | Request-type management by AppAdmin | — (`CanAdminister` policy unused) | — | [PLANNED]{.badge .planned} (TASK-012) |
| C11 | Separate service-request workflow (submit-only) | — (all categories use the same chain) | — | [PLANNED]{.badge .planned} (TASK-015) |
| C12 | File attachments in Blob Storage | — (storage provisioned, no code) | — | [NOT CONFIRMED]{.badge .nc} |

Table: Table 4.1 — Capabilities and implementation status

## Out of scope (current workspace)

The workspace contains none of the following: a mobile client, offline mode, integrations with ITSM tools (e.g. ServiceNow), automatic provisioning into GitHub/Azure/VPN, reporting dashboards, or multi-tenancy. These are **not confirmed from the current workspace**.

# User Roles and Personas {#user-roles}

Roles are string constants in `src/backend/SmartServe.Api/Domain/Enums.cs` (class `Roles`). Entra ID must issue them as **app roles** in the `roles` claim. The app-registration manifest is not part of the workspace (§34).

| Role | Persona | Allowed actions in code | Policy / check |
|---|---|---|---|
| Employee | Any staff member | Create requests; list/read **own** requests; comment on own requests; confirm own provisioned requests | `CanCreateRequest`; ownership filter `OnlyEmployee()`; requester check in `Confirm` |
| Manager | Line manager | Create; list/read **all** requests; decide at the *Manager* stage | `CanApprove` + stage check |
| SecurityReviewer | Information security | Create; list/read all; decide at the *Security* stage | `CanApprove` + stage check |
| ItAdmin | IT operations | Create; list/read all; decide at the *IT* stage (provisioning) | `CanApprove` + stage check |
| AppAdmin | Portal administrator | Create; list/read all; read the audit trail; `CanAdminister` defined but no endpoint uses it | `CanCreateRequest`, `CanAudit` |
| Auditor | Compliance | List/read all requests; read the audit trail | `CanAudit` |

Table: Table 5.1 — Roles and permissions as implemented

> **Note.** Users holding several roles get the union of their permissions. Anyone who is not a plain Employee can list and read **all** requests; there is no direct-report scoping for managers. The Architecture artifact (ARCH-23) treats several of these mappings as *(proposed)*, confirming only "employee: own requests" and "auditor: all requests, read-only" (§34).

![Figure 3 — Authorization model: roles → policies → actions](diagrams/rendered/18-authorization-model.png)

# Functional Requirements {#functional-requirements}

Requirements come from the approved artifacts for issue #23 (`docs/brd/BRD-23.md`, `docs/prd/PRD-23.md`, `docs/epic/EPIC-23.md`, `docs/tasks/TASK-23.md`) and are mapped to code.

| Requirement | Summary | Implementation evidence | Status |
|---|---|---|---|
| BRD-REQ-001 / PRD-FR-001 | Employee request submission | `AccessRequestsController.Create`, `App.tsx` form | [IMPLEMENTED]{.badge .ok} |
| BRD-REQ-002 / PRD-FR-002 | Review, approval, rejection, tracking | `Decide`, `WorkflowService.Advance/CurrentStage`, `List`, `GetById` | [IMPLEMENTED]{.badge .ok} (API) |
| BRD-REQ-003 / PRD-FR-003 | Role permissions for six roles | `Program.cs` policies, controller checks | [IMPLEMENTED]{.badge .ok} |
| BRD-REQ-004 / PRD-FR-004 | Notifications | No notification code | [PLANNED]{.badge .planned} |
| BRD-REQ-009 / PRD-NFR-005 | Request history and audit information | `AuditEntry`, `AuditAsync`, `AuditController` | [PARTIAL]{.badge .partial} — old/new status not recorded; list capped at 500 |
| TASK-012 | Request-type management (AppAdmin) | none | [PLANNED]{.badge .planned} |
| TASK-015 | Service-request submit-only workflow | none (single chain for all categories) | [PLANNED]{.badge .planned} |

Table: Table 6.1 — Functional requirement traceability

# Non-Functional Requirements {#non-functional-requirements}

`docs/nfr/NFR-23.md` defines five verifiable NFRs. Performance, availability, scalability, retention and DR targets are deliberately recorded there as open questions; none are invented here.

| NFR | Requirement | Evidence | Status |
|---|---|---|---|
| NFR-001 | Every API endpoint requires a valid Entra ID token; no anonymous endpoint | `[Authorize]` on controllers; **`/health` is `AllowAnonymous()`** (`Program.cs`) and tested as anonymous | [PARTIAL]{.badge .partial} |
| NFR-002 | Role-based authorization enforced server-side | Policies + controller checks; integration test asserts 401 without a token | [IMPLEMENTED]{.badge .ok} |
| NFR-003 | Secrets via managed identity and Key Vault; none in source control | Key Vault config provider with `DefaultAzureCredential`; placeholders in `appsettings.json`; gitleaks | [IMPLEMENTED]{.badge .ok} |
| NFR-004 | Users reach Azure SQL only through the API (EF Core) | SPA has no DB access; SQL accessed by API via managed identity | [IMPLEMENTED]{.badge .ok} (network still public, §20) |
| NFR-005 | One audit record per status change with actor, timestamp, old and new status | Audit row per action has actor and timestamp, but stores `stage=…;approved=…` not old/new status | [PARTIAL]{.badge .partial} |

Table: Table 7.1 — Non-functional requirements and compliance

Quality attributes that are not quantified in the workspace are performance, availability SLO, RPO/RTO, data retention, accessibility and localisation. They are listed in §34 and must not be assumed.
