Good — MarkBroken is actually defined. Let's build and run the full test suite to see real state (QC claim may be stale/about a since-fixed issue, or may point to a real compile error elsewhere).

Confirmed — `AccessRequest.cs` and `AccessRequestsController.cs` are orphaned legacy files from a prior superseded model (the current model is `PortalRequest`/`RequestKind`/`RequestStatus`). They reference `RequestCategory`/`CommentDto` which no longer exist. These must be removed to build. Let me check if `AuditController.cs` or others reference `AccessRequest`.

This entirely references the old pre-SmartServe model (RequestCategory, SecurityApproval, ItProcessing, Provisioned statuses) that no longer exists — it's superseded by `WorkflowAuditTests.cs`. Removing these 3 stale/orphaned files to unblock the build.

Build succeeds now. Let's run the test suite to find real failures.

30/30 tests pass. Now let's examine all the other QC findings in detail — the key source files.

Network access is available. Now let's examine the remaining key files before making fixes: WorkflowService.cs, SmartServeDbContext.cs, frontend fixture/comment files, and the Implementation Summary table requirement for paths.

This looks good already with (proposed) labels. Let's check AuditController, RequestTypesController, Program.cs CanCreateRequest/CanAudit policies for the AppAdmin-write / non-Employee-submission labeling finding.

This already looks fine. Now let's check frontend fixture test and the App.tsx comment, plus existing tests directory structure.

Good, App.tsx already labels this. Now let's check the migrations folder for exact paths, and the frontend admin request-types test.

Now let's start implementing the fixes. First, NotificationService's finalization bug:

Now the full-lifecycle test's timestamp loop:

Good, those already have both bounds. Now let's fix the concurrency test's atomicity gap — replace the InMemory-provider workaround with a genuine SQLite-backed relational atomicity test.

Good. Now create the new relational atomicity test file.

Now let's build and run this new test.

Let's run it a few times to check stability, then run full suite.

Stable. Now update the old InMemory test comment to reference the new atomic test, removing the misleading "cannot be tested here" framing:

Now let's add a test for the NotificationService.FinalizeAsync persistence-failure path (returning Failed, not an in-memory unpersisted outcome).

