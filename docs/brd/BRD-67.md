# Business Requirements Document (BRD): GitHub Enterprise Access (test 3)

## Executive Summary
Employees need to submit and track access requests without contacting IT for status updates. The feature must use company sign-in and support IT administrators’ review process, with a target that 90% of requests receive an initial review within one business day.

## Business Problem
Employees cannot check the status of access requests and contact IT for updates, creating avoidable follow-up work.

## Business Objective
Let employees see the progress of their access requests so they can get updates without contacting IT.

## Stakeholders
- **Employees:** Submit access requests and check their progress.
- **IT administrators:** Review access requests.

## Scope
- Submit access requests.
- Let employees view the status of their requests.
- Support IT administrators’ review of requests.
- Require company sign-in.

## Out of Scope
The request does not specify any out-of-scope items.

## Functional Requirements
- **BRD-REQ-001: Submit access requests.** Employees must be able to submit an access request after signing in with company sign-in.
- **BRD-REQ-002: View request status.** Employees must be able to view the status of their submitted requests without contacting IT.
- **BRD-REQ-003: Review requests.** IT administrators must be able to review submitted access requests.

## Assumptions
- Employees can access the feature using their company sign-in.
- For status tracking, assume each request can be associated with its submitter and its status made available to that employee; access by other users is unspecified.
- “Initial review” means the first review by an IT administrator; further workflow details are unspecified.

## Dependencies
- Company sign-in must be available to authenticate users.

## Constraints
- The feature must use company sign-in.
- The stated service target is for 90% of requests to receive an initial review within one business day.

## Acceptance Criteria
- An employee signed in through company sign-in can submit an access request.
- An employee can view the status of a submitted request without contacting IT.
- An IT administrator can access and review submitted requests.
- At least 90% of requests receive an initial review within one business day, assuming “initial review” means the first review by an IT administrator.