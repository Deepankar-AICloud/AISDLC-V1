## Executive Summary

Employees need a way to see progress on their access requests without contacting IT for updates. Providing request tracking for employees and team-level visibility for managers is intended to reduce status inquiries while supporting timely IT reviews.

## Business Problem

Employees cannot check access-request status, resulting in requests to IT for progress updates. This adds avoidable work for IT and leaves employees without a clear view of their requests.

## Business Objective

Show access-request status so employees can see progress without contacting IT. The stated success target is for 90% of requests to receive an initial review within one business day.

## Stakeholders

- **Employees:** Submit access requests and check their progress.
- **IT administrators:** Review access requests and update their progress.
- **Managers:** Track requests submitted by their teams.

## Scope

- Enable employees to submit and track access requests.
- Provide managers with visibility into team requests.
- Support IT administrators in reviewing requests and communicating their status.

## Out of Scope

- Changes to HR records.
- Any additional access-request workflow or integrations not specified in the request.

## Functional Requirements

- **BRD-REQ-001:** Employees must be able to view the status and progress of their own access requests.
  - **Priority:** High
  - **Acceptance Criteria:** An employee can locate a submitted request and see its current status without contacting IT.
- **BRD-REQ-002:** Employees must be able to submit access requests.
  - **Priority:** High
  - **Acceptance Criteria:** A submitted request is recorded and available for the employee to track.
- **BRD-REQ-003:** IT administrators must be able to review access requests and update their status.
  - **Priority:** High
  - **Acceptance Criteria:** An IT administrator can review a submitted request and record a status that is visible to the appropriate users.
- **BRD-REQ-004:** Managers must be able to track access requests submitted by their teams.
  - **Priority:** Medium
  - **Acceptance Criteria:** A manager can view team requests and their statuses, but not requests outside their authorized team scope.

## Assumptions

- The request status is updated by IT administrators; automated status determination is not specified.
- The organization will define the status values and what constitutes an “initial review.”
- “Within one business day” is measured from request submission, using the organization’s business calendar.
- Managers’ team membership and authorization can be determined from an existing company source.

## Dependencies

- Company sign-in to authenticate users.
- An existing or defined source of employee and manager team relationships.
- An IT review process for handling submitted access requests.

## Constraints

- The feature must use company sign-in.
- Request visibility and handling must follow company access-control policies.
- Request data must follow company data-retention policies.

## Acceptance Criteria

- Employees can submit access requests and view the current status of their own requests.
- Managers can track requests from their teams, subject to access controls.
- IT administrators can review requests and update their status.
- At least 90% of requests receive an initial review within one business day.
- Users cannot view requests outside the scope authorized for their role.
- The feature uses company sign-in and complies with applicable access-control and data-retention policies.