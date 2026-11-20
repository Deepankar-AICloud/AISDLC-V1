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
**Goal:** Enable employees to submit and track access requests, IT administrators to review them, and managers to track requests within their authorized team scope.  
**Traces to:** PRD-FR-001, PRD-FR-002, PRD-FR-003, PRD-FR-004

## Feature
### FEATURE-001 — Employee request status
**Traces to:** PRD-FR-001

### FEATURE-002 — Access request submission
**Traces to:** PRD-FR-002

### FEATURE-003 — IT review and status updates
**Traces to:** PRD-FR-003

### FEATURE-004 — Manager team request tracking
**Traces to:** PRD-FR-004

## User Stor
#### US-001 — As an employee, I want to view my submitted requests and their status so that I can check progress without contacting IT
- **Traces to:** PRD-FR-001; BRD-REQ-001
- **Dependencies:** Company sign-in and request-scope authorization (proposed).
- **Estimate:** M (proposed)

##### Acceptance criteria
- Given an employee is signed in and has submitted requests, when they open their requests and select one, then they can see its current status and available progress information.
- Given the employee has no requests, when they open their requests, then an empty state is shown.
- Given a request has no status update, when the employee views it, then it remains identifiable as submitted; the exact display value remains open.
- Given a request cannot be retrieved, when the employee tries to view it, then an error is shown without exposing unauthorized request data.
- Given a request belongs to another employee, when the employee attempts to view it through this function, then access is denied and the request data is not disclosed.

#### US-002 — As an employee, I want to submit an access request and receive confirmation so that I can track the recorded request
- **Traces to:** PRD-FR-002; BRD-REQ-002
- **Dependencies:** Company sign-in and request-data retention policies (proposed).
- **Estimate:** M (proposed)

##### Acceptance criteria
- Given an employee is signed in and provides the required request information, when they submit the request successfully, then it is recorded and confirmation is shown.
- Given required information is missing, when the employee submits the request, then the missing information is explained and success is not indicated.
- Given submission fails, when the employee submits the request, then the failure is reported and success is not indicated.
- Given a request is successfully recorded, when the submitter opens their requests, then they can find and track that request.
- Given an employee submits repeatedly, when the submissions are processed, then they are not presented as one successful submission unless the system confirms they refer to the same recorded request.
- **Open questions:** The request information collected and its validation rules remain to be defined.

#### US-003 — As an IT administrator, I want to review requests and record status updates so that authorized users can see request progress
- **Traces to:** PRD-FR-003; BRD-REQ-003
- **Dependencies:** Company sign-in, IT administrator authorization, and permitted status values (proposed).
- **Estimate:** L (proposed)

##### Acceptance criteria
- Given an IT administrator is authorized and a request is available for review, when they review it and save a permitted status update, then authorized users can see the current status.
- Given a user is not authorized as an IT administrator, when they attempt to update a request, then the update is rejected.
- Given an authorized status update cannot be saved, when the administrator submits it, then the failure is reported and the previously recorded status is retained.
- Given requests are submitted during the measurement period, when the initial-review target is measured using the organization’s business calendar, then at least 90% receive an initial review within one business day of submission.
- **Open questions:** Permitted status values, concurrent-update handling, what constitutes an “initial review,” and the reporting method for the 90% target remain to be defined.

#### US-004 — As a manager, I want to view requests and statuses within my authorized team scope so that I can track my team’s requests
- **Traces to:** PRD-FR-004; BRD-REQ-004
- **Dependencies:** Company sign-in and an authoritative source for the manager’s authorized team scope (proposed).
- **Estimate:** M (proposed)

##### Acceptance criteria
- Given a manager is signed in and their authorized team scope can be determined, when they open team requests, then they can view requests and statuses only within that scope.
- Given the manager’s team scope cannot be determined, when they try to access team requests, then no team request data is shown and access unavailability is reported.
- Given a request is outside the manager’s authorized team scope, when they attempt to view it, then access is denied and its data is not disclosed.
- Given team membership changes, when the manager views team requests, then access reflects the currently authorized scope and does not include requests outside it.
- **Open question:** The authoritative source and update timing for employee-manager team relationships remain to be defined.