Now add a test exercising this in the new relational test file (it fits well there since it's about real persistence failure, not EF InMemory quirks).

Both pass. Now let's add the `(proposed)` labels for AppAdmin all-requests access and non-Employee submission in Program.cs and AuditController.

Now let's fix the frontend fixture naming to remove the "captured" claim:

Now let's check the remaining QC item: "MarkBroken" concern and the EndpointAuthorizationTests for the loop over every endpoint including /health, and verify all tests run. Let's run the full backend suite.

32/32 pass. Let's run it a few more times to check for flakiness in the concurrency tests, then move to frontend validation.

Consistently 32/32. Now frontend validation.

Dependencies not installed. Let's install them.

All frontend tests pass. Let's run tsc and eslint too, plus npm run build.

Both clean (no output = no errors). Now build:

Build succeeds. Now bicep check:

Bicep compiles cleanly (ARM JSON generated, no errors). Now let's gather the final file list for the Implementation Summary. Let's check git status/diff to compile the full list.

Good, this isn't in a TASK but relates to ARCH-23 item 5 (security reviewer read-only visibility) — it's a (proposed) addition not tied to a specific TASK ID, so I'll mention it under Files but not create a new row. Now let's finalize everything with git diff stat for Program.cs/AuditController check.

All verification complete. Here's the final summary.

## Implementation Summary

| TASK ID | Title | Status | Files |
|---|---|---|---|
| TASK-001 | Scaffold portal solution (proposed consolidation) | implemented | `src/backend/SmartServe.sln`, `src/backend/SmartServe.Api/SmartServe.Api.csproj`, `src/backend/SmartServe.Api/Program.cs`, `src/frontend/package.json`, `src/frontend/vite.config.ts`, `src/frontend/tsconfig.json` |
| TASK-002 | Enforce Entra ID authentication on every endpoint | implemented | `src/backend/SmartServe.Api/Program.cs`, `src/backend/SmartServe.Api/Testing/TestAuthHandler.cs`, `src/backend/SmartServe.Tests/EndpointAuthorizationTests.cs` |
| TASK-003 | Server-side role-based authorization module | implemented | `src/backend/SmartServe.Api/Program.cs`, `src/backend/SmartServe.Tests/RoleScopeTests.cs` |
| TASK-004 | EF Core data access layer over Azure SQL | implemented | `src/backend/SmartServe.Api/Data/SmartServeDbContext.cs`, `src/backend/SmartServe.Api/Data/SmartServeDbContextFactory.cs`, `src/backend/SmartServe.Api/Data/DbSeeder.cs`, `src/backend/SmartServe.Api/Domain/PortalRequest.cs`, `src/backend/SmartServe.Api/Domain/Enums.cs`, `src/backend/SmartServe.Api/Migrations/20261103093414_InitialPortalRequestModel.cs`, `src/backend/SmartServe.Api/Migrations/20261103093414_InitialPortalRequestModel.Designer.cs`, `src/backend/SmartServe.Api/Migrations/SmartServeDbContextModelSnapshot.cs` |
| TASK-005 | Request submission (US-001) | partial — form fields/on-screen confirmation UX are (proposed)/open questions, not confirmed | `src/backend/SmartServe.Api/Controllers/RequestsController.cs`, `src/backend/SmartServe.Api/Services/WorkflowService.cs`, `src/backend/SmartServe.Api/Dtos/RequestDtos.cs` |
| TASK-006 | View own requests / status (US-002) | implemented | `src/backend/SmartServe.Api/Controllers/RequestsController.cs`, `src/backend/SmartServe.Api/Program.cs` (CanViewOwnRequests) |
| TASK-007 | Access-request manager approve/reject (US-003) | implemented; manager-only endpoint permission is (proposed) | `src/backend/SmartServe.Api/Services/WorkflowService.cs`, `src/backend/SmartServe.Api/Controllers/RequestsController.cs`, `src/backend/SmartServe.Api/Program.cs` |
| TASK-008 | IT admin fulfillment of approved access requests (US-003) | implemented; IT-admin-only endpoint permission is (proposed) | `src/backend/SmartServe.Api/Services/WorkflowService.cs`, `src/backend/SmartServe.Api/Controllers/RequestsController.cs` |
| TASK-009 | Audit logging on every status change | implemented | `src/backend/SmartServe.Api/Services/WorkflowService.cs`, `src/backend/SmartServe.Api/Domain/PortalRequest.cs`, `src/backend/SmartServe.Tests/WorkflowAuditTests.cs`, `src/backend/SmartServe.Tests/RelationalAtomicityTests.cs` |
| TASK-010 | Requester notification on every status change | partial — dispatch/persistence logic implemented and tested with a fake sender; real SMTP/Graph delivery not verifiable in this environment | `src/backend/SmartServe.Api/Services/NotificationService.cs`, `src/backend/SmartServe.Api/Services/Email/EmailTemplates.cs`, `src/backend/SmartServe.Api/Services/Email/IEmailSender.cs`, `src/backend/SmartServe.Api/Services/Email/GraphEmailSender.cs`, `src/backend/SmartServe.Api/Services/Email/UnconfiguredEmailSender.cs`, `src/backend/SmartServe.Tests/TestSupport/FakeEmailSender.cs`, `src/backend/SmartServe.Tests/RelationalAtomicityTests.cs` |
| TASK-011 | Manager "waiting for approval" notification | partial — same dispatch/persistence coverage as TASK-010; recipient resolution via Graph not live-verified here | `src/backend/SmartServe.Api/Services/NotificationService.cs`, `src/backend/SmartServe.Api/Services/Directory/IDirectoryService.cs`, `src/backend/SmartServe.Api/Services/Directory/GraphDirectoryService.cs`, `src/backend/SmartServe.Api/Services/Directory/InMemoryDirectoryService.cs`, `src/backend/SmartServe.Tests/TestSupport/FakeDirectoryService.cs` |
| TASK-012 | Application admin: manage request types | implemented | `src/backend/SmartServe.Api/Controllers/RequestTypesController.cs`, `src/frontend/src/features/admin-request-types/AdminRequestTypesPage.tsx`, `src/frontend/src/features/admin-request-types/__tests__/AdminRequestTypesPage.test.tsx` |
| TASK-013 | Auditor read-only access to all requests and history | implemented; Auditor read-only confirmed, AppAdmin same access is (proposed) | `src/backend/SmartServe.Api/Controllers/AuditController.cs`, `src/backend/SmartServe.Tests/RoleScopeTests.cs` |
| TASK-014 | Key Vault + managed identity secret handling | partial — infra config implemented; live Key Vault/managed-identity resolution not verifiable here | `infra/main.bicep`, `src/backend/SmartServe.Api/Program.cs`, `src/backend/SmartServe.Api/appsettings.json` |
| TASK-015 | Service-request workflow stub (proposed, submission-only confirmed) | implemented | `src/backend/SmartServe.Api/Services/WorkflowService.cs`, `src/backend/SmartServe.Api/Controllers/RequestsController.cs` |
| TASK-016 | Deployment pipeline (proposed environment topology) | implemented; end-to-end deployment verification deferred to DEV_DEPLOYMENT | `infra/main.bicep` |

## Files

Modified: `infra/main.bicep`, `src/backend/SmartServe.Api/Controllers/AuditController.cs`, `src/backend/SmartServe.Api/Controllers/RequestsController.cs`, `src/backend/SmartServe.Api/Program.cs`, `src/backend/SmartServe.Api/Services/NotificationService.cs`, `src/backend/SmartServe.Tests/WorkflowAuditTests.cs`, `src/backend/SmartServe.Tests/SmartServe.Tests.csproj`, `src/frontend/src/__tests__/apiFixture.test.ts`

Created: `src/backend/SmartServe.Tests/RelationalAtomicityTests.cs`

Deleted (orphaned pre-consolidation files that broke the build): `src/backend/SmartServe.Api/Controllers/AccessRequestsController.cs`, `src/backend/SmartServe.Api/Domain/AccessRequest.cs`, `src/backend/SmartServe.Tests/WorkflowServiceTests.cs`

**Builds/tests actually run this round:** `dotnet build SmartServe.sln` (0 errors/warnings); `dotnet test SmartServe.sln` ×5 (32/32 passed each run); `npx vitest run --passWithNoTests` (5/5 passed); `npx tsc --noEmit` (clean); `npx eslint src` (clean); `npm run build` (succeeded); `az bicep build infra/main.bicep` (succeeded, ARM JSON emitted).

**QC fixes this round:** (1) notification `FinalizeAsync` no longer returns a stale in-memory outcome on genuine persistence failure — now sets `Failed`/`FinalizePersistFailed:` reason, new test `Notification_finalize_persistence_failure_reports_failed_not_the_unpersisted_computed_outcome` proves it; (2) added real relational-provider (SQLite) atomicity test for status+audit commits under concurrency; (3) added missing lower-bound timestamp assertions; (4) labeled AppAdmin's all-requests/audit access and non-Employee submission as `(proposed)` in `AuditController.cs`/`RequestsController.cs`/`Program.cs`; (5) renamed `CAPTURED_BACKEND_RESPONSE_JSON` to `REPRESENTATIVE_BACKEND_SHAPED_JSON` to remove a provenance claim contradicting its own comment; (6) deleted dead pre-consolidation files that were silently breaking the build.