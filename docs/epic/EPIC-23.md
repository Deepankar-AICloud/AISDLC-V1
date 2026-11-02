# Epics, Features & User Stories

*Decomposition of approved PRD-23.md (SmartServe Portal), incorporating confirmed Epic-level decisions supplied as source requirements. Items not stated in the PRD are marked ASSUMPTION or Open Question. Personas, dependencies, and estimates not specified by the PRD are marked (proposed).*

## Traceability Matrix

| Story | Feature | Epic | PRD-FR / PRD-NFR | BRD-REQ |
|---|---|---|---|---|
| US-001 | FEATURE-001 | EPIC-001 | PRD-FR-001 | BRD-REQ-001 |
| US-002 | FEATURE-001 | EPIC-001 | PRD-FR-001, PRD-FR-002 | BRD-REQ-001, BRD-REQ-002 |
| US-003 | FEATURE-002 | EPIC-002 | PRD-FR-002, PRD-FR-003 | BRD-REQ-002, BRD-REQ-003 |
| US-003a | FEATURE-002 | EPIC-002 | PRD-FR-002, PRD-FR-003 | BRD-REQ-002, BRD-REQ-003 |
| US-004 | FEATURE-003 | EPIC-002 | PRD-FR-002, PRD-FR-003 | BRD-REQ-002, BRD-REQ-003 |
| US-005 | FEATURE-005 | EPIC-003 | PRD-FR-003 | BRD-REQ-003 |
| US-006 | FEATURE-008 | EPIC-005 | PRD-NFR-005 | BRD-REQ-009 |
| US-007 | FEATURE-008 | EPIC-005 | PRD-NFR-005 | BRD-REQ-009 |
| US-008 | FEATURE-007 | EPIC-004 | PRD-FR-004 | BRD-REQ-004 |
| US-009 | FEATURE-007 | EPIC-004 | PRD-FR-004 | BRD-REQ-004 |
| US-010 | FEATURE-009 | EPIC-006 | PRD-NFR-001 | BRD-REQ-005 |
| US-011 | FEATURE-009 | EPIC-006 | PRD-NFR-002 | BRD-REQ-006 |
| US-012 | FEATURE-010 | EPIC-006 | PRD-NFR-003 | BRD-REQ-007 |
| US-013 | FEATURE-010 | EPIC-006 | PRD-NFR-004 | BRD-REQ-008 |

**Coverage check:** Every PRD-FR (001–004) and every PRD-NFR (001–005) is traced by at least one story (no gaps). Every story above traces to a PRD-FR or PRD-NFR, and transitively to its BRD-REQ (no orphans).

---

## EPIC-001 — Request Submission & Status Tracking
**Goal:** Allow employees to submit IT service and access requests and track their status.
**Traces to:** PRD-FR-001, PRD-FR-002

### FEATURE-001 — Employee Request Submission & Visibility
**Traces to:** PRD-FR-001

#### US-001 — As an employee, I want to submit an IT service or access request so that I can obtain the service/access I need
- **Traces to:** PRD-FR-001
- **Persona:** Employee
- **Acceptance criteria:**
  - Given ASSUMPTION: the employee is authenticated, When the employee selects a request type and enters description and business justification and submits, Then the portal displays a confirmation screen containing a unique request ID and the request's status is shown as "Submitted".
  - Given required fields (type, description, business justification) are incomplete, When the employee attempts to submit, Then open question — the PRD does not define field-level validation or error messaging; behavior is undecided.
- **Open questions:**
  - What additional information (beyond type, description, justification) must employees provide for each request type? (PRD: NEEDS CLARIFICATION)
  - What validation feedback should the portal show for invalid/incomplete submissions? (PRD: NEEDS CLARIFICATION)
- **Dependencies:** None
- **Estimate:** M (proposed)

