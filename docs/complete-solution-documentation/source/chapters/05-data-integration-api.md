# Data Architecture {#data-architecture}

## Entity model

![Figure 15 — Entity relationship diagram (SmartServeDbContext)](diagrams/rendered/11-entity-relationship.png)

Entities are defined in `src/backend/SmartServe.Api/Domain/PortalRequest.cs` and configured in `Data/SmartServeDbContext.cs`. The schema is created by the committed migration `Migrations/20261103093414_InitialPortalRequestModel.cs`, applied at startup.

- All enums are stored as strings (`HasConversion<string>()`).
- `PortalRequests` is indexed on `Kind`, `Status`, `RequesterId`, `ManagerId` and `RequestTypeId`; its foreign key to `RequestTypes` uses `OnDelete: Restrict`.
- `RequestTypes` is indexed on (`Kind`, `IsActive`); `RequestAudits` on `PortalRequestId` and `Timestamp`; `NotificationRecords` on `PortalRequestId` and (`Status`, `LeaseExpiresAt`).
- `PortalRequest` and `NotificationRecord` carry an application-managed GUID `RowVersion` concurrency token, which behaves the same on SQL Server and the In-Memory provider.
- Four request types are seeded on first start: *Application Access* and *VPN Access* (Access), *Laptop Request* and *Password Support* (Service) — marked *(proposed)* in `DbSeeder.cs`.

## Data dictionary

| Entity.Field | Type | Constraints | Classification | Notes |
|---|---|---|---|---|
| PortalRequest.Id | Guid | PK | Internal | Generated in code |
| PortalRequest.Kind | enum (string) | Access / Service | Internal | Drives the workflow |
| PortalRequest.RequestTypeId | Guid | FK → RequestType (restrict) | Internal | Must be active and of the same kind at submission |
| PortalRequest.Title | string | required, ≤200 | Internal / business | Free text from the user |
| PortalRequest.Description | string | required, ≤4000 | Internal / may contain personal or security-sensitive detail | Free text |
| PortalRequest.Status | enum (string) | Submitted, UnderReview, Approved, Rejected, Fulfilled | Internal | Workflow state |
| PortalRequest.RequesterId | string | required, ≤200, indexed | **Personal data** (Entra object ID `oid`) | Ownership key |
| PortalRequest.ManagerId | string? | ≤200, indexed | Personal data | Set when routed to the manager |
| PortalRequest.FulfilledById | string? | ≤200 | Personal data | IT administrator who fulfilled |
| PortalRequest.CreatedAt / UpdatedAt | DateTimeOffset | — | Internal | UTC |
| PortalRequest.RowVersion | Guid | Concurrency token | Internal | Renewed on every transition |
| RequestType.* | Kind, Name ≤200, Description ≤2000, IsActive, CreatedAt, UpdatedAt, DeactivatedAt | Index (Kind, IsActive) | Internal | Deactivation is one-way |
| RequestAudit.* | long Id, PortalRequestId, ActorId ≤200, OldStatus?, NewStatus, Timestamp | Indexed | Personal data (ActorId); security-relevant | Append-only by code; DB-level immutability not enforced |
| NotificationRecord.* | Template, RecipientRole, RecipientAddress ≤320, Status, Reason ≤200, CreatedAt, LeaseExpiresAt, CompletedAt, RowVersion | Indexed | **Personal data** (e-mail address) | Outcome per e-mail: Pending, Accepted, NotSent, Failed |

Table: Table 14.1 — Data dictionary

## Data classification matrix

| Class | Data | Where | Protection in place | Gaps |
|---|---|---|---|---|
| Personal data (identifiers) | `RequesterId`, `ManagerId`, `FulfilledById`, `ActorId` (Entra object IDs), recipient e-mail addresses | Azure SQL | Private endpoint only; Entra-only authentication; TLS in transit; encryption at rest (platform default, **not explicitly configured**) | Retention and erasure policy not defined |
| Business content | Titles, descriptions, decision notes | Azure SQL | Max lengths; strictly scoped reads | No content scanning; decision notes are not stored (accepted by the API but not persisted) |
| Security-relevant records | Audit rows | Azure SQL | Written in the same transaction as the change; Auditor/AppAdmin read | No DB-level append-only enforcement |
| Secrets / configuration | Entra settings, App Insights connection string | App settings, Key Vault | Key Vault RBAC and private endpoint; no SQL password exists | — |
| Telemetry | Requests, dependencies, exceptions | App Insights / Log Analytics (30/90 days) | Workspace-based retention | No PII scrubbing configuration found |

