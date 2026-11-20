I'll start by examining the current repository state to understand what the previous draft actually produced.

Confirmed: docs/decisions/access-request-contract.md is missing from the diff (matches QC finding). Let me review all the key files to understand current implementation before fixing.

Confirmed: no pagination UI at all. Let me check api.ts's teamRequests method and the related tests.

Now let's check ManagerTeamPage.test.tsx, api.ts PagedResult interface, and the Program.cs auth/DI section fully, plus the contract doc references elsewhere, then begin implementing.

Now I have a full picture. Let me implement fixes, starting with the directory service extension for current team scope.

Now the GraphDirectoryService (production):

Now the test fake:

Good, System.Linq is implicit. Now create the swappable `ITeamScopeProvider`:

Now update `TeamRequestsController` to use the swappable scope provider instead of the stale `ManagerId`:

Now update Program.cs to register the scope provider:

Now let's build the backend to confirm these changes compile before moving to review metrics/retention/frontend.

Builds clean. Now update the TeamRequestsTests to cover reassignment and pagination (per QC finding), then move to review metrics.

All 6 team-request tests pass, including reassignment, directory-outage denial, and pagination. Now let's fix the review metrics cohort/denominator logic.

Now update the controller doc comment (already generic, fine) and update existing tests that rely on old semantics:

Now let's build and run the ReviewMetrics tests:

All pass. Now let's fix the retention service per the QC findings.

Now let's implement the domain entity change:

Now rewrite RetentionService.cs fully:

Now update the DbContext config for the new `FirstReviewAt` column (it's a plain nullable property, no conversion needed, but let's check):

Good, builds. Now generate a new EF Core migration for the `FirstReviewAt` column addition.

Now update RetentionServiceTests to reflect the new opt-in configuration model, and build/test.

Now update `ReviewMetricsService` to merge preserved disposal-record timing facts so reporting survives disposal:

All 8 retention tests pass. Now let's address pagination in the `ManagerTeamPage.tsx` frontend component.

No existing pattern to follow; I'll implement straightforward Prev/Next pagination.

Now add tests for pagination behavior to the test file:

Now let's run frontend tests and build.

Tests pass but with an act() warning. Let me fix that using `fireEvent`:

Clean. Now let's address the ReviewMetricsController API and "label provisional results" requirement — also check for the EligibleForReporting requirement being reflected in docs and controller comment:

All 52 backend tests pass. Now let's create the missing decision contract document (TASK-001).

Let's verify Program.cs retention comment is accurate and do a final full solution build/test pass plus full frontend build, then review the complete diff.

This comment is fine and still accurate. Now full solution build + test + frontend validation:

Everything builds and passes: 52 backend tests, 9 frontend tests, both builds clean. Let's do a final review of the full diff for sanity.

All QC findings addressed. Summary of fixes:

## Implementation Summary

| TASK ID | Title | Status | Files |
|---|---|---|---|
| TASK-001 | Confirm implementation contracts | implemented | `docs/decisions/access-request-contract.md` |
| TASK-002 | Add request persistence and history | implemented (pre-existing) | `src/backend/SmartServe.Api/Domain/PortalRequest.cs`, `src/backend/SmartServe.Api/Data/SmartServeDbContext.cs` |
| TASK-003 | Test request persistence | implemented (pre-existing) | `src/backend/SmartServe.Tests/RelationalAtomicityTests.cs`, `WorkflowAuditTests.cs` |
| TASK-004 | Enforce sign-in and authorization | implemented (pre-existing) | `src/backend/SmartServe.Api/Program.cs` |
| TASK-005 | Test authorization policies | implemented (pre-existing) | `src/backend/SmartServe.Tests/EndpointAuthorizationTests.cs`, `RoleScopeTests.cs` |
| TASK-006 | Implement employee submission and status views | implemented (pre-existing) | `src/backend/SmartServe.Api/Controllers/RequestsController.cs` |
| TASK-007 | Test employee request flows | implemented (pre-existing) | `src/backend/SmartServe.Tests/EndpointAuthorizationTests.cs` |
| TASK-008 | Implement IT review and status updates | implemented (pre-existing) | `src/backend/SmartServe.Api/Services/WorkflowService.cs` |
| TASK-009 | Test IT review and update flows | implemented (pre-existing) | `src/backend/SmartServe.Tests/WorkflowAuditTests.cs` |
| TASK-010 | Implement manager team request view | implemented (revised) | `src/backend/SmartServe.Api/Controllers/TeamRequestsController.cs`, `Services/Teams/ITeamScopeProvider.cs`, `Services/Directory/*`, `src/frontend/src/features/manager-team/ManagerTeamPage.tsx` |
| TASK-011 | Test manager team scope | implemented (revised) | `src/backend/SmartServe.Tests/TeamRequestsTests.cs`, `TestSupport/FakeDirectoryService.cs`, `ManagerTeamPage.test.tsx` |
| TASK-012 | Implement review timestamp capture and reporting | implemented (revised) | `src/backend/SmartServe.Api/Services/ReviewMetricsService.cs`, `Controllers/ReviewMetricsController.cs` |
| TASK-013 | Test review metrics | implemented (revised) | `src/backend/SmartServe.Tests/ReviewMetricsServiceTests.cs` |
| TASK-014 | Implement audit retention and disposal | implemented (revised, still disabled by default) | `src/backend/SmartServe.Api/Services/RetentionService.cs`, `Domain/PortalRequest.cs`, `appsettings.json`, `Migrations/20261120155000_*` |
| TASK-015 | Test retention and audit behavior | implemented (revised) | `src/backend/SmartServe.Tests/RetentionServiceTests.cs` |
| TASK-016 | Verify end-to-end access control | implemented | `EndpointAuthorizationTests.cs`, `TeamRequestsTests.cs` |

## Files
Created: `docs/decisions/access-request-contract.md`, `src/backend/SmartServe.Api/Services/Teams/ITeamScopeProvider.cs`, `Migrations/20261120155000_AddFirstReviewAtToRetentionDisposalRecord.{cs,Designer.cs}`.
Modified: `TeamRequestsController.cs` (resolves scope via `ITeamScopeProvider`, fails closed with 403), `Services/Directory/{IDirectoryService,InMemoryDirectoryService,GraphDirectoryService}.cs` (+`GetDirectReportIdsAsync`), `Domain/PortalRequest.cs` (ManagerId re-documented as notification-only; `RetentionDisposalRecord.FirstReviewAt` added), `ReviewMetricsService.cs` (new cohort: overdue-unreviewed count as misses, `Provisional` flag, merges disposed records), `RetentionService.cs` (`Enabled` + `EligibleTerminalStatuses` + `DisposalRecordRetentionDays` gates; no more notification deletion), `Program.cs`, `appsettings.json`, `ManagerTeamPage.tsx` (pagination UI), plus corresponding test files.

**Builds/tests run:** `dotnet build SmartServe.sln` (0 errors), `dotnet test SmartServe.sln` (52 passed), `npx vitest run --passWithNoTests` (9 passed), `npm run build` (succeeded).

**Notes:** All six QC findings fixed — team scope now resolves current manager via a swappable `ITeamScopeProvider` (fail-closed on outage, immune to reassignment), UI paginates past 50; review metric now counts overdue-unreviewed requests as misses and labels `provisional: true` in the API; retention requires three explicit approvals (`Enabled`, status list, window) before acting, never touches notifications, and preserves `FirstReviewAt` so disposal never alters historical NFR-003 reporting; the decision-contract doc is now present.