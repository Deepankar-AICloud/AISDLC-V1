# Development Task Plan

**Source artifacts:** ARCH-23.md (Architecture Plan), NFR-23.md (Non-Functional Requirements) — NFR-23.md's text is now available to this plan and quoted/mapped directly below, replacing the earlier unverifiable citation. Story IDs below are inferred from the confirmed Epic decision list order recorded in the issue thread (submission=US-001, status/review=US-002, approval=US-003, permissions=US-004, notifications=US-005, audit=US-006); the underlying Epic markdown itself was not supplied to this task, so each US-xxx mapping is marked **"(US ID mapped from decision order, not re-verified against Epic text)"**. Any task implementing an ARCH-COMP item labeled `(proposed)` in ARCH-23.md is itself marked `(proposed)` below — it should be built, but its decomposition/endpoint mapping is not source-confirmed and may change. Per the API section of ARCH-23.md, exactly two permission cells are confirmed — Employee GET on own requests, and Auditor GET read-only across all requests and audit history — and every other role-to-endpoint permission (manager approve/reject, IT admin fulfil, app admin request-type management) is **(proposed)**, even where the underlying workflow *behavior* (that a manager approves/rejects, that IT admin fulfils) is itself confirmed. This distinction — confirmed behavior vs. proposed endpoint/permission mapping — is carried through every task below.

## Traceability

| Task | Traces to | Produces |
|---|---|---|
| TASK-001 | ARCH-COMP-001, ARCH-COMP-002 | src/frontend/ (scaffold), src/backend/SmartServe.Api/ (scaffold) |
| TASK-002 | NFR-001, ARCH-COMP-002, ARCH-COMP-012 | src/backend/SmartServe.Api/Auth/EntraIdAuthentication.cs |
| TASK-003 | NFR-002, ARCH-COMP-002, ARCH-COMP-005 | src/backend/SmartServe.Api/Auth/RoleAuthorizationPolicies.cs |
| TASK-004 | NFR-004, ARCH-COMP-002, ARCH-COMP-009, ARCH-COMP-010 | src/backend/SmartServe.Api/Data/SmartServeDbContext.cs, migrations/ |
| TASK-005 | US-001, ARCH-COMP-003 | src/backend/SmartServe.Api/Services/RequestService.cs, POST /api/requests (proposed endpoint shape) |
| TASK-006 | US-002, ARCH-COMP-003 | GET /api/requests/{id}, GET /api/requests/mine (confirmed permission; endpoint shape proposed) |
| TASK-007 | US-003, ARCH-COMP-004 | src/backend/SmartServe.Api/Services/WorkflowEngine.cs (access-request approve/reject; endpoint permission mapping proposed) |
| TASK-008 | US-003, ARCH-COMP-004 | Fulfillment endpoint, status → "Fulfilled" (endpoint permission mapping proposed) |
| TASK-009 | NFR-005, ARCH-COMP-007, ARCH-COMP-010 | src/backend/SmartServe.Api/Services/AuditLoggingModule.cs |
| TASK-010 | US-005, ARCH-COMP-006 | Requester status-change email dispatch |
| TASK-011 | US-005, ARCH-COMP-006 | Manager "waiting for approval" email dispatch |
| TASK-012 | US-004, ARCH-COMP-008 | Request-type CRUD endpoints (capability confirmed; app-admin-only permission mapping proposed) |
| TASK-013 | US-004, NFR-005, ARCH-COMP-002, ARCH-COMP-005 | Auditor read-only endpoints (all requests + history) — confirmed permission |
| TASK-014 | NFR-003, ARCH-COMP-011 | Key Vault + managed identity configuration |
| TASK-015 | ARCH-COMP-004 (proposed scope) | Service-request submission-only workflow stub |
| TASK-016 | ARCH-COMP-002, ARCH-COMP-012 (proposed deployment) | infra/ deployment pipeline (proposed env topology) |
| UT-001…UT-016 | corresponding TASK-xxx | tests/unit/... |
| FT-001, FT-002, FT-003 | TASK-005/006/007/008, TASK-009/010/011, TASK-013 | tests/functional/... |

## Tasks