Table: Table 14.2 — Data classification matrix

## Data lifecycle, retention and ownership

- **Create:** request submission, request-type creation. **Update:** routing, decisions, fulfilment, request-type edits and deactivation, notification outcomes. **Delete:** no endpoint deletes data.
- **Retention:** not defined (NFR-23 records audit retention as an open question). Log Analytics retains 30 days (dev/staging) and 90 days (production).
- **Backup:** Azure SQL automated backups apply by default; retention and long-term retention are **not configured** in Bicep (§26).
- **Data owner:** not confirmed from the current workspace (§34).

# Integration Architecture {#integration-architecture}

![Figure 16 — Integration architecture (internal vs external, sync vs async)](diagrams/rendered/15-integration-architecture.png)

| Integration | Direction / style | Protocol | Auth | Status |
|---|---|---|---|---|
| SPA → Microsoft Entra ID | Outbound, synchronous | OAuth 2.0 / OIDC over HTTPS | Public client (PKCE), redirect sign-in | [IMPLEMENTED]{.badge .ok} |
| SPA → SmartServe API | Synchronous | REST/JSON over HTTPS | Bearer JWT (`api://<API_CLIENT_ID>/access_as_user`) | [IMPLEMENTED]{.badge .ok} |
| API → Entra ID | Synchronous (metadata/keys) | HTTPS | — | [IMPLEMENTED]{.badge .ok} |
| API → Azure SQL | Synchronous | TDS over TLS (`Encrypt=True`), private endpoint | `Active Directory Managed Identity` with the user-assigned identity (Entra admin of the server) | [IMPLEMENTED]{.badge .ok} — verified in DEV |
| API → Key Vault | Synchronous at startup | HTTPS, private endpoint | `DefaultAzureCredential` (user-assigned identity, Key Vault Secrets User) | [IMPLEMENTED]{.badge .ok} |
| API → Microsoft Graph (directory) | Synchronous | HTTPS `GET /users/{id}`, `/users/{id}/manager` | Managed identity, `https://graph.microsoft.com/.default` | [PARTIAL]{.badge .partial} — application permission not granted in DEV |
| API → Microsoft Graph (mail) | Synchronous, after commit | HTTPS `POST /users/{sender}/sendMail` | Managed identity | [PARTIAL]{.badge .partial} — `Mail.Send` not granted; sender not set in DEV |
| API → Application Insights | Asynchronous (SDK batching) | HTTPS | Connection string | [IMPLEMENTED]{.badge .ok} |
| API → Blob Storage | — | — | Identity has Storage Blob Data Contributor | [NOT CONFIRMED]{.badge .nc} — no code uses it |
| GitHub Actions → Azure | Synchronous | ARM / Kudu over HTTPS | OIDC federated credential on a user-assigned identity | [IMPLEMENTED]{.badge .ok} |
| Agentic SDLC → GitHub Copilot | Synchronous CLI | HTTPS (Copilot CLI) | `COPILOT_GITHUB_TOKEN` | [IMPLEMENTED]{.badge .ok} |

Table: Table 15.1 — Integration inventory

# API Architecture {#api-architecture}

![Figure 17 — API surface and the policy applied to each endpoint](diagrams/rendered/14-api-architecture.png)

## Endpoint inventory

::: {.landscape}

