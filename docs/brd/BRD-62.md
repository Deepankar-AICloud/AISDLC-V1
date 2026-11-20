# Business Requirements Document (BRD)

## Executive Summary

Employees currently have no way to check the progress of their access requests and contact IT for updates. Providing request submission and status tracking should give employees visibility into progress, reduce avoidable status inquiries, and help managers track team requests.

## Business Problem

Employees cannot check access-request status, so they contact IT for updates. This creates avoidable follow-up work for IT and leaves employees without a clear view of request progress.

Source: AISDLC Portal reference `req_2611209e04f558506a`. No GitHub issue number was provided.

## Business Objective

Show request status so employees can see progress without contacting IT. The stated service target is for 90% of requests to receive an initial review within one business day.

## Stakeholders

- **Employees:** Submit access requests and check their progress.
- **IT administrators:** Review access requests and provide status updates.
- **Managers:** Track access requests submitted by their teams.

## Scope

- Enable employees to submit access requests.
- Enable employees to view the status of their requests.
- Enable managers to track requests submitted by their teams.
- Enable IT administrators to review requests and update their status.

## Out of Scope

- Changes to HR records.

## Functional Requirements

- **BRD-REQ-001: Access request submission.** Employees must be able to submit an access request.  
  **Acceptance criteria:** An employee can submit a request, and the system records it so it can be reviewed and tracked.

- **BRD-REQ-002: Employee request tracking.** Employees must be able to view the status of their submitted access requests.  
  **Acceptance criteria:** An employee can find their requests and see the current status for each, without contacting IT for a status update.

- **BRD-REQ-003: IT review and status updates.** IT administrators must be able to review submitted requests and update their status.  
  **Acceptance criteria:** An IT administrator can access requests for review and update a request’s status; the updated status is visible to the relevant employee.

- **BRD-REQ-004: Manager team tracking.** Managers must be able to track access requests submitted by their teams.  
  **Acceptance criteria:** A manager can view the status of team requests they are authorized to track, without accessing requests outside that authorization.

## Assumptions

- The company sign-in mechanism can identify employees, managers, and IT administrators.
- The organization will define the request statuses and the events that cause them to change.
- “Initial review” means the first review by an IT administrator; the organization will define business-day and time-zone rules for measuring the one-business-day target.
- The request does not specify notifications, request fields, or approval steps; these are not assumed as required capabilities.

## Dependencies

- Company sign-in and identity information sufficient to identify users and their roles.
- Existing or defined access-control policies to determine which requests employees, managers, and IT administrators may view or update.
- Data-retention policies governing storage and deletion of request records.
- IT review processes and status definitions needed to manage requests.

## Constraints

- The solution must use company sign-in.
- Request data and visibility must comply with company data-retention and access-control policies.
- The stated service target is that at least 90% of requests receive an initial review within one business day.

## Acceptance Criteria

- Employees can submit access requests and view the current status of their own requests.
- IT administrators can review submitted requests and update their status, with changes visible to the relevant employee.
- Managers can track team requests within their authorized access.
- Request visibility and retention comply with company policies, and access uses company sign-in.
- At least 90% of requests receive an initial review within one business day, measured using business-day rules defined by the organization.