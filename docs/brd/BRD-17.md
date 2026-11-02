# Business Requirements Document (BRD)

## Executive Summary
SmartServe is intended to provide employees and IT teams with a secure, centralized portal for IT service and access requests. This document captures the known business needs and identifies workflow and policy decisions that stakeholders must confirm before implementation requirements can be finalized.

**Source:** GitHub issue “SDLC intake for CodeQL commit c724fb86b3b774f875f17132b7a26ad31afb9194” (commit `c724fb86b3b774f875f17132b7a26ad31afb9194`). No human comments were provided.

## Business Problem
Employees and IT teams need a secure, centralized way to handle IT service and access requests. The complete request workflow, approval rules, and status expectations have not yet been confirmed, so implementation decisions cannot be based on those details without stakeholder input.

## Business Objective
Define and validate requirements for a portal where employees can submit IT service and access requests, authorized staff can review and manage them, and access is enforced according to each user’s role.

## Stakeholders
- **Employees:** Submit and track requests.
- **Managers:** Review requests; specific approval responsibilities are to be confirmed.
- **Security reviewers:** Assess access requests; review criteria are to be confirmed.
- **IT administrators:** Handle service and access requests.
- **Application administrators:** Manage the portal.
- **Auditors:** Review request and access activity.

## Scope
- Document employee workflows for submitting IT service and access requests.
- Define how requests are reviewed, approved, rejected, and tracked.
- Define permissions for employees, managers, security reviewers, IT administrators, application administrators, and auditors.
- Identify notification, request-history, and audit-information requirements.
- Document functional and non-functional requirements.

## Out of Scope
- Selecting or defining approval rules, routing, or business policies not provided in the issue.
- Specifying detailed technical architecture or implementation design.
- Defining request categories, forms, service levels, or status values not yet confirmed.

## Functional Requirements
- **FR-1 — Request submission:** The portal must support employees submitting IT service and access requests.  
  **Priority:** High.  
  **Acceptance criteria:** Stakeholders confirm the request types, required submission information, and any validation rules before implementation.

- **FR-2 — Request review and disposition:** The portal must support authorized staff reviewing requests and recording approval or rejection.  
  **Priority:** High.  
  **Acceptance criteria:** Stakeholders define who may review each request type, required approval steps, and the information recorded for approval or rejection.

- **FR-3 — Request tracking:** The portal must allow requests to be tracked through their lifecycle.  
  **Priority:** High.  
  **Acceptance criteria:** Stakeholders confirm the request statuses, who can view them, and what status changes are visible to employees and staff.

- **FR-4 — Role-based permissions:** The portal must provide permissions appropriate to employees, managers, security reviewers, IT administrators, application administrators, and auditors.  
  **Priority:** High.  
  **Acceptance criteria:** Stakeholders approve a role-permission matrix covering request submission, review, management, portal administration, and audit access.

- **FR-5 — Notifications:** The portal must support notifications required by the request workflow.  
  **Priority:** Medium.  
  **Acceptance criteria:** Stakeholders specify notification recipients, triggering events, channels, and required content.

- **FR-6 — Request history and audit information:** The portal must retain and make available request history and audit information for authorized users.  
  **Priority:** High.  
  **Acceptance criteria:** Stakeholders define which events and fields must be recorded, who may review them, and applicable retention requirements.

## Assumptions
- SmartServe is the portal intended to address the stated IT service and access request needs.
- Workflow details, approval rules, statuses, notification behavior, and business policies are unresolved and must be confirmed rather than assumed.
- No additional product context or issue comments were provided.

## Dependencies
- Stakeholder confirmation of request types, workflows, approval rules, role permissions, statuses, notifications, and audit requirements.
- The application context specified in the issue: React and TypeScript frontend, .NET 8 Web API, Microsoft Entra ID authentication, and Azure SQL via Entity Framework Core.
- Managed identity and Azure Key Vault for secrets management.

## Constraints
- Authorization must be enforced by the API, not only by the UI.
- Secrets must use managed identity and Azure Key Vault; secrets must not be stored in source control.
- The application uses a React and TypeScript frontend with a .NET 8 Web API.
- Authentication uses Microsoft Entra ID.
- Data is stored in Azure SQL through Entity Framework Core.
- Unresolved approval rules and business policies must be recorded as questions, not assumed.

## Acceptance Criteria
- [ ] Stakeholders validate the request types and employee submission workflows.
- [ ] Approval and rejection authority, steps, and recorded outcomes are documented for each applicable request type.
- [ ] Request statuses, visibility, and tracking expectations are defined.
- [ ] A role-permission matrix is approved for all listed stakeholder roles.
- [ ] Notification triggers, recipients, channels, and content requirements are documented.
- [ ] Required request-history and audit information, access rules, and retention expectations are documented.
- [ ] Unresolved business rules and policies are explicitly listed as open questions before implementation decisions are made.