| Endpoint | Method | Purpose | Handler | Request | Response | Policy (roles) | Status codes | Audit | Source |
|---|---|---|---|---|---|---|---|---|---|
| `/api/requests` | POST | Submit a request | `RequestsController.Create` | `CreateRequestDto {kind, requestTypeId, title ≤200, description ≤4000}` | `RequestResponse` | `CanCreateRequest` (Employee; Manager, ItAdmin, AppAdmin *(proposed)*) | 201, 400, 401, 403 | null → Submitted (+ Submitted → UnderReview when routed) | `RequestsController.cs` |
| `/api/requests` | GET | List own requests | `List` | — | `RequestResponse[]` (newest first) | `CanViewOwnRequests` (Employee) | 200, 401, 403 | — | same |
| `/api/requests/{id}` | GET | Get own request | `GetById` | Route `id:guid` | `RequestResponse` | `CanViewOwnRequests` | 200, 401, 403, 404 | — | same |
| `/api/requests/{id}/decision` | POST | Approve or reject | `Decide` | `DecisionDto {approved, notes ≤2000}` | `RequestResponse` | `CanApprove` (Manager *(proposed)*) | 200, 400, 401, 403, 404 | UnderReview → Approved/Rejected | same |
| `/api/requests/{id}/fulfil` | POST | Fulfil an approved request | `Fulfil` | — | `RequestResponse` | `CanFulfil` (ItAdmin *(proposed)*) | 200, 400, 401, 403, 404 | Approved → Fulfilled | same |
| `/api/requests/{id}/retry-routing` | POST | Retry manager routing | `RetryRouting` | — | `RequestResponse` | `CanRetryRouting` (ItAdmin *(proposed)*) | 200, 401, 403, 404 | Submitted → UnderReview when resolved | same |
| `/api/request-types` | GET | List request types | `RequestTypesController.List` | — | `RequestTypeResponse[]` | `CanReadRequestTypes` (any signed-in user *(proposed)*) | 200, 401 | — | `RequestTypesController.cs` |
| `/api/request-types` | POST | Create type | `Create` | `CreateRequestTypeDto {kind, name, description}` | `RequestTypeResponse` | `CanAdminister` (AppAdmin) | 201, 400, 401, 403 | — | same |
| `/api/request-types/{id}` | PUT | Edit type | `Update` | `UpdateRequestTypeDto {name, description}` | `RequestTypeResponse` | `CanAdminister` | 200, 400, 401, 403, 404 | — | same |
| `/api/request-types/{id}/deactivate` | POST | Deactivate (one-way) | `Deactivate` | — | `RequestTypeResponse` | `CanAdminister` | 200, 401, 403, 404 | — | same |
| `/api/audit/requests` | GET | All requests (paged) | `AuditController.ListAllRequests` | `page`, `pageSize` (default 50, max 200) | `PagedResult<RequestResponse>` | `CanAudit` (Auditor; AppAdmin *(proposed)*) | 200, 401, 403 | — | `AuditController.cs` |
| `/api/audit/requests/{id}/history` | GET | Status history (paged) | `History` | `page`, `pageSize` | `PagedResult<AuditEntryResponse>` | `CanAudit` | 200, 401, 403 | — | same |
| `/api/security/access-requests` | GET | Access requests (paged, read-only) | `SecurityReviewController` | `page`, `pageSize` | `PagedResult<RequestResponse>` | `CanSecurityReview` (SecurityReviewer) | 200, 401, 403 | — | `SecurityReviewController.cs` |
| `/health` | GET | Health including DB | Minimal API | — | `{ "status": "Healthy" }` / 503 | Any authenticated user | 200, 401, 503 | — | `Program.cs` |
| `/swagger` | GET | OpenAPI UI/JSON | Swashbuckle | — | — | Development environment only | 200 | — | `Program.cs` |

Table: Table 16.1 — API inventory (no OpenAPI specification file is committed; Swagger is generated at runtime in Development)

:::

## Sanitised examples

```http
POST /api/requests HTTP/1.1
Host: <API_HOST>
Authorization: Bearer <ACCESS_TOKEN>
x-correlation-id: 7f1c…
Content-Type: application/json

{ "kind": "Access", "requestTypeId": "<REQUEST_TYPE_ID>", "title": "VPN for remote work", "description": "Needed while travelling" }
```

```http
HTTP/1.1 201 Created
Location: /api/requests/<REQUEST_ID>

{ "id": "<REQUEST_ID>", "kind": "Access", "requestTypeId": "<REQUEST_TYPE_ID>", "requestTypeName": "VPN Access",
  "title": "VPN for remote work", "description": "Needed while travelling", "status": "UnderReview",
  "requesterId": "<ENTRA_OBJECT_ID>", "managerId": "<MANAGER_OBJECT_ID>",
  "createdAt": "2026-11-04T10:00:00+00:00", "updatedAt": "2026-11-04T10:00:01+00:00" }
```

If the manager cannot be resolved, the same call returns `"status": "Submitted"` and `"managerId": null`.

## Error responses

- **Validation failures** (`[ApiController]`) return `400` with a `ValidationProblemDetails` body.
- **Workflow rule violations** (unknown or inactive request type, request not awaiting a decision, not approved) return `400` with a plain-text message.
- **Missing token** returns `401`; **missing role** returns `403` (no body). An **Auditor** attempting any write receives `403`, even when holding another role.
- **Others' requests** return `404` from the own-request endpoints, so their existence is not revealed.
- **Unhandled exceptions** return the framework default `500`. No custom ProblemDetails or exception handler is configured.

## Contract

Enums travel as strings in both directions (`JsonStringEnumConverter`); `EnumJsonSerializationTests` and the frontend `apiFixture.test.ts` check the shared `PortalRequest` shape. [IMPLEMENTED]{.badge .ok}
