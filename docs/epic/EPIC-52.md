# Epics, Features & User Stories

## Traceability Matrix

| Story | Feature | Epic | PRD-FR | BRD-REQ |
|---|---|---|---|---|
| US-001 | FEATURE-001 | EPIC-001 | PRD-FR-001 | BRD-REQ-001 |
| US-002 | FEATURE-002 | EPIC-001 | PRD-FR-002 | BRD-REQ-002 |
| US-003 | FEATURE-003 | EPIC-001 | PRD-FR-003 | BRD-REQ-003 |
| US-004 | FEATURE-004 | EPIC-001 | PRD-FR-004 | BRD-REQ-004 |

## Epic

### EPIC-001 — Access request submission, review, and tracking
**Goal:** Enable employees to submit and track access requests, IT administrators to review them, and authorized managers to see team request status.
**Traces to:** PRD-FR-001, PRD-FR-002, PRD-FR-003, PRD-FR-004

## Feature

### FEATURE-001 — Submit access requests
**Traces to:** PRD-FR-001

### FEATURE-002 — Track personal request status
**Traces to:** PRD-FR-002

### FEATURE-003 — Review submitted requests
**Traces to:** PRD-FR-003

### FEATURE-004 — Track authorized team requests
**Traces to:** PRD-FR-004

## User Stor

#### US-001 — As an employee, I want to submit an access request so that it can be tracked and reviewed
- **Traces to:** PRD-FR-001
- **Acceptance criteria:**
  - Given I am authenticated using company sign-in, When I submit an access request, Then the system records it and makes it available for tracking and review.
  - Given I am unauthenticated or company sign-in is unavailable, When I attempt to submit a request, Then the request is not submitted.
  - Given a request is recorded, When it is retained, Then it follows company data-retention policies and does not change HR records.
- **Dependencies:** None specified (proposed)
- **Estimate:** M (proposed)

#### US-002 — As an employee, I want to view my request status and progress so that I can check updates without contacting IT
- **Traces to:** PRD-FR-002
- **Acceptance criteria:**
  - Given I am authenticated using company sign-in, When I view my requests, Then I can see the status and progress available for each request I am authorized to view.
  - Given I request information for a request I am not authorized to view, When the system responds, Then it does not disclose that request or its status.
- **Dependencies:** US-001 (proposed)
- **Estimate:** M (proposed)

#### US-003 — As an authorized IT administrator, I want to access submitted requests for review so that they can be handled through the organization’s existing process
- **Traces to:** PRD-FR-003
- **Acceptance criteria:**
  - Given I am authenticated and company access-control policies authorize review access, When I access submitted requests, Then I can access them for review under the organization’s existing process.
  - Given I do not have review authorization, When I attempt to access submitted requests, Then the system does not disclose them.
  - Given requests are submitted, When one business day has elapsed after submission, Then at least 90% of requests have received an initial review.
- **Dependencies:** US-001 (proposed)
- **Estimate:** M (proposed)

#### US-004 — As a manager, I want to view authorized team-request status so that I can track requests when policy permits
- **Traces to:** PRD-FR-004
- **Acceptance criteria:**
  - Given I am authenticated and company access-control policies authorize access to the relevant team requests, When I view team requests, Then I can see their status.
  - Given policy does not authorize access to a team request, When I attempt to view it, Then the system does not disclose the request or its status.
- **Dependencies:** US-001 (proposed)
- **Estimate:** M (proposed)

## Acceptance criteria

All four PRD functional requirements appear in the traceability matrix and are covered by at least one story; each story traces to its PRD-FR and corresponding BRD-REQ. PRD details left unspecified—including request fields and duplicate-submission behavior, status labels and progress details, behavior when no requests exist, and the definition of a team and manager authorization rules—remain open.