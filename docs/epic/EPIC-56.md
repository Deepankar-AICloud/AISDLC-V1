## Traceability Matrix

| Story | Feature | Epic | PRD-FR | BRD-REQ |
|---|---|---|---|---|
| US-001 | FEATURE-001 | EPIC-001 | PRD-FR-001 | BRD-REQ-001 |
| US-002 | FEATURE-002 | EPIC-001 | PRD-FR-002 | BRD-REQ-002 |
| US-003 | FEATURE-003 | EPIC-001 | PRD-FR-003 | BRD-REQ-003 |
| US-004 | FEATURE-004 | EPIC-001 | PRD-FR-004 | BRD-REQ-004 |

## Epic

### EPIC-001 — Access request lifecycle
**Goal:** Enable employees to submit and track access requests, IT administrators to review them, and managers to track authorized team requests.  
**Traces to:** PRD-FR-001, PRD-FR-002, PRD-FR-003, PRD-FR-004

## Feature

### FEATURE-001 — Request submission
**Traces to:** PRD-FR-001

### FEATURE-002 — Employee request tracking
**Traces to:** PRD-FR-002

### FEATURE-003 — IT request review
**Traces to:** PRD-FR-003

### FEATURE-004 — Manager team tracking
**Traces to:** PRD-FR-004

## User Stor

#### US-001 — As an employee, I want to submit an access request so that it can be recorded and tracked.
- **Traces to:** PRD-FR-001
- **Acceptance criteria:**
  - Given I am signed in with company sign-in and have provided the required information, When I submit a request and it is recorded, Then I receive confirmation and can find it in request tracking.
  - Given required information is missing or the request cannot be recorded, When I submit it, Then I see the issue and the system does not indicate successful submission.
  - Given a submission may be a duplicate, When I submit it, Then it is not silently presented as a successful duplicate; handling follows the access-request process.
- **Dependencies:** Access-request process and record availability (proposed)
- **Estimate:** M (proposed)

#### US-002 — As an employee, I want to view the current status of my authorized requests so that I can follow progress without contacting IT.
- **Traces to:** PRD-FR-002
- **Acceptance criteria:**
  - Given I am signed in and authorized to access a request, When I view it in request tracking, Then I see its current status.
  - Given status is unavailable, When I view the request, Then the system indicates that status is unavailable and does not present an invented or stale status as current.
  - Given a request is unavailable or I am not authorized to access it, When I try to view it, Then the system does not disclose its status or details and provides an appropriate message.
- **Dependencies:** Request status data and access controls (proposed)
- **Estimate:** M (proposed)

#### US-003 — As an IT administrator, I want to access and initially review authorized requests so that the request process records the review and resulting status.
- **Traces to:** PRD-FR-003
- **Acceptance criteria:**
  - Given I am signed in with company sign-in and authorized to review a request, When I perform an initial review, Then the request process records the review and resulting status.
  - Given a request has not received an initial review, When it is displayed, Then it is distinguishable from a reviewed request.
  - Given I am unauthorized or a review update fails, When I access or attempt to review a request, Then the system does not disclose unauthorized details or present the review as completed.
  - Given the organization’s business-day calendar and applicable time zone, When initial-review performance is measured, Then at least 90% of requests receive an initial review within one business day.
- **Dependencies:** Request review process and recording capability (proposed)
- **Estimate:** L (proposed)

#### US-004 — As a manager, I want to track authorized requests for my team so that I can view their available progress.
- **Traces to:** PRD-FR-004
- **Acceptance criteria:**
  - Given I am signed in and authorized to access team requests, When I open team request tracking, Then I can view the authorized team requests and their available progress.
  - Given I am not authorized to access a request, When I try to view it, Then the system does not disclose its details or status.
  - Given team membership or authorization changes, When access is evaluated, Then it reflects those changes according to applicable policies.
- **Dependencies:** Team association and authorization information (proposed)
- **Estimate:** M (proposed)

## Acceptance criteria

All stories require company sign-in and applicable access controls. Request submission, retrieval, review, and tracking must not expose unauthorized information; failures must not be presented as successful operations. Data retention must follow applicable policies, and changing HR records is out of scope. The PRD does not prescribe status values, transitions, or review outcomes; those remain defined by the access-request process.