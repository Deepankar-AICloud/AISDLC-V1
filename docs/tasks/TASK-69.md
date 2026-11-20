# Development Task Plan

## Traceability

| Upstream requirement | Covered by |
|---|---|
| ARCH-COMP-001 — Request Service | Request persistence; employee submission and status view; request tests |
| ARCH-COMP-002 — Status Update Service | IT review and status updates; transactional-update tests |
| ARCH-COMP-003 — Authorization Service | Company sign-in and authorization on every data-access path; access-control tests |
| ARCH-COMP-004 — Team Scope Service | Manager team view and fail-closed scope resolution; manager-scope tests |
| ARCH-COMP-005 — Request Data Store | Request schema and repository; persistence tests |
| ARCH-COMP-006 — Audit/Retention Log | Status-change history and retention enforcement; audit and retention tests |
| ARCH-COMP-007 — Review Metrics / Reporting Service | Raw timestamp capture and review-target reporting; metrics tests |
| NFR-001 through NFR-004 | Access control, failed-update integrity, review-target measurement, and retention tasks below |

No `US-NNN` identifiers were included in the supplied upstream artifacts; functional traceability therefore uses the available `ARCH-COMP-NNN` identifiers without inventing story IDs. File paths below are proposed because no repository structure or technology stack was specified.

## Tasks

### TASK-001 — Confirm implementation contracts
- **Traces to:** ARCH-COMP-001, ARCH-COMP-002, ARCH-COMP-004, ARCH-COMP-006, ARCH-COMP-007
- **Scope:** Record the approved API and request fields, permitted status values, IT review scope, authoritative manager/team source and update timing, retention schedule, and definitions of “initial review” and “one business day.” Mark unresolved decisions explicitly; do not encode assumptions as policy.
- **Files:** `docs/decisions/access-request-contract.md`
- **Depends on:** none
- **Definition of done:** Approved decisions and remaining open items are documented and available to implementation tasks.

### TASK-002 — Add request persistence and history
- **Traces to:** ARCH-COMP-001, ARCH-COMP-002, ARCH-COMP-005, ARCH-COMP-006
- **Scope:** Implement persistence for requests, current status, submission/status-change timestamps, and status history using the confirmed request contract.
- **Files:** `src/requests/model.*`, `src/requests/repository.*`, `src/data/migrations/*`
- **Depends on:** TASK-001
- **Definition of done:** Requests and status history can be stored and retrieved; schema and migrations match the approved contract.
- **Tests:** TASK-003

### TASK-003 — Test request persistence
- **Traces to:** ARCH-COMP-005, ARCH-COMP-006
- **Scope:** Add unit tests for persistence, timestamp storage, and status-history retrieval.
- **Files:** `tests/unit/requests/repository.*`
- **Depends on:** TASK-002
- **Definition of done:** Tests cover successful persistence and retrieval, including multiple status-history entries.

### TASK-004 — Enforce sign-in and authorization
- **Traces to:** ARCH-COMP-003; NFR-001
- **Scope:** Integrate company sign-in and enforce role/resource-scope authorization before every request-data read or write, including submission, employee reads, IT review reads and updates, and manager reads. Deny by default.
- **Files:** `src/auth/*`, `src/authorization/*`
- **Depends on:** TASK-001
- **Definition of done:** Every request-data access path requires an authenticated identity and the applicable role and scope check.
- **Tests:** TASK-005, TASK-016

### TASK-005 — Test authorization policies
- **Traces to:** ARCH-COMP-003; NFR-001
- **Scope:** Add focused tests for unauthenticated access, permitted roles/scopes, and denied or unresolved scopes.
- **Files:** `tests/unit/authorization/*`
- **Depends on:** TASK-004
- **Definition of done:** Tests confirm denial by default and verify that authorization decisions do not disclose protected request data.

### TASK-006 — Implement employee submission and status views
- **Traces to:** ARCH-COMP-001, ARCH-COMP-003, ARCH-COMP-005
- **Scope:** Implement request submission and employee-only list/detail status views. Validate submissions before persistence; return explicit errors rather than success-shaped responses on failure.
- **Files:** `src/requests/service.*`, `src/api/requests.*`, `src/ui/requests/*`
- **Depends on:** TASK-002, TASK-004
- **Definition of done:** An employee can submit a valid request and view only their own persisted request status and progress.
- **Tests:** TASK-007

### TASK-007 — Test employee request flows
- **Traces to:** ARCH-COMP-001, ARCH-COMP-003, ARCH-COMP-005
- **Scope:** Add unit and functional tests for valid submission, invalid submission, own-status reads, and attempts to read another employee’s request.
- **Files:** `tests/unit/requests/*`, `tests/functional/employee-requests.*`
- **Depends on:** TASK-006
- **Definition of done:** Tests verify persistence on success, explicit errors on validation failure, and denial without data disclosure for out-of-scope reads.

