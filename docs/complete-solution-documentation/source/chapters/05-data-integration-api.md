# Data Architecture {#data-architecture}

## Entity model

![Figure 15 — Entity relationship diagram (SmartServeDbContext)](diagrams/rendered/11-entity-relationship.png)

Entities are defined in `src/backend/SmartServe.Api/Domain/AccessRequest.cs` and configured in `Data/SmartServeDbContext.cs`:

- `Status` and `Category` are stored as strings.
- `RequesterId` and `Status` are indexed.
- `AuditEntries` is indexed on `AccessRequestId` and `Timestamp`.
- `Comments` and `Approvals` cascade-delete with their request.

## Data dictionary

| Entity.Field | Type | Constraints | Classification | Notes |
|---|---|---|---|---|
| AccessRequest.Id | Guid | PK | Internal | Generated in code |
| AccessRequest.Title | string | required, ≤200 | Internal / business | Free text from the user |
| AccessRequest.Description | string | required, ≤4000 | Internal / may contain personal or security-sensitive detail | Free text |
| AccessRequest.Category | enum (string) | 11 values | Internal | Drives `RequiresSecurityReview` |
| AccessRequest.Status | enum (string) | 9 values, indexed | Internal | Workflow state |
| AccessRequest.RequesterId | string | required, ≤200, indexed | **Personal data** (Entra object ID `oid`) | Ownership key |
| AccessRequest.AssignedToId | string? | ≤200 | Personal data | Never set by current code |
| AccessRequest.RequiresSecurityReview | bool | — | Internal | Computed at creation |
| AccessRequest.CreatedAt / UpdatedAt / ClosedAt | DateTimeOffset | — | Internal | UTC |
| ApprovalStep.* | Stage, DecidedById, Approved, Notes ≤2000, DecidedAt | FK → AccessRequest | Personal data (DecidedById) | One row per decision |
| RequestComment.* | AuthorId, Body ≤4000, CreatedAt | FK → AccessRequest | Personal data / free text | — |
| AuditEntry.* | long Id, AccessRequestId?, ActorId, Action ≤100, Details ≤2000, Timestamp, CorrelationId ≤100 | Indexed | Personal data (ActorId); security-relevant | Written by code only; DB-level immutability not enforced |

Table: Table 14.1 — Data dictionary

## Data classification matrix

| Class | Data | Where | Protection in place | Gaps |
|---|---|---|---|---|
| Personal data (identifiers) | `RequesterId`, `DecidedById`, `AuthorId`, `ActorId` (Entra object IDs) | Azure SQL | TLS in transit; Azure SQL encryption at rest (platform default, **not explicitly configured**) | Retention and erasure policy not defined |
| Business content | Titles, descriptions, notes, comments | Azure SQL | Max lengths; role-based read access | No content scanning; plain employees are isolated only for their own requests |
| Security-relevant records | Approvals, audit entries | Azure SQL | Written by API only; Auditor/AppAdmin read | No DB-level append-only enforcement; read capped at 500 |
| Secrets / configuration | Entra settings, App Insights connection string, SQL admin password | App settings, Key Vault, deployment parameter | Key Vault RBAC, managed identity, `@secure()` parameter | SQL admin password still enabled |
| Telemetry | Requests, dependencies, exceptions | App Insights / Log Analytics (30/90 days) | Workspace-based retention | No PII scrubbing configuration found |

Table: Table 14.2 — Data classification matrix

## Data lifecycle, retention and ownership

- **Create:** request submission. **Update:** decisions, confirmation, comments. **Delete:** no endpoint; cascade rules exist for future use.
- **Retention:** not defined (NFR-23 records audit retention as an open question). Log Analytics retains 30 days (dev/staging) and 90 days (production).
- **Backup:** Azure SQL automated backups apply by default; retention and long-term retention are **not configured** in Bicep (§26).
- **Data owner:** not confirmed from the current workspace (§34).

# Integration Architecture {#integration-architecture}

![Figure 16 — Integration architecture (internal vs external, sync vs async)](diagrams/rendered/15-integration-architecture.png)

| Integration | Direction / style | Protocol | Auth | Status |
|---|---|---|---|---|
| SPA → Microsoft Entra ID | Outbound, synchronous | OAuth 2.0 / OIDC over HTTPS | Public client (PKCE) | [PARTIAL]{.badge .partial} — silent token only |
| SPA → SmartServe API | Synchronous | REST/JSON over HTTPS | Bearer JWT | [IMPLEMENTED]{.badge .ok} |
| API → Entra ID | Synchronous (metadata/keys) | HTTPS | — | [IMPLEMENTED]{.badge .ok} |
| API → Azure SQL | Synchronous | TDS over TLS (`Encrypt=True`), port 1433 | `Active Directory Managed Identity` | [PARTIAL]{.badge .partial} — DB user for the identity not provisioned |
| API → Key Vault | Synchronous at startup | HTTPS | `DefaultAzureCredential` (managed identity) | [IMPLEMENTED]{.badge .ok} (slot identity lacks role) |
| API → Application Insights | Asynchronous (SDK batching) | HTTPS | Connection string | [IMPLEMENTED]{.badge .ok} |
| API → Blob Storage | — | — | MI has Storage Blob Data Contributor | [NOT CONFIRMED]{.badge .nc} — no code uses it |
| API → e-mail / notification service | — | — | — | [PLANNED]{.badge .planned} |
| GitHub Actions → Azure | Synchronous | ARM / Kudu over HTTPS | OIDC federated credential | [IMPLEMENTED]{.badge .ok} |
| Agentic SDLC → GitHub Copilot | Synchronous CLI | HTTPS (Copilot CLI) | `COPILOT_GITHUB_TOKEN` | [IMPLEMENTED]{.badge .ok} |