#### US-002 — As an employee, I want to view my own requests and their current status so that I can track progress
- **Traces to:** PRD-FR-001, PRD-FR-002
- **Persona:** Employee
- **Acceptance criteria:**
  - Given ASSUMPTION: the employee is authenticated, When the employee opens their requests list, Then the portal displays only requests the employee submitted, each with its request ID and current status (Submitted, Under Review, Approved, Rejected, or Fulfilled).
  - Given a request the employee submitted, When its status changes, Then the employee sees the updated status value on their requests list.
- **Open questions:**
  - Whether an existing submitted request is a precondition for it to enter "Under Review" is not defined in the PRD text (the PRD diagram leaves review/approval/rejection ordering as "order to be confirmed"); the status sequence above reflects a business decision supplied outside the PRD and is recorded here pending PRD update.
- **Dependencies:** US-001 (proposed — relationship between submission and review is unresolved in the PRD)
- **Estimate:** S (proposed)

---

## EPIC-002 — Request Approval Workflow
**Goal:** Enable authorized reviewers to approve, reject, or route requests, and for IT to fulfil approved requests.
**Traces to:** PRD-FR-002, PRD-FR-003

### FEATURE-002 — Manager & Security Reviewer Approval
**Traces to:** PRD-FR-002, PRD-FR-003

#### US-003 — As a manager, I want to approve or reject requests from my direct reports so that only authorized requests proceed
- **Traces to:** PRD-FR-002, PRD-FR-003
- **Persona:** Manager
- **Acceptance criteria:**
  - Given a request submitted by one of the manager's direct reports with status "Submitted" or "Under Review," When the manager approves it, Then for a service request the status becomes "Approved," and for an access request the status becomes "Under Review" pending security reviewer approval.
  - Given such a request, When the manager rejects it, Then the status becomes "Rejected" and no further approval steps occur.
  - Blocked pending decision: whether a manager can act only on requests already "Under Review" or also on newly "Submitted" requests is not defined in the PRD (review/approval ordering is marked "order to be confirmed").
- **Open questions:** Exact role-to-action permission boundaries beyond "approve direct reports' requests" remain undefined in the PRD (PRD-FR-003 edge cases).
- **Dependencies:** US-001, US-002 (both proposed — PRD does not confirm submission is a precondition for review/approval)
- **Estimate:** L (proposed)

#### US-003a — As a security reviewer, I want to approve or reject access requests after manager approval so that access grants receive security sign-off
- **Traces to:** PRD-FR-002, PRD-FR-003
- **Persona:** Security reviewer
- **Acceptance criteria:**
  - Given an access request with manager approval recorded, When the security reviewer approves it, Then the status becomes "Approved."
  - Given an access request with manager approval recorded, When the security reviewer rejects it, Then the status becomes "Rejected."
  - Blocked pending decision: whether security reviewers can act on access requests before manager approval is not defined in the PRD (ordering among review/approval/rejection is "order to be confirmed").
- **Open questions:** Routing/notification rules when a security reviewer rejects after manager approval are undefined in the PRD.
- **Dependencies:** US-003 (proposed — manager-before-security-reviewer sequencing is a business decision not yet reflected as a defined rule in the PRD)
- **Estimate:** M (proposed)

### FEATURE-003 — Request Fulfilment
**Traces to:** PRD-FR-002, PRD-FR-003

#### US-004 — As an IT administrator, I want to fulfil approved requests so that employees receive the requested service or access
- **Traces to:** PRD-FR-002, PRD-FR-003
- **Persona:** IT administrator
- **Acceptance criteria:**
  - Given a request with status "Approved," When the IT administrator marks it fulfilled, Then the status becomes "Fulfilled" and the employee's requests list reflects this status.
  - Blocked pending decision: whether an IT administrator can fulfil a request before all required approvals are recorded is not defined in the PRD.
- **Open questions:** What constitutes "fulfilment" per request type (e.g., required sub-steps or evidence) is not specified in the PRD.
- **Dependencies:** US-003, US-003a (proposed)
- **Estimate:** M (proposed)

---

## EPIC-003 — Role-Based Access & Portal Administration
**Goal:** Enforce role permissions and allow application administrators to manage request types.
**Traces to:** PRD-FR-003

### FEATURE-005 — Request Type Administration
**Traces to:** PRD-FR-003

