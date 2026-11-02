# Business Requirements Document (BRD)

## Executive Summary

This BRD captures requirements for SmartServe, a portal intended to let employees submit IT service and access requests and authorized staff review and manage them. It documents the stated workflow, role, platform, and audit needs while leaving unresolved business rules as open questions rather than making implementation assumptions. The intake references CodeQL-passing commit `46b4faa8e852024273028cc962720b154514a383`.

## Business Problem

Employees and IT teams need a secure, centralized way to handle IT service and access requests. The request workflow, approval rules, and status expectations still need confirmation before implementation decisions are made.

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

- Document employee request-submission workflows.
- Define how requests are reviewed, approved, rejected, and tracked.
- Define role permissions for the listed stakeholders.
- Identify required notifications, request history, and audit information.
- Document functional and non-functional requirements.

## Out of Scope

- Approval rules, routing, required request fields, and status definitions not specified in the issue.
- Performance, availability, and retention targets; these remain open questions.
- Implementation details beyond the stated technology and security constraints.
- Any additional exclusions not recorded in the issue.

## Functional Requirements

- **BRD-REQ-001: Employee request submission.** Document workflows for employees to submit IT service and access requests.
  - Priority: High
  - Acceptance Criteria: The requirements document describes employee request-submission workflows for both IT service and access requests.

- **BRD-REQ-002: Request review and disposition.** Define how requests are reviewed, approved, rejected, and tracked.
  - Priority: High
  - Acceptance Criteria: The requirements document addresses review, approval, rejection, and tracking without presuming unresolved rules or status expectations.

- **BRD-REQ-003: Role permissions.** Define permissions for employees, managers, security reviewers, IT administrators, application administrators, and auditors.
  - Priority: High
  - Acceptance Criteria: The requirements document covers role permissions for each listed stakeholder group.

- **BRD-REQ-004: Notifications and records.** Identify required notifications, request history, and audit information.
  - Priority: Medium
  - Acceptance Criteria: The requirements document identifies these needs and records details that remain undecided as open questions.

## Non-Functional Requirements

- **BRD-REQ-005: Authentication.** The application uses Microsoft Entra ID for authentication.
  - Priority: High
  - Acceptance Criteria: The requirements specify Microsoft Entra ID authentication.

- **BRD-REQ-006: Server-side authorization.** Authorization is enforced by the API, not only by the UI, and is based on user roles.
  - Priority: High
  - Acceptance Criteria: The requirements specify API-side enforcement of role-based authorization.

- **BRD-REQ-007: Data platform.** Data is stored in Azure SQL through Entity Framework Core.
  - Priority: High
  - Acceptance Criteria: The requirements specify Azure SQL and Entity Framework Core for data storage.

- **BRD-REQ-008: Secret management.** Secrets use managed identity and Azure Key Vault and are not placed in source control.
  - Priority: High
  - Acceptance Criteria: The requirements specify managed identity and Azure Key Vault for secrets and prohibit storing secrets in source control.

- **BRD-REQ-009: Request history and audit information.** The portal’s requirements include request history and audit information.
  - Priority: Medium
  - Acceptance Criteria: The requirements document identifies request history and audit information needs; retention and other unspecified targets remain open questions.

## Assumptions

- The issue describes SmartServe as intended to serve as the centralized portal; its detailed product context is not yet recorded.
- No required employee-provided fields, approval routing, or detailed workflow behavior is assumed.
- No performance, availability, or retention targets are assumed.

**Open questions**
- What information must employees provide for each request type?
- Which approval rules, reviewers, and routing paths apply to each request type?
- What request statuses and status expectations should users see?
- Which events require notifications, and who should receive them?
- What request history and audit details must be captured and made available?
- What are the required performance, availability, and retention targets?

## Dependencies

- Microsoft Entra ID for authentication.
- Azure SQL and Entity Framework Core for data storage.
- Azure Key Vault and managed identity for secret management.
- The stated React and TypeScript frontend and .NET 8 Web API.

## Constraints

- The application uses a React and TypeScript frontend with a .NET 8 Web API.
- Authentication uses Microsoft Entra ID.
- Authorization must be enforced by the API, not only by the UI.
- Data is stored in Azure SQL through Entity Framework Core.
- Secrets must use managed identity and Azure Key Vault; secrets must not be put in source control.
- Unresolved approval rules or business policies must be recorded as questions, not assumed.

## Acceptance Criteria

- [ ] The BRD documents employee submission workflows for IT service and access requests.
- [ ] The BRD addresses request review, approval, rejection, and tracking.
- [ ] The BRD defines role-permission requirements for all stakeholder groups listed in the issue.
- [ ] The BRD identifies notification, request history, and audit information needs.
- [ ] The BRD records the stated technology and security constraints, including API-side authorization.
- [ ] Unspecified workflow rules, required request fields, status expectations, and performance, availability, and retention targets are left as open questions rather than invented criteria.