# Product Requirements Document (PRD / FSD)

## Overview
This PRD derives from approved BRD-56.md and specifies access-request submission, status tracking, IT review, and manager tracking. It preserves the stated constraints: company sign-in, applicable access-control and data-retention policies, and no changes to HR records.

## Traceability Summary
| BRD ID | Functional requirement |
|---|---|
| BRD-REQ-001 | Submit access requests |
| BRD-REQ-002 | View access-request status |
| BRD-REQ-003 | Review access requests |
| BRD-REQ-004 | Track team requests |

## Functional Requirements

### PRD-FR-001 — Submit access requests
- **Source:** BRD-REQ-001
- **Description:** The system must allow an authenticated employee to submit an access request and find it later in the request-tracking experience.
- **Preconditions:** The employee is signed in using company sign-in.
- **Main flow:** The employee provides the information required by the access-request process, submits the request, and receives confirmation that it was recorded.
- **Alternate / error flows:** If required information is missing or the request cannot be recorded, the system identifies the issue and does not indicate successful submission.
- **Edge cases:** A repeated submission must not silently appear as a successful duplicate. **ASSUMPTION:** Duplicate handling follows the access-request process.
- **Acceptance criteria:** A submitted request is recorded and subsequently discoverable by its submitting employee in the tracking experience.
- **Interfaces touched:** Request-submission experience; access-request record and tracking experience.

### PRD-FR-002 — View access-request status
- **Source:** BRD-REQ-002
- **Description:** The system must show an employee the current status of each access request they are authorized to access.
- **Preconditions:** The employee is signed in using company sign-in and is authorized to access the request.
- **Main flow:** The employee opens request tracking, selects or views a request, and sees its current status.
- **Alternate / error flows:** If the request is unavailable or the employee is not authorized to access it, the system does not disclose its status or details and provides an appropriate access or availability message.
- **Edge cases:** If status is not available from the request process, the system must not present an invented or stale status as current. **ASSUMPTION:** The experience can indicate that status is unavailable.
- **Acceptance criteria:** An employee can find and view the current status of each request they are authorized to access without contacting IT for a status update.
- **Interfaces touched:** Employee request-tracking experience; request status data.

### PRD-FR-003 — Review access requests
- **Source:** BRD-REQ-003
- **Description:** The system must support IT administrators in accessing requests they are authorized to review and performing an initial review.
- **Preconditions:** The administrator is signed in using company sign-in and is authorized to review the request.
- **Main flow:** The administrator accesses an authorized request, performs its initial review, and the request process records the review and resulting status.
- **Alternate / error flows:** Unauthorized access or an unsuccessful review update must not be presented as a completed review.
- **Edge cases:** Requests that have not yet received an initial review remain distinguishable from reviewed requests. **ASSUMPTION:** The request process provides a way to record whether an initial review occurred.
- **Acceptance criteria:** An IT administrator can access authorized requests and perform an initial review. At least 90% of requests receive an initial review within one business day, measured using the organization’s business-day calendar and applicable time zone.
- **Interfaces touched:** IT administrator review experience; request review and status data.

### PRD-FR-004 — Track team requests
- **Source:** BRD-REQ-004
- **Description:** The system must allow managers to track requests for their team, limited to requests they are authorized to access.
- **Preconditions:** The manager is signed in using company sign-in and the requests are associated with their team and permitted by applicable access controls.
- **Main flow:** The manager opens team request tracking and views the authorized team requests and their available progress.
- **Alternate / error flows:** If the manager lacks authorization, the system must not disclose request details or status.
- **Edge cases:** Team membership or authorization changes must be reflected in access according to applicable policies. **ASSUMPTION:** The request process or an associated source provides team association and authorization information.
- **Acceptance criteria:** A manager can track authorized requests for their team and cannot access requests outside that authorization.
- **Interfaces touched:** Manager team-tracking experience; team association, authorization, and request status data.

## Business Workflow
1. An employee signs in and submits an access request.
2. The request process records the request and its status.
3. The employee tracks the request; an authorized manager can track it for their team.
4. An authorized IT administrator accesses the request and performs an initial review.
5. The request process updates status for authorized users to view.

**ASSUMPTION:** The exact status values, transitions, and review outcomes are defined by the access-request process; this PRD does not prescribe them.

## Interfaces
- **Employee UI:** Submission and request-tracking experiences, including submission confirmation and request status.
- **IT administrator UI:** Authorized request access and initial-review experience.
- **Manager UI:** Authorized team-request tracking.
- **API contracts:** **ASSUMPTION:** The BRD does not specify endpoints, protocols, payloads, or status codes. Interfaces must support request submission, authorized request retrieval, status display, and initial-review recording, with access checks applied to every operation.
- **Data model:** Request data, status, and initial-review information must be available from the request process. **ASSUMPTION:** The exact fields and system of record are determined during design.

## Validation
- Require company sign-in for employees, IT administrators, and managers.
- Enforce applicable access controls when submitting, retrieving, reviewing, and tracking requests; do not expose unauthorized request information.
- Validate required submission information according to the access-request process. **ASSUMPTION:** Field-level rules are defined by that process.
- Clearly distinguish a recorded submission or review from a failed operation; surface validation, authorization, and availability errors without falsely indicating success.
- Follow applicable data-retention policies.
- Measure the initial-review target as at least 90% of requests reviewed within one business day, using the organization’s calendar and applicable time zone.

## Out of Scope
- Changing HR records.
- Defining specific request-status values, lifecycle transitions, or review decisions not established by the BRD.
- Specifying implementation technology, API paths, or data fields not established by the BRD.