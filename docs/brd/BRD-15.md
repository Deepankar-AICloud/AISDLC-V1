# Business Requirements Document (BRD)

## Executive Summary
This intake describes a proposed SmartServe portal for employees to submit IT service and access requests and for authorized staff to review and manage them. The business value and detailed workflow are not yet validated; requirements below distinguish stated goals from matters that stakeholders must confirm before implementation decisions are made.

**Traceability:** GitHub issue “SDLC intake for CodeQL commit e138c76c6d8b4e0f9449f5737c2e54d5eafeebab”; commit `e138c76c6d8b4e0f9449f5737c2e54d5eafeebab`.

## Business Problem
Employees and IT teams need a secure, centralized way to handle IT service and access requests. SmartServe is intended to address this need, but the complete request workflow, approval rules, and status expectations have not been established in the intake.

## Business Objective
Define and validate requirements for a portal where employees can submit IT service and access requests, authorized staff can review and manage them, and access is enforced according to each user’s role.

## Stakeholders
- Employees submitting requests
- Managers reviewing requests
- Security reviewers assessing access requests
- IT administrators handling service and access requests
- Application administrators managing the portal
- Auditors reviewing request and access activity

## Scope
The intake calls for documenting request submission, review and decision workflows; role permissions; notifications; request history; audit information; and functional and non-functional requirements. Specific behaviors and policies remain subject to stakeholder confirmation.

## Out of Scope
The intake does not establish any explicit exclusions. Boundaries beyond the stated scope are **undetermined** and should be confirmed with stakeholders rather than assumed.

## Functional Requirements
The following are requirements to define and validate. Details not established by the intake are explicitly left for stakeholder confirmation.

- **FR-1 — Request submission:** Define how employees submit IT service and access requests.
  - **Acceptance criteria for confirmation:** Stakeholders confirm the request types, submission steps, and information needed for each type.

- **FR-2 — Request review and decisions:** Define how authorized staff review, approve, or reject requests.
  - **Acceptance criteria for confirmation:** Stakeholders confirm who may review each request type, applicable approval rules, and decision outcomes. Unresolved policies are recorded as questions.

- **FR-3 — Request tracking and history:** Define how request status and history are made available to relevant users.
  - **Acceptance criteria for confirmation:** Stakeholders confirm which roles may view status and history, what information is included, and any access restrictions.

- **FR-4 — Role permissions:** Define permissions for employees, managers, security reviewers, IT administrators, application administrators, and auditors.
  - **Acceptance criteria for confirmation:** Stakeholders approve a role-permission definition that identifies permitted actions and information access for each role.

- **FR-5 — Notifications:** Identify the notifications needed during request handling.
  - **Acceptance criteria for confirmation:** Stakeholders specify triggering events, recipients, and required notification content and channels.

- **FR-6 — Audit information:** Define the request and access activity information needed for audit review.
  - **Acceptance criteria for confirmation:** Stakeholders identify the events and details to record, who may review them, and any applicable retention policy.

## Assumptions
- SmartServe is intended to support employee IT service and access requests, as stated in the intake.
- The stakeholder groups listed in the intake are relevant to requirements validation; their exact responsibilities and permissions remain to be confirmed.
- No approval rules, status model, required request fields, notification channels, or audit-retention periods are assumed by this document.

## Dependencies
- Stakeholder confirmation of request workflows, approval policies, role permissions, status expectations, notifications, and audit needs is needed to finalize requirements.
- The stated platform context is React and TypeScript, a .NET 8 Web API, Microsoft Entra ID authentication, and Azure SQL via Entity Framework Core.
- Requirements should account for API-enforced authorization and managed identity and Azure Key Vault for secrets, as specified in the intake.

## Constraints
- The application uses a React and TypeScript frontend with a .NET 8 Web API.
- Authentication uses Microsoft Entra ID.
- Authorization must be enforced by the API, not only by the UI.
- Data is stored in Azure SQL through Entity Framework Core.
- Secrets must use managed identity and Azure Key Vault; secrets must not be put in source control.
- Unresolved approval rules or business policies must be recorded as questions, not assumed.
- These platform and security constraints are not a complete set of non-functional requirements. Performance, availability, usability, accessibility, and other non-functional needs remain to be elicited and documented.

## Acceptance Criteria
- [ ] Stakeholders confirm the request-submission workflows for IT service and access requests.
- [ ] Review, approval, rejection, and request-tracking expectations are documented, with unresolved business policies recorded as questions.
- [ ] Role permissions are defined and confirmed for every stakeholder role listed in this document.
- [ ] Notification triggers, recipients, content, and channels are confirmed or recorded as open questions.
- [ ] Required request history and audit information, access to that information, and retention expectations are confirmed or recorded as open questions.
- [ ] Additional non-functional requirements are elicited; the listed platform and security constraints are not treated as a complete set.
- [ ] No unconfirmed workflow detail, policy, or implementation behavior is represented as an established business requirement.