### TASK-008 — Implement IT review and status updates
- **Traces to:** ARCH-COMP-002, ARCH-COMP-003, ARCH-COMP-005, ARCH-COMP-006
- **Scope:** Implement IT review reads and authorized status updates. Make each update transactional so failures preserve the prior status; record successful changes in status history.
- **Files:** `src/reviews/service.*`, `src/api/reviews.*`, `src/ui/reviews/*`
- **Depends on:** TASK-002, TASK-004
- **Definition of done:** Authorized IT administrators can review and update requests; failed updates leave the stored status unchanged.
- **Tests:** TASK-009

### TASK-009 — Test IT review and update flows
- **Traces to:** ARCH-COMP-002, ARCH-COMP-003, ARCH-COMP-005, ARCH-COMP-006; NFR-002
- **Scope:** Test review authorization, successful status changes, history recording, and update failures.
- **Files:** `tests/unit/reviews/*`, `tests/functional/reviews.*`
- **Depends on:** TASK-008
- **Definition of done:** Tests confirm unauthorized access is denied and every failed update retains the prior status.

### TASK-010 — Implement manager team request view
- **Traces to:** ARCH-COMP-003, ARCH-COMP-004, ARCH-COMP-005
- **Scope:** Implement an adapter behind a swappable team-scope interface and a manager view filtered to the caller’s authorized team. Fail closed if scope cannot be resolved.
- **Files:** `src/teams/scope-provider.*`, `src/teams/service.*`, `src/api/team-requests.*`, `src/ui/team-requests/*`
- **Depends on:** TASK-001, TASK-002, TASK-004
- **Definition of done:** Managers see only authorized team requests; unresolved scope results in denial, not guessed access.
- **Tests:** TASK-011

### TASK-011 — Test manager team scope
- **Traces to:** ARCH-COMP-003, ARCH-COMP-004
- **Scope:** Test team filtering, unauthorized manager access, and unavailable or unresolved team-scope data.
- **Files:** `tests/unit/teams/*`, `tests/functional/team-requests.*`
- **Depends on:** TASK-010
- **Definition of done:** Tests verify correct team filtering and fail-closed behavior without disclosing out-of-scope data.

### TASK-012 — Implement review timestamp capture and reporting
- **Traces to:** ARCH-COMP-001, ARCH-COMP-002, ARCH-COMP-007; NFR-003
- **Scope:** Capture submission and review-event timestamps and provide reporting against the 90%-within-one-business-day target using the definitions approved in TASK-001. Preserve raw timestamps for recalculation.
- **Files:** `src/metrics/review-metrics.*`, `src/requests/service.*`, `src/reviews/service.*`, `src/api/metrics.*`
- **Depends on:** TASK-001, TASK-002, TASK-006, TASK-008
- **Definition of done:** Raw timestamps are recorded and the report applies the approved review-event and business-calendar definitions; the report measures the target rather than implying the software guarantees it.
- **Tests:** TASK-013

### TASK-013 — Test review metrics
- **Traces to:** ARCH-COMP-007; NFR-003
- **Scope:** Test timestamp capture and reporting for the approved review definition and business calendar, including boundary cases.
- **Files:** `tests/unit/metrics/*`, `tests/functional/review-metrics.*`
- **Depends on:** TASK-012
- **Definition of done:** Tests verify reported results against known submission and review timestamps.

### TASK-014 — Implement audit retention and disposal
- **Traces to:** ARCH-COMP-006; NFR-004
- **Scope:** Apply the approved retention policy to request and status-history records, including required disposal behavior and auditability.
- **Files:** `src/retention/*`, `src/audit/*`, `src/data/migrations/*`
- **Depends on:** TASK-001, TASK-002
- **Definition of done:** Configured retention and disposal behavior matches the approved company policy; no retention schedule is invented where approval is pending.
- **Tests:** TASK-015

### TASK-015 — Test retention and audit behavior
- **Traces to:** ARCH-COMP-006; NFR-004
- **Scope:** Test retention eligibility, policy-compliant disposal, and status-history handling.
- **Files:** `tests/unit/retention/*`, `tests/functional/retention.*`
- **Depends on:** TASK-014
- **Definition of done:** Tests demonstrate that records are handled according to the approved retention schedule.

### TASK-016 — Verify end-to-end access control
- **Traces to:** ARCH-COMP-001, ARCH-COMP-002, ARCH-COMP-003, ARCH-COMP-004, ARCH-COMP-005; NFR-001
- **Scope:** Add functional coverage across submission, employee status reads, IT review reads and updates, and manager team reads, including unauthenticated and out-of-scope attempts.
- **Files:** `tests/functional/access-control.*`
- **Depends on:** TASK-006, TASK-008, TASK-010
- **Definition of done:** Every request-data path is exercised; denied requests disclose no protected data and failed status updates preserve prior status.

## Definition of done

The plan is complete when each listed architecture component has an implementation task and corresponding test coverage; all four access paths enforce company sign-in and authorization; failed status updates retain prior state; request and review timestamps support the approved 90% target calculation; and retention behavior matches the approved company policy. Unresolved upstream decisions remain documented and are not replaced with invented policy or business definitions.