### TASK-001 — Scaffold portal solution (proposed consolidation)
- **Traces to:** ARCH-COMP-001, ARCH-COMP-002
- **Scope:** Create the single React/TypeScript SPA and the single .NET 8 Web API project per the architecture's `(proposed)` consolidated decomposition. Decomposition choice itself is not source-confirmed; keep swappable.
- **Files:** `src/frontend/` (Vite/React+TS scaffold), `src/backend/SmartServe.Api/` (.NET 8 Web API scaffold), `SmartServe.sln`
- **Depends on:** none
- **Definition of done:** Both projects build and run locally. **(Proposed, not source-confirmed)**: the API exposes a health-check endpoint — no source artifact specifies this; include it only as a `(proposed)` convenience endpoint, clearly labeled, not a requirement. No business logic yet.
- **Tests:** UT-001

### TASK-002 — Enforce Entra ID authentication on every endpoint
- **Traces to:** NFR-001, ARCH-COMP-002, ARCH-COMP-012
- **Scope:** Configure Microsoft Entra ID (OIDC/JWT bearer) validation as global middleware so no endpoint is anonymous, matching NFR-001: "Every API endpoint requires a valid Microsoft Entra ID token; no endpoint is anonymous." The OIDC token-validation implementation mechanism is **(proposed)** per ARCH-23.md Security/Deployment sections.
- **Files:** `src/backend/SmartServe.Api/Program.cs`, `src/backend/SmartServe.Api/Auth/EntraIdAuthentication.cs`
- **Depends on:** TASK-001
- **Definition of done:** Per NFR-001's verification method — "Test each endpoint with no token, an invalid token, and a valid token" — each endpoint is tested in all three conditions and the outcome differs between "no/invalid token" and "valid token" across all endpoints; no controller/action opts out. Specific HTTP status codes (e.g., 401 vs. 403) are **(proposed)**, not specified by NFR-001, and should be treated as an implementation detail pending confirmation.
- **Tests:** UT-002, FT-003

### TASK-003 — Server-side role-based authorization module
- **Traces to:** NFR-002, ARCH-COMP-002, ARCH-COMP-005
- **Scope:** Implement role enforcement per NFR-002: "The API enforces role-based authorization server-side; UI-only authorization does not satisfy this requirement." Only two permissions are confirmed (employee: own requests; auditor: all requests, read-only); every other role→endpoint mapping is `(proposed)` per the ARCH-23.md API table and must be flagged as such in code comments/config pending confirmation.
- **Files:** `src/backend/SmartServe.Api/Auth/RoleAuthorizationPolicies.cs`
- **Depends on:** TASK-002
- **Definition of done:** Per NFR-002's verification method — "Test API access directly against the confirmed role permissions. Treat unspecified endpoint permissions as proposed." — API-level tests (not UI-level) prove the two confirmed permissions are enforced independent of the UI; all other role mappings are implemented behind clearly labeled `(proposed)` policy stubs, not presented as confirmed.
- **Tests:** UT-003, FT-003

### TASK-004 — EF Core data access layer over Azure SQL
- **Traces to:** NFR-004, ARCH-COMP-002, ARCH-COMP-009, ARCH-COMP-010
- **Scope:** Define `DbContext`, entity models (Request, StatusHistory/Audit, RequestType), and migrations, per NFR-004: "Users access Azure SQL only through the API, which uses Entity Framework Core for data access." Ensure no client ever has a direct connection string — only the API reaches Azure SQL.
- **Files:** `src/backend/SmartServe.Api/Data/SmartServeDbContext.cs`, `src/backend/SmartServe.Api/Data/Entities/`, `migrations/`
- **Depends on:** TASK-001
- **Definition of done:** Per NFR-004's verification method — "Review access configuration and verify through integration tests." — migrations apply cleanly to an Azure SQL (or local SQL) instance, and an integration test confirms no role/client has a database access path other than via the API and EF Core.
- **Tests:** UT-004, FT-003