#### US-005 — As an application administrator, I want to manage request types so that employees can submit against an up-to-date catalog of request types
- **Traces to:** PRD-FR-003
- **Persona:** Application administrator
- **Acceptance criteria:**
  - Given the application administrator is on the request-type management screen, When they create a new request type with a name, Then the new type appears in the list of request types available to employees when submitting a request (US-001).
  - Given an existing request type, When the application administrator disables it, Then employees no longer see it as an option when submitting new requests.
  - Blocked pending decision: whether request types distinguish "service" vs. "access" category attributes (affecting the approval chain in US-003/US-003a) is not defined in the PRD.
- **Open questions:** What fields/configuration a request type requires (e.g., associated approval chain, validation rules) is undefined in the PRD.
- **Dependencies:** None
- **Estimate:** M (proposed)

---

## EPIC-004 — Notifications
**Goal:** Keep requesters and approvers informed of relevant request events.
**Traces to:** PRD-FR-004

### FEATURE-007 — Status Change & Pending Approval Notifications
**Traces to:** PRD-FR-004

#### US-008 — As an employee who submitted a request, I want to be notified by email when my request is approved, rejected, or fulfilled so that I know its outcome without checking the portal
- **Traces to:** PRD-FR-004
- **Persona:** Employee
- **Acceptance criteria:**
  - Given a request the employee submitted, When its status changes to "Approved," "Rejected," or "Fulfilled," Then the requester receives an email notification reflecting the new status.
  - Blocked pending decision: email content/template and delivery-failure handling are not defined in the PRD.
- **Open questions:** Notification channel beyond email, and whether in-portal notifications are also required, are undefined in the PRD.
- **Dependencies:** US-003, US-003a, US-004 (proposed)
- **Estimate:** S (proposed)

#### US-009 — As an approver (manager or security reviewer), I want to be notified by email when a request is waiting for my action so that I can act promptly
- **Traces to:** PRD-FR-004
- **Persona:** Manager / Security reviewer
- **Acceptance criteria:**
  - Given a request reaches a state requiring the approver's action, When that state is reached, Then the approver receives an email notification identifying the pending request.
  - Blocked pending decision: the exact trigger point (e.g., "Submitted" vs. "Under Review") that defines "waiting for them" is not defined in the PRD due to unresolved review/approval ordering.
- **Open questions:** Reminder/escalation notifications for requests pending beyond a time threshold are not specified in the PRD.
- **Dependencies:** US-001 (proposed)
- **Estimate:** S (proposed)

---

## EPIC-005 — Audit Trail & History
**Goal:** Capture and expose request status history for auditors.
**Traces to:** PRD-NFR-005

### FEATURE-008 — Status Change Audit Logging
**Traces to:** PRD-NFR-005

#### US-006 — As an auditor, I want read-only access to all requests and their audit history so that I can review activity for compliance
- **Traces to:** PRD-NFR-005
- **Persona:** Auditor
- **Acceptance criteria:**
  - Given the auditor is viewing any request, When they open its history, Then they see every recorded status change with who made it, what changed (old status → new status), and when it occurred.
  - Given an auditor account, When the auditor attempts any create/update/delete action on a request, Then the action is denied (read-only access).
- **Open questions:** Specific audit UI/report format and export capability are not defined in the PRD.
- **Dependencies:** US-007
- **Estimate:** M (proposed)

#### US-007 — As the system, I want to record an audit entry for every request status change so that a complete, retained history exists
- **Traces to:** PRD-NFR-005
- **Persona:** System (proposed)
- **Acceptance criteria:**
  - Given a request's status changes for any reason, When the change is saved, Then the system stores an audit record containing who made the change, what changed (old status, new status), and the timestamp of the change.
  - Given an audit record with a creation timestamp, When 1 year elapses from that timestamp, Then the record is no longer returned to auditors querying request history (retained for 1 year from creation, consistent with the confirmed retention period).
- **Open questions:** Whether retained records are purged or archived after 1 year, and any legal-hold exceptions, are not defined in the PRD.
- **Dependencies:** None
- **Estimate:** M (proposed)

