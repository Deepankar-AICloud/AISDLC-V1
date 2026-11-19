## Executive Summary

Employees currently need to contact IT to learn the status of their access requests. This initiative will let employees submit and track access requests, making progress visible while supporting IT administrators’ reviews and managers’ need to track team requests.

## Business Problem

Employees cannot check access-request status independently, creating avoidable follow-up contacts to IT and limiting visibility into request progress.

## Business Objective

Show employees the progress of their access requests so they can get updates without contacting IT. The stated service success criterion is for 90% of requests to receive an initial review within one business day.

## Stakeholders

- **Employees:** Submit access requests and check their progress.
- **IT administrators:** Review access requests.
- **Managers:** Track team requests.

## Scope

- Enable employees to submit access requests.
- Enable employees to track access-request status.
- Support IT administrators’ review of requests and managers’ tracking of team requests, subject to applicable access controls.

## Out of Scope

- Changing HR records.

## Functional Requirements

- **BRD-REQ-001:** The system must allow employees to submit access requests.
  - **Priority:** High
  - **Acceptance Criteria:** An employee can submit an access request and can subsequently find it in the request-tracking experience.

- **BRD-REQ-002:** The system must show employees the status of their access requests.
  - **Priority:** High
  - **Acceptance Criteria:** An employee can view the current status of each request they are authorized to access, without contacting IT for a status update.

- **BRD-REQ-003:** The system must support IT administrators in reviewing access requests.
  - **Priority:** High
  - **Acceptance Criteria:** An IT administrator can access requests they are authorized to review and perform an initial review.

- **BRD-REQ-004:** The system must support managers in tracking team requests.
  - **Priority:** Medium
  - **Acceptance Criteria:** A manager can track requests for their team, limited to requests they are authorized to access.

## Assumptions

- Access-request status is maintained by the request process and can be displayed to authorized users.
- The specific status values and request lifecycle are not defined in the issue and must be established during design.
- “One business day” will be measured using the organization’s business-day calendar and applicable time zone.

## Dependencies

- Company sign-in is available for employees, IT administrators, and managers.
- An access-request process or system provides request records and review status.
- Applicable data-retention and access-control policies are available to guide implementation.

## Constraints

- Users must authenticate using company sign-in.
- The solution must follow company data-retention and access-control policies.
- The stated service target is that 90% of requests receive an initial review within one business day.

## Acceptance Criteria

- Employees can submit and track access requests.
- Employees can view request progress without contacting IT, subject to access controls.
- IT administrators can review authorized requests, and managers can track authorized team requests.
- At least 90% of requests receive an initial review within one business day.
- The feature does not change HR records.