### TASK-005 — Request submission (US-001)
- **Traces to:** US-001 (US ID mapped from decision order, not re-verified against Epic text), ARCH-COMP-003
- **Scope:** `POST /api/requests` (proposed endpoint shape) persists a new request with status `Submitted` and triggers the confirmed requester "submitted" notification (see TASK-010). **Submission form fields are NOT confirmed by any supplied source artifact** (ARCH-23.md labels the request body "fields proposed — not specified" in both workflow diagrams and its own Design Decisions); do not implement a fixed field set as a confirmed requirement. **On-screen confirmation behavior and request-ID display are likewise NOT confirmed** — ARCH-23.md labels this "proposed — on-screen behavior not specified." Treat the specific field list, confirmation UX, and request-ID presentation as **(proposed)** placeholders or open questions pending stakeholder confirmation; do not present them as settled requirements.
- **Files:** `src/backend/SmartServe.Api/Controllers/RequestsController.cs`, `src/backend/SmartServe.Api/Services/RequestService.cs`, `src/frontend/src/features/submit-request/`
- **Depends on:** TASK-002, TASK-003, TASK-004
- **Definition of done:** Given a submission attempt (fields **(proposed)**, pending confirmation of exact schema), when the API persists it, then status is `Submitted`, an audit record exists (TASK-009), and the requester receives the confirmed "submitted" email (TASK-010). Any on-screen confirmation content, request-ID format, or display behavior implemented is explicitly labeled `(proposed)` in code/UI and is **not** treated as a verified requirement.
- **Tests:** UT-005, FT-001
- **Open questions:** What are the required submission form fields? What on-screen confirmation and request-ID behavior should the UI present?

### TASK-006 — View own requests / status (US-002)
- **Traces to:** US-002 (US ID mapped from decision order, not re-verified against Epic text), ARCH-COMP-003
- **Scope:** `GET /api/requests/mine` and `GET /api/requests/{id}` (proposed endpoint shapes) for the requester; status values restricted to the confirmed set `Submitted, Under Review, Approved, Rejected, Fulfilled`. The employee-own-requests view permission is **confirmed** per the ARCH-23.md API table.
- **Files:** `src/backend/SmartServe.Api/Controllers/RequestsController.cs`, `src/frontend/src/features/my-requests/`
- **Depends on:** TASK-005
- **Definition of done:** Employee can view only their own submitted requests and current status (confirmed permission); auditor's broader read access covered separately in TASK-013.
- **Tests:** UT-006, FT-001

### TASK-007 — Access-request manager approve/reject (US-003)
- **Traces to:** US-003 (US ID mapped from decision order, not re-verified against Epic text), ARCH-COMP-004
- **Scope:** Implement the confirmed access-request workflow behavior: `Submitted → Under Review → manager Approves or Rejects`. Record `Under Review` status + audit entry first, then trigger the confirmed manager "waiting for approval" email (TASK-011). Rejection ends the workflow as `Rejected`. Security reviewers have **no** approve/reject action — read-only only (confirmed). **The endpoint shapes (`POST .../approve`, `POST .../reject`) and the manager-permission mapping to these endpoints are `(proposed)`** per the ARCH-23.md API table — only employee-own-view and auditor-read-only are confirmed permissions; whether approval is restricted to the requester's direct reports is also **(proposed)/open question**.
- **Files:** `src/backend/SmartServe.Api/Services/WorkflowEngine.cs`, `src/backend/SmartServe.Api/Controllers/ApprovalsController.cs`
- **Depends on:** TASK-004, TASK-009
- **Definition of done:** Access request moves to `Under Review` with an audit record before any email send (confirmed ordering); manager approve → `Approved`; manager reject → `Rejected` (terminal) — these are confirmed workflow behaviors. The specific endpoint/permission wiring that grants managers this action, and any direct-report scoping, is implemented only as a `(proposed)` mapping, clearly flagged, pending confirmation. Security reviewer has no approve/reject endpoint access (confirmed non-role).
- **Tests:** UT-007, FT-001
- **Open question:** Is manager approval authority restricted to the requester's direct reports?