---

## EPIC-006 — Platform Security & Data Foundation
**Goal:** Satisfy the stated non-functional constraints for authentication, authorization, data persistence, and secret management.
**Traces to:** PRD-NFR-001, PRD-NFR-002, PRD-NFR-003, PRD-NFR-004

### FEATURE-009 — Authentication & Authorization Enforcement
**Traces to:** PRD-NFR-001, PRD-NFR-002

#### US-010 — As the system, I want to authenticate all users via Microsoft Entra ID so that only verified identities access the portal
- **Traces to:** PRD-NFR-001
- **Persona:** System (proposed)
- **Acceptance criteria:**
  - Given an unauthenticated user, When they attempt to access any portal page or API endpoint, Then they are redirected to Microsoft Entra ID sign-in and are not shown portal content until authenticated.
  - Given a user successfully authenticates via Microsoft Entra ID, When they access the portal, Then their session reflects their Entra ID identity.
- **Open questions:** Specific Entra ID protocol/configuration details are not specified in the PRD.
- **Dependencies:** None
- **Estimate:** M (proposed)

#### US-011 — As the system, I want the .NET Web API to enforce role-based authorization independent of the UI so that access control cannot be bypassed
- **Traces to:** PRD-NFR-002
- **Persona:** System (proposed)
- **Acceptance criteria:**
  - Given a user whose role does not permit a given action (e.g., an employee calling an approval endpoint), When they call the corresponding API endpoint directly, Then the API rejects the request regardless of what the UI displays.
  - Given a user whose role permits an action, When they call the corresponding API endpoint, Then the API allows the request.
- **Open questions:** Detailed role-to-endpoint/action mappings are not specified in the PRD (PRD-FR-003 edge cases).
- **Dependencies:** None
- **Estimate:** M (proposed)

### FEATURE-010 — Data Persistence & Secret Management
**Traces to:** PRD-NFR-003, PRD-NFR-004

#### US-012 — As the system, I want all request and audit data stored in Azure SQL via Entity Framework Core so that data persists reliably on the required platform
- **Traces to:** PRD-NFR-003
- **Persona:** System (proposed)
- **Acceptance criteria:**
  - Given a request is submitted, updated, or audited, When the operation completes, Then the corresponding data is persisted in Azure SQL and is retrievable via Entity Framework Core queries after an application restart.
- **Open questions:** Schema/data model details are not specified in the PRD.
- **Dependencies:** None
- **Estimate:** L (proposed)

#### US-013 — As the system, I want to access secrets only via managed identity and Azure Key Vault so that no secrets are stored in source control
- **Traces to:** PRD-NFR-004
- **Persona:** System (proposed)
- **Acceptance criteria:**
  - Given the application needs a secret (e.g., connection string, API key), When it starts up or runs, Then it retrieves the secret from Azure Key Vault using managed identity rather than from configuration files or source control.
  - Given the application's source repository, When scanned for secrets, Then no credentials or keys are found committed in source control.
- **Open questions:** None beyond the stated constraint.
- **Dependencies:** None
- **Estimate:** S (proposed)

---

## Coverage Verification

- **No orphan stories:** US-001 through US-013 (including US-003a) each trace to at least one PRD-FR or PRD-NFR.
- **No missing upstream requirements:** PRD-FR-001 (US-001, US-002), PRD-FR-002 (US-002, US-003, US-003a, US-004), PRD-FR-003 (US-003, US-003a, US-004, US-005, US-011), PRD-FR-004 (US-008, US-009), PRD-NFR-001 (US-010), PRD-NFR-002 (US-011), PRD-NFR-003 (US-012), PRD-NFR-004 (US-013), PRD-NFR-005 (US-006, US-007) — all represented.
- **Unresolved PRD items** (approval ordering, field validation, notification triggers beyond the confirmed set, retention mechanics beyond 1-year window, performance/availability targets) are carried forward as Open Questions / Blocked-pending-decision criteria rather than assumed.