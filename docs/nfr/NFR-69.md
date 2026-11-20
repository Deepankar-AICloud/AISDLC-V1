# Non-Functional Requirements

### NFR-001 — Enforce sign-in and authorization

#### Category
Security

#### Target
Every request-data access path requires company sign-in and rejects access outside the caller’s authorized role and scope.

#### Verification
Integration tests cover submission, employee status reads, IT review reads and updates, and manager team reads; confirm unauthenticated and out-of-scope requests are denied without disclosing data.

#### Rationale
The BRD requires company sign-in and compliance with access-control policies; the architecture specifies authorization on every data-access path.

#### Traces to
ARCH-COMP-001, ARCH-COMP-002, ARCH-COMP-003, ARCH-COMP-004, ARCH-COMP-005

### NFR-002 — Preserve status when an update fails

#### Category
Availability/Reliability

#### Target
Every failed status update leaves the request’s prior status unchanged.

#### Verification
Integration tests cause status updates to fail and confirm the stored status remains unchanged.

#### Rationale
The approved architecture records this as a confirmed PRD-FR-003 requirement.

#### Traces to
ARCH-COMP-002, ARCH-COMP-005

### NFR-003 — Meet the initial-review target

#### Category
Performance

#### Target
At least 90% of requests receive an initial review within one business day of submission. The definition of “initial review” and the applicable business calendar remain to be confirmed.

#### Verification
Once those definitions are confirmed, verify the reported percentage against submission and initial-review timestamps for the measured requests.

#### Rationale
The approved architecture identifies the 90%-within-one-business-day target as confirmed, while noting that the review definition and business calendar are unresolved.

#### Traces to
ARCH-COMP-001, ARCH-COMP-002, ARCH-COMP-007

### NFR-004 — Follow the data-retention policy

#### Category
Privacy/Compliance

#### Target
Access-request data is retained and disposed of in accordance with the applicable company data-retention policy.

#### Verification
Compare configured retention and disposal behavior with the approved company policy; test that records are handled according to its schedule.

#### Rationale
The BRD requires compliance with data-retention policies; the architecture identifies retention enforcement as a confirmed requirement.

#### Traces to
ARCH-COMP-006

## Open Questions
- What response-time and throughput targets are required?
- What availability and disaster-recovery targets are required?
- What observability, maintainability, and accessibility requirements apply?
- What is the approved retention schedule?
- What qualifies as an “initial review,” and which business calendar defines “one business day”?