### TASK-008 — IT admin fulfillment of approved access requests (US-003)
- **Traces to:** US-003 (US ID mapped from decision order, not re-verified against Epic text), ARCH-COMP-004
- **Scope:** On `Approved`, IT admin fulfils the request (confirmed workflow behavior); status becomes `Fulfilled`; audit entry recorded; requester fulfillment email sent (TASK-010). **The fulfillment endpoint shape and the IT-admin-only permission mapping to it are `(proposed)`** per the ARCH-23.md API table — IT admin is not one of the two confirmed view permissions (employee own, auditor read-all).
- **Files:** `src/backend/SmartServe.Api/Services/WorkflowEngine.cs`, `src/backend/SmartServe.Api/Controllers/FulfillmentController.cs`
- **Depends on:** TASK-007, TASK-009, TASK-010
- **Definition of done:** Given an `Approved` access request, when IT admin fulfils it, then status is `Fulfilled`, an audit record exists, and the requester receives the fulfilled email — these are confirmed outcomes. The endpoint/permission wiring restricting this action to IT admins is implemented only as a `(proposed)` mapping, clearly flagged in code/config, pending confirmation.
- **Tests:** UT-008, FT-001

### TASK-009 — Audit logging on every status change
- **Traces to:** NFR-005, ARCH-COMP-007, ARCH-COMP-010
- **Scope:** Per NFR-005: "Every request status change has one audit record containing the actor, timestamp, old status, and new status." Apply at every transition among `Submitted, Under Review, Approved, Rejected, Fulfilled`. Retention period is an **open question** (per NFR-23.md Open Questions) — do not implement a purge/retention job until confirmed.
- **Files:** `src/backend/SmartServe.Api/Services/AuditLoggingModule.cs`, `src/backend/SmartServe.Api/Data/Entities/AuditRecord.cs`
- **Depends on:** TASK-004
- **Definition of done:** Per NFR-005's verification method — "Exercise each status transition and verify the corresponding audit record and fields." — exercising each status transition produces exactly one corresponding audit record containing actor, timestamp, old status, and new status.
- **Tests:** UT-009, FT-002

### TASK-010 — Requester notification on every status change
- **Traces to:** US-005 (US ID mapped from decision order, not re-verified against Epic text), ARCH-COMP-006
- **Scope:** Send requester an email on every status change (confirmed, not limited to approved/rejected/fulfilled per the authoritative clarification). Email transport/provider is `(proposed)`; specific email content/body is **(proposed)**, not specified in any supplied source artifact.
- **Files:** `src/backend/SmartServe.Api/Services/NotificationService.cs`
- **Depends on:** TASK-009
- **Definition of done:** Each of the five confirmed status transitions triggers one requester email. The specific email content requirement (e.g., that content must include the new status) and any failure-handling behavior for send errors are **(proposed)** — not specified by any supplied source artifact — and must be labeled as such, not presented as a verified requirement.
- **Tests:** UT-010, FT-002
- **Open question:** What content must each notification email contain, and how should send failures be handled?

### TASK-011 — Manager "waiting for approval" notification
- **Traces to:** US-005 (US ID mapped from decision order, not re-verified against Epic text), ARCH-COMP-006
- **Scope:** When an access request enters `Under Review`, email the requester's manager that a request awaits approval — sent only after the `Under Review` status and its audit entry (TASK-009) are recorded (confirmed ordering).
- **Files:** `src/backend/SmartServe.Api/Services/NotificationService.cs`
- **Depends on:** TASK-007, TASK-009
- **Definition of done:** Given a request transitions to `Under Review`, when the transition completes, then the status + audit record exist first and the manager email is sent after, in that order (confirmed).
- **Tests:** UT-011, FT-002

### TASK-012 — Application admin: manage request types
- **Traces to:** US-004 (US ID mapped from decision order, not re-verified against Epic text), ARCH-COMP-008
- **Scope:** CRUD (create, edit, deactivate) of request types. **The capability itself** — application administrators create, edit, and deactivate request types — **is confirmed** per the authoritative issue comment cited in ARCH-23.md. **The specific endpoint shape (`GET/POST/PUT /api/request-types`) and the permission mapping restricting this to app admins are `(proposed)`** per the ARCH-23.md API table — app-admin is not one of the two confirmed view permissions.
- **Files:** `src/backend/SmartServe.Api/Controllers/RequestTypesController.cs`, `src/frontend/src/features/admin-request-types/`
- **Depends on:** TASK-003, TASK-004
- **Definition of done:** App admin can create, edit, and deactivate a request type (confirmed capability). The restriction of this capability to the app-admin role at the endpoint level, and the resulting behavior for non-admin callers, is implemented only as a `(proposed)` permission mapping, clearly flagged pending confirmation — not asserted as a verified access-control guarantee.
- **Tests:** UT-012, FT-001