Table: Table 15.1 — Integration inventory

# API Architecture {#api-architecture}

![Figure 17 — API surface and the policy applied to each endpoint](diagrams/rendered/14-api-architecture.png)

## Endpoint inventory

::: {.landscape}

| Endpoint | Method | Purpose | Handler | Request | Response | Auth / role | Validation | Status codes | Audit | Source |
|---|---|---|---|---|---|---|---|---|---|---|
| `/api/requests` | POST | Create request | `Create` | `CreateRequestDto {title, description, category}` | `RequestResponse` | Bearer; `CanCreateRequest` (Employee, Manager, ItAdmin, AppAdmin, SecurityReviewer) | Required, ≤200 / ≤4000, enum | 201, 400, 401, 403 | `RequestCreated` | `AccessRequestsController.cs` L59 |
| `/api/requests` | GET | List requests | `List` | — | `RequestResponse[]` (newest first) | Bearer; plain Employee sees own only | — | 200, 401 | — | L79 |
| `/api/requests/{id}` | GET | Get one | `GetById` | Route `id:guid` | `RequestResponse` | Bearer; ownership for plain Employee | Route constraint | 200, 401, 403, 404 | — | L94 |
| `/api/requests/{id}/decision` | POST | Stage decision | `Decide` | `DecisionDto {approved, notes ≤2000}` | `RequestResponse` | Bearer; `CanApprove` + stage role; not own request | ≤2000 | 200, 400, 401, 403, 404 | `Decision` | L109 |
| `/api/requests/{id}/confirm` | POST | Close after provisioning | `Confirm` | — | `RequestResponse` | Bearer; requester only | Status must be Provisioned/AwaitingConfirmation | 200, 400, 401, 403, 404 | `Closed` | L143 |
| `/api/requests/{id}/comments` | POST | Add comment | `AddComment` | `CommentDto {body ≤4000}` | — | Bearer; ownership for plain Employee | Required, ≤4000 | 204, 400, 401, 403, 404 | `CommentAdded` | L160 |
| `/api/audit?requestId=` | GET | Read audit trail | `AuditController.List` | Optional Guid | `AuditEntry[]` (≤500, newest first) | Bearer; `CanAudit` (Auditor, AppAdmin) | — | 200, 401, 403 | — | `AuditController.cs` L20 |
| `/health` | GET | Health incl. DB | Health checks | — | `Healthy` / `Unhealthy` | **Anonymous** | — | 200, 503 | — | `Program.cs` L95 |
| `/swagger` | GET | OpenAPI UI/JSON | Swashbuckle | — | — | Development environment only | — | 200 | — | `Program.cs` |

Table: Table 16.1 — API inventory (no OpenAPI specification file is committed; Swagger is generated at runtime in Development)

:::

## Sanitised examples

```http
POST /api/requests HTTP/1.1
Host: <API_HOST>
Authorization: Bearer <ACCESS_TOKEN>
x-correlation-id: 7f1c…
Content-Type: application/json

{ "title": "Read access to analytics DB", "description": "Needed for Q4 reporting", "category": "DatabaseAccess" }
```

```http
HTTP/1.1 201 Created
Location: /api/requests/<REQUEST_ID>

{ "id": "<REQUEST_ID>", "title": "Read access to analytics DB", "description": "Needed for Q4 reporting",
  "category": 4, "status": 1, "requesterId": "<ENTRA_OBJECT_ID>", "assignedToId": null,
  "requiresSecurityReview": true, "createdAt": "2026-11-03T10:00:00+00:00", "updatedAt": null }
```

## Error responses

- **Validation failures** (`[ApiController]`) return `400` with a `ValidationProblemDetails` body.
- **`Forbid()`** returns `403` with no body.
- **`BadRequest(string)`** returns `400` with a plain-text message.
- **Unhandled exceptions** return the framework default `500`. No custom ProblemDetails or exception handler is configured.

## Contract issue — enum serialisation {#enum-contract}

`Program.cs` registers no `JsonStringEnumConverter`, so System.Text.Json serialises `Category` and `Status` as **numbers** (shown in the response above) and rejects string values on input. The SPA (`api.ts`) types them as **strings** and posts `"category": "GitHubAccess"`. As a result:

1. Request creation from the UI fails model binding (400).
2. The list shows numbers instead of names.

Fix: register `JsonStringEnumConverter` and add an API contract test (§33). [PARTIAL]{.badge .partial}
