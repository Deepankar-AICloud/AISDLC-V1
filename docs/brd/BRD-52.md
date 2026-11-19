# Executive Summary

Employees currently need to contact IT to learn the status of their access requests. This feature will let employees submit and track requests, while supporting IT review and authorized manager visibility, reducing status inquiries without changing HR records.

# Business Problem

Employees cannot check access-request status and therefore contact IT for updates. This creates avoidable follow-up work for IT and leaves employees without a self-service way to see progress.

# Business Objective

Show request status so employees can see progress without contacting IT. Support IT administrators in reviewing requests and managers in tracking team requests, subject to company access-control policies.

# Stakeholders

- **Employees:** Submit access requests and check their progress.
- **IT administrators:** Review access requests.
- **Managers:** Track team requests where authorized.

# Scope

- Submit access requests.
- Show employees the status of their requests.
- Support IT administrators’ review of requests.
- Allow managers to track team requests when permitted by access-control policies.

# Out of Scope

- Changing HR records.
- Any additional workflow, status stages, or integrations not specified in the request.

# Functional Requirements

- **BRD-REQ-001: Submit access requests.** Employees must be able to submit an access request.
  - **Priority:** High
  - **Acceptance Criteria:** An authenticated employee can submit a request, and the system records it so it can be tracked.

- **BRD-REQ-002: Track request status.** Employees must be able to view the status and progress of their access requests.
  - **Priority:** High
  - **Acceptance Criteria:** An employee can view the status of each request they are authorized to see without contacting IT.

- **BRD-REQ-003: Review requests.** IT administrators must be able to review submitted access requests.
  - **Priority:** High
  - **Acceptance Criteria:** An authorized IT administrator can access submitted requests for review.

- **BRD-REQ-004: Track team requests.** Managers must be able to track team requests where authorized.
  - **Priority:** Medium
  - **Acceptance Criteria:** A manager can view team-request status only when permitted by access-control policies.

# Assumptions

- The company’s existing sign-in process identifies employees, IT administrators, and managers.
- The organization’s existing review process and policies determine request statuses and who may view them.
- No specific request fields, status labels, or notification behavior were provided.

# Dependencies

- Company sign-in.
- Company access-control and data-retention policies.
- IT administrators’ request-review process.

# Constraints

- Use company sign-in.
- Follow company data-retention policies.
- Follow company access-control policies.
- Do not change HR records.

# Acceptance Criteria

- Employees can submit and view the status of their access requests without contacting IT for status updates.
- IT administrators can access submitted requests for review, and managers can track team requests only when authorized.
- At least 90% of requests receive an initial review within one business day.
- The feature uses company sign-in and complies with data-retention and access-control policies.
- No HR records are changed by this feature.