### TASK-013 — Auditor read-only access to all requests and history
- **Traces to:** US-004 (US ID mapped from decision order, not re-verified against Epic text), NFR-005, ARCH-COMP-002, ARCH-COMP-005
- **Scope:** Confirmed permission: auditors may view all requests and their full audit history, read-only, with no mutation endpoints reachable.
- **Files:** `src/backend/SmartServe.Api/Controllers/AuditController.cs`
- **Depends on:** TASK-003, TASK-009
- **Definition of done:** Given an auditor role token, when calling the audit/history endpoints, then all requests and their status-change history are returned (confirmed permission), and any write attempt by the auditor role is rejected. The specific endpoint shape and exact rejection status code are **(proposed)**, not specified in any supplied source artifact.
- **Tests:** UT-013, FT-003

### TASK-014 — Key Vault + managed identity secret handling
- **Traces to:** NFR-003, ARCH-COMP-011
- **Scope:** Per NFR-003: "Secrets use managed identity and Azure Key Vault; secrets must not be stored in source control." Wire API to retrieve secrets (DB connection, etc.) exclusively via managed identity + Azure Key Vault. Specific secret types (connection strings, API keys, certificates) are **(proposed/open question)**, not enumerated in any supplied source artifact.
- **Files:** `src/backend/SmartServe.Api/Program.cs`, `infra/keyvault-config.bicep` (proposed), `.gitignore` review
- **Depends on:** TASK-001
- **Definition of done:** Per NFR-003's verification method — "Review deployment configuration and run secret scanning." — a secret scan of the repository finds no committed secrets, and the deployed API resolves configuration via managed identity against Key Vault.
- **Tests:** UT-014, FT-003
- **Open question:** What specific secret types must be stored in Key Vault?

### TASK-015 — Service-request workflow stub (proposed, submission-only confirmed)
- **Traces to:** ARCH-COMP-004 (proposed scope beyond submission)
- **Scope:** Implement only what is confirmed for IT service (non-access) requests: employee submits → status `Submitted` → requester is emailed. All further service-request steps, assignment, approvers, or transitions are **(proposed)** by analogy only and explicitly out of scope pending decision; do not implement them speculatively.
- **Files:** `src/backend/SmartServe.Api/Services/WorkflowEngine.cs` (service-request branch)
- **Depends on:** TASK-005, TASK-010
- **Definition of done:** Given a service (non-access) request submission, when saved, then status is `Submitted` and the requester receives a confirmation email; no approval/fulfillment logic exists for this request type yet.
- **Tests:** UT-015, FT-001
- **Open question:** What is the full IT service-request approval/fulfillment workflow, including whether a manager "waiting for approval" email applies to service requests?

### TASK-016 — Deployment pipeline (proposed environment topology)
- **Traces to:** ARCH-COMP-002, ARCH-COMP-012 (all environment/hosting choices proposed)
- **Scope:** Stand up a deployment pipeline for Dev/Staging/Production per the architecture's `(proposed)` topology. No environment, including Production, is treated as confirmed; hosting service choice (App Service vs. Container Apps vs. Static Web Apps) remains open.
- **Files:** `infra/` (Bicep/Terraform, proposed), `.github/workflows/deploy.yml` (proposed)
- **Depends on:** TASK-002, TASK-004, TASK-014
- **Definition of done:** A build artifact deploys successfully to at least one `(proposed)` environment end-to-end (UI reaches API reaches DB) without manual secret entry.
- **Tests:** FT-003
- **Open question:** Confirm actual environment names/count and hosting compute before treating this as final.

### UT-001 — Solution scaffold tests
- **Verifies:** TASK-001
- **Cases:** frontend build succeeds; API builds and starts; **(proposed)** health-check endpoint returns a success response, if implemented

### UT-002 — Entra ID authentication tests
- **Verifies:** TASK-002
- **Cases:** per NFR-001's verification method — no token (reject); invalid token (reject); valid token (allow). Specific HTTP status codes are **(proposed)**. Token near-expiry handling is **(proposed)/open question**, not specified by NFR-001.

