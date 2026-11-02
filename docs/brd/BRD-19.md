# Executive Summary

SmartServe is intended to provide employees and IT teams with a secure, centralized way to handle IT service and access requests. This BRD captures the known business need and defines what must be clarified before implementation decisions are made; approval policies and other unresolved business rules remain open questions.

# Business Problem

Employees and IT teams need a centralized process for submitting, reviewing, and tracking IT service and access requests. The request lifecycle, approval rules, status expectations, and role permissions have not yet been confirmed, creating a risk that implementation would rely on unsupported assumptions.

# Business Objective

Define and validate requirements for a portal that supports employee IT service and access requests, enables authorized staff to review and manage them, and enforces access according to user role.

# Stakeholders

- Employees submitting requests
- Managers reviewing requests
- Security reviewers assessing access requests
- IT administrators handling service and access requests
- Application administrators managing the portal
- Auditors reviewing request and access activity

# Scope

- Document employee request-submission workflows.
- Define how requests are reviewed, approved, rejected, and tracked.
- Define permissions for each stakeholder role.
- Identify required notifications, request history, and audit information.
- Document functional and non-functional requirements.
- Record unresolved policies and workflow decisions as questions for stakeholder validation.

# Out of Scope

- Selecting or designing technical implementation details beyond the stated technology constraints.
- Establishing approval rules, service levels, request statuses, or notification triggers without stakeholder confirmation.
- Defining request categories, forms, or data fields not established by business stakeholders.
- Implementing or configuring the portal.

# Functional Requirements

- **BRD-REQ-001: Request submission.** The portal must support employee submission of IT service and access requests.  
  **Priority:** High  
  **Acceptance criteria:** Stakeholders confirm the request types, required information for each type, and submission workflow; the resulting requirements document records those decisions or identifies them as unresolved questions.

- **BRD-REQ-002: Request review and disposition.** The portal must support authorized staff review and management of submitted requests, including approval and rejection where applicable.  
  **Priority:** High  
  **Acceptance criteria:** Stakeholders confirm which roles may review, approve, reject, or otherwise manage each request type, and specify any required approval sequence. Unconfirmed rules are recorded as questions rather than assumed.

- **BRD-REQ-003: Request tracking and history.** The portal must provide request status and history appropriate to employees and authorized staff.  
  **Priority:** High  
  **Acceptance criteria:** Stakeholders define the statuses, who can view them, and which request events or changes must be retained in history.

- **BRD-REQ-004: Role-based permissions.** The portal must define and enforce permissions for employees, managers, security reviewers, IT administrators, application administrators, and auditors.  
  **Priority:** High  
  **Acceptance criteria:** A stakeholder-validated permission matrix specifies each role’s permitted actions and information access. Authorization must be enforced by the API, not only by the UI.

- **BRD-REQ-005: Notifications.** The portal’s notification needs for request submission, review, decisions, and status changes must be defined.  
  **Priority:** Medium  
  **Acceptance criteria:** Stakeholders identify notification events, recipients, and required channels, or record each unresolved item as a question.

- **BRD-REQ-006: Audit information.** The portal must capture request and access activity needed for authorized audit review.  
  **Priority:** High  
  **Acceptance criteria:** Stakeholders define the activity to be recorded, auditor access, and retention expectations; unresolved details are documented as questions.

# Assumptions

- SmartServe is the intended portal for employee IT service and access requests.
- The listed stakeholder groups are relevant to requirements discovery; their precise permissions remain to be validated.
- No approval sequence, status model, service-level target, notification policy, or retention period is assumed.
- Unresolved business rules and policies will be recorded as questions for stakeholder validation.

# Dependencies

- Stakeholder input is required to confirm request types, workflows, role permissions, notifications, audit needs, and applicable policies.
- The stated application environment includes a React and TypeScript frontend and a .NET 8 Web API.
- Authentication uses Microsoft Entra ID.
- Data is stored in Azure SQL through Entity Framework Core.
- Managed identity and Azure Key Vault are used for secrets; secrets must not be stored in source control.

# Constraints

- Authorization must be enforced by the API, not only by the UI.
- Secrets must use managed identity and Azure Key Vault and must not be committed to source control.
- The application uses React and TypeScript, .NET 8 Web API, Microsoft Entra ID, Azure SQL, and Entity Framework Core.
- Unresolved approval rules or business policies must be recorded as questions, not assumed.

# Acceptance Criteria

- The business problem, objective, stakeholder groups, scope, and constraints are documented in this BRD.
- Requirements **BRD-REQ-001** through **BRD-REQ-006** have stakeholder-verifiable acceptance criteria.
- The request lifecycle and role permissions are confirmed by stakeholders or explicitly recorded as unresolved questions.
- Notification and audit expectations are confirmed or recorded as unresolved questions.
- No unconfirmed approval rules or business policies are presented as settled requirements.