# Epics, Features & User Stories

## Traceability Matrix

| Story | Feature | Epic | PRD-FR | BRD-REQ |
|---|---|---|---|---|
| US-001 | FEATURE-001 | EPIC-001 | PRD-FR-001 | BRD-REQ-001 |
| US-002 | FEATURE-001 | EPIC-001 | PRD-FR-001 | BRD-REQ-001 |
| US-003 | FEATURE-002 | EPIC-001 | PRD-FR-002 | BRD-REQ-002 |
| US-004 | FEATURE-003 | EPIC-001 | PRD-FR-003 | BRD-REQ-003 |
| US-005 | FEATURE-004 | EPIC-001 | PRD-FR-004 | BRD-REQ-004 |
| US-006 | FEATURE-004 | EPIC-001 | PRD-FR-004 | BRD-REQ-004 |
| US-007 | FEATURE-005 | EPIC-001 | PRD-FR-005 | BRD-REQ-005 |
| US-008 | FEATURE-006 | EPIC-001 | PRD-FR-006 | BRD-REQ-006 |

## Epic

### EPIC-001 — Secure IT request lifecycle
**Goal:** Enable employees and authorized staff to submit, review, track, and audit IT requests under stakeholder-confirmed rules and permissions.  
**Traces to:** PRD-FR-001, PRD-FR-002, PRD-FR-003, PRD-FR-004, PRD-FR-005, PRD-FR-006

## Feature

### FEATURE-001 — Request submission
**Traces to:** PRD-FR-001

### FEATURE-002 — Request review and disposition
**Traces to:** PRD-FR-002

### FEATURE-003 — Request tracking and history
**Traces to:** PRD-FR-003

### FEATURE-004 — Role-based permissions
**Traces to:** PRD-FR-004

### FEATURE-005 — Notifications
**Traces to:** PRD-FR-005

### FEATURE-006 — Audit information
**Traces to:** PRD-FR-006

## User Stor

### US-001 — As an employee, I want confirmed request types and required information defined so that I know what to provide.
- **Traces to:** PRD-FR-001
- **Acceptance criteria:**
  - Given a request type, when stakeholders confirm its submission workflow, then the required information and steps are documented for that type.
  - Given any unresolved request type, field, attachment, draft, eligibility, or duplicate-submission rule, when the requirements are reviewed, then each unresolved item is recorded as a question rather than assumed.
- **Dependencies:** Stakeholder confirmation
- **Estimate:** M

### US-002 — As an employee, I want to submit a valid service or access request and receive confirmation so that it can be reviewed and tracked.
- **Traces to:** PRD-FR-001
- **Acceptance criteria:**
  - Given an authenticated employee and a request that meets confirmed requirements, when the employee submits it successfully, then the portal confirms receipt and the request is available for subsequent review and tracking.
  - Given a request with validation errors, when submission is attempted, then the portal explains the errors and allows correction.
- **Dependencies:** US-001
- **Estimate:** M

### US-003 — As an authorized reviewer, I want confirmed review and disposition rules so that I can take only permitted actions on requests.
- **Traces to:** PRD-FR-002
- **Acceptance criteria:**
  - Given each request type, when stakeholders confirm review roles, allowed actions, and any approval sequence, then those rules are documented.
  - Given an unresolved rule for approval, rejection, further information, reassignment, escalation, withdrawal, reopening, or decision changes, when requirements are reviewed, then the rule is recorded as a question.
  - Given a user who is not authorized for an action, when they attempt it, then the operation is denied.
- **Dependencies:** Stakeholder confirmation
- **Estimate:** L

### US-004 — As an employee or authorized staff member, I want to view permitted request status and history so that I can track progress and activity.
- **Traces to:** PRD-FR-003
- **Acceptance criteria:**
  - Given an existing request and a user authorized to view it, when the user opens the request, then the current status and available history are displayed according to confirmed visibility rules.
  - Given unresolved status values, transitions, history events, visibility, or retention rules, when requirements are reviewed, then each is recorded as a question.
  - Given a user not authorized to view a request, when they attempt to access it, then access is denied.
- **Dependencies:** Stakeholder confirmation
- **Estimate:** M

### US-005 — As a stakeholder, I want a validated permission matrix for all portal roles so that each role’s access is explicit.
- **Traces to:** PRD-FR-004
- **Acceptance criteria:**
  - Given the employee, manager, security reviewer, IT administrator, application administrator, and auditor roles, when stakeholders validate permissions, then the matrix specifies each role’s permitted actions and information access.
  - Given unresolved role assignment, overlapping-role, delegation, or changed-role behavior, when the matrix is reviewed, then each unresolved rule is recorded as a question.
- **Dependencies:** Stakeholder confirmation
- **Estimate:** M

### US-006 — As an application owner, I want the API to enforce the validated permission matrix so that protected operations cannot rely on UI restrictions alone.
- **Traces to:** PRD-FR-004
- **Acceptance criteria:**
  - Given an authenticated user and a protected API operation, when the user is authorized by the validated policy, then the API permits the operation.
  - Given an authenticated user not authorized by that policy, when the user calls the protected API directly, then the API denies the operation independently of the UI.
  - Given an unauthenticated request, when it calls a protected API operation, then the operation is denied.
- **Dependencies:** US-005
- **Estimate:** M

### US-007 — As a request participant, I want notifications sent according to confirmed policies so that relevant request events are communicated.
- **Traces to:** PRD-FR-005
- **Acceptance criteria:**
  - Given a stakeholder-confirmed notification event, when it occurs, then the agreed recipients receive the notification through the agreed channel.
  - Given unresolved events, recipients, channels, timing, message content, retry, delivery-failure, or duplicate-notification rules, when requirements are reviewed, then each is recorded as a question.
  - Given an unconfirmed trigger, recipient, or channel, when notification behavior is specified, then none is assumed.
- **Dependencies:** Stakeholder confirmation
- **Estimate:** M

### US-008 — As an auditor, I want confirmed request and access activity recorded and available under validated access rules so that I can review relevant activity.
- **Traces to:** PRD-FR-006
- **Acceptance criteria:**
  - Given an activity stakeholders have confirmed must be audited, when it occurs, then the portal records it according to the confirmed event requirements.
  - Given an auditor authorized under confirmed access rules, when they request audit information, then the permitted information is available.
  - Given an unauthorized user, when they request audit information, then access is denied.
  - Given unresolved event details, sensitive-information handling, immutability, retention, export, or failure-handling rules, when requirements are reviewed, then each is recorded as a question.
- **Dependencies:** Stakeholder confirmation
- **Estimate:** L