### UT-003 — Role authorization policy tests
- **Verifies:** TASK-003
- **Cases:** employee accesses own request (confirmed: allowed); employee accesses another's request (confirmed denial, by exclusion — only own-request access is granted); auditor read access to all requests (confirmed: allowed); auditor write attempt (confirmed denial — auditor permission is read-only)

### UT-004 — EF Core / Azure SQL data access tests
- **Verifies:** TASK-004
- **Cases:** migration applies cleanly; entity CRUD round-trip; no direct external connection string path exists (per NFR-004)

### UT-005 — Request submission tests
- **Verifies:** TASK-005
- **Cases:** happy path (returns a request ID and status `Submitted`); field set and validation rules are **(proposed)**, pending confirmed submission-form fields — test against whatever `(proposed)` field set is implemented, not an assumed schema. Duplicate-submission handling is **(proposed)/open question**, not specified in any supplied source artifact.

### UT-006 — View own requests tests
- **Verifies:** TASK-006
- **Cases:** employee sees own requests (confirmed); employee cannot see others' requests (confirmed, by exclusion); empty-list edge case

### UT-007 — Manager approve/reject tests
- **Verifies:** TASK-007
- **Cases:** approve transitions to `Approved` (confirmed behavior); reject transitions to `Rejected`, terminal (confirmed behavior); security reviewer attempt to approve/reject is denied (confirmed non-role). The specific endpoint/permission check granting the manager role access is **(proposed)**, tested only against whatever `(proposed)` mapping is implemented.

### UT-008 — IT admin fulfillment tests
- **Verifies:** TASK-008
- **Cases:** fulfil an `Approved` request → `Fulfilled` (confirmed behavior); attempt to fulfil a non-`Approved` request — behavior **(proposed)/open question**, not specified in any supplied source artifact; fulfilment by a non-IT-admin role — endpoint/permission check is **(proposed)**, tested against whatever mapping is implemented

### UT-009 — Audit logging tests
- **Verifies:** TASK-009
- **Cases:** per NFR-005's verification method — each of the five status transitions creates exactly one audit record containing actor, timestamp, old status, and new status. Concurrent-transition handling is **(proposed)/open question**, not specified by NFR-005.

### UT-010 — Requester notification tests
- **Verifies:** TASK-010
- **Cases:** one email is sent on each confirmed status change. Specific email content requirements and email-send-failure handling are **(proposed)/open question**, not specified in any supplied source artifact.

### UT-011 — Manager notification ordering tests
- **Verifies:** TASK-011
- **Cases:** audit record exists before the manager email dispatch call (confirmed ordering); email sent exactly once per `Under Review` transition; whether a manager email applies to non-access (service) requests is **(proposed)/open question** (see TASK-015)

### UT-012 — Request type management tests
- **Verifies:** TASK-012
- **Cases:** create/edit/deactivate by app admin (confirmed capability, happy path). The endpoint-level permission check restricting this to app admins, and any behavior for a type in active use, are **(proposed)/open question**, not specified in any supplied source artifact.

### UT-013 — Auditor read-only tests
- **Verifies:** TASK-013
- **Cases:** auditor retrieves all requests + history (confirmed); auditor write attempt denied (confirmed, by exclusion). Pagination/large-result-set behavior is **(proposed)/open question**, not specified in any supplied source artifact.

### UT-014 — Key Vault / managed identity tests
- **Verifies:** TASK-014
- **Cases:** per NFR-003's verification method — secret retrieved via managed identity; secret-scan of source finds nothing. Behavior for a missing/misconfigured identity is **(proposed)/open question**, not specified by NFR-003.

### UT-015 — Service-request submission stub tests
- **Verifies:** TASK-015
- **Cases:** submission sets `Submitted` and emails requester (confirmed scope); no approval endpoint exists yet for service requests (expected gap, not a bug, per the open service-request workflow question)

### UT-016 — Deployment configuration tests
- **Verifies:** TASK-016
- **Cases:** pipeline runs end-to-end without manual secrets. Rollback behavior is **(proposed)/open question**, not specified in any supplied source artifact — test only if implemented.

### FT-001 — Access-request end-to-end functional test
- **Verifies:** TASK-005, TASK-006, TASK-007, TASK-008
- **Cases:** submit → `Under Review` → manager approve → IT admin fulfil → `Fulfilled`, verified via the employee's own-request view (confirmed permission) at each stage. Submission field content, confirmation UX, and the manager/IT-admin endpoint permission mappings exercised along the way are **(proposed)**, per TASK-005/007/008.

### FT-002 — Notifications and audit functional test
- **Verifies:** TASK-009, TASK-010, TASK-011
- **Cases:** per NFR-005's verification method and the confirmed notification behaviors — full status lifecycle produces one audit record (with actor/timestamp/old/new status) and one requester email per transition, plus one manager email at `Under Review`, in the confirmed order (status + audit before email). Email content assertions beyond "one email per transition" are **(proposed)/open question**.

### FT-003 — Security and access-control functional test
- **Verifies:** TASK-002, TASK-003, TASK-013, TASK-014, TASK-016
- **Cases:** per NFR-001/NFR-002/NFR-003's verification methods — all endpoints reject missing/invalid tokens and accept valid tokens; the two confirmed role permissions (employee-own, auditor-read-all) are enforced server-side; a secret scan finds no committed secrets; a deployed environment is reachable only via an API-mediated database path (per NFR-004). Specific HTTP status codes and any other role-to-endpoint denial not among the two confirmed permissions are **(proposed)**, tested only against whatever `(proposed)` mapping is implemented.

## Definition of done

The plan as a whole is complete when:
- Every confirmed capability in ARCH-23.md (access-request lifecycle statuses, manager approve/reject behavior, IT admin fulfillment behavior, requester notification on every status change, manager "waiting for approval" notification, audit logging at every status change, request-type management capability, Entra ID auth on every endpoint, server-side role authorization for the two confirmed permissions, Key Vault/managed-identity secret handling, EF Core/Azure SQL as the sole data path) has at least one TASK-xxx and at least one UT-xxx, with FT-xxx coverage for cross-cutting behavior (FT-001/002/003).
- Every NFR-001 through NFR-005 in NFR-23.md has a corresponding task and test exercising exactly the verification method stated for that NFR ID in NFR-23.md (quoted inline in each task above); no numeric target is implemented beyond what each NFR specifies (pass/fail checks only, per NFR-23.md's "Target" section).
- Endpoint-level permission mappings beyond the two confirmed ones (employee-own-view, auditor-read-all) — including manager approve/reject, IT admin fulfil, and app-admin request-type management — are implemented and tested only as explicitly flagged `(proposed)` mappings, never presented as confirmed access-control guarantees, even where the underlying workflow behavior they gate is itself confirmed.
- Submission form fields, on-screen confirmation behavior, and request-ID display (TASK-005) are implemented, if at all, only as flagged `(proposed)` placeholders, and are recorded as open questions rather than invented as settled requirements.
- Test-case specifics not supported by ARCH-23.md or NFR-23.md — including particular HTTP status codes, a health-check endpoint, token-expiry handling, duplicate-submission behavior, email content/failure handling, pagination, and rollback — are labeled `(proposed)`/open question in the relevant UT-/FT- case lists above, and are not asserted as verified requirements.
- Items labeled `(proposed)` in ARCH-23.md (component decomposition, internal module boundaries, endpoint/permission mappings beyond the two confirmed ones, deployment topology, email transport, OIDC validation mechanism, service-request workflow beyond submission) are implemented only as flagged placeholders — explicitly marked `(proposed)` in code/config — and are not presented as confirmed requirements.
- Open questions carried from NFR-23.md (performance, scalability, availability/recovery, audit retention, privacy/compliance, observability, maintainability, accessibility, disaster recovery) and from ARCH-23.md (manager-approval direct-reports restriction, full service-request workflow, submission form fields/confirmation UX, email content/failure handling, secret-type enumeration) remain recorded as open questions in this plan and are not resolved by invented values in any task's Definition of done.
- Each individual task's own "Definition of done" (stated per task above) is independently verifiable without requiring the other tasks to be complete, except where an explicit "Depends on" relationship exists.