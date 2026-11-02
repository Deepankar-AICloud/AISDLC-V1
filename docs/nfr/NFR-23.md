# Non-Functional Requirements

## Category

| NFR ID | Category | Requirement (measurable) | Target | Verification | Traces to | Rationale |
|---|---|---|---|---|---|---|
| NFR-001 | Security | Every API endpoint requires a valid Microsoft Entra ID token; no endpoint is anonymous. | Every endpoint requires a valid token. | Test each endpoint with no token, an invalid token, and a valid token. | ARCH-COMP-002, ARCH-COMP-012 | The approved architecture requires Entra ID authentication on every API endpoint (PRD-NFR-001, PRD-NFR-002). |
| NFR-002 | Security | The API enforces role-based authorization server-side; UI-only authorization does not satisfy this requirement. | Authorization is enforced by the API for every authorization decision. | Test API access directly against the confirmed role permissions. Treat unspecified endpoint permissions as proposed. | ARCH-COMP-002, ARCH-COMP-005 | The approved architecture requires server-side role-based authorization (PRD-NFR-002). |
| NFR-003 | Security | Secrets use managed identity and Azure Key Vault; secrets must not be stored in source control. | Key Vault access uses managed identity; no secrets are committed to source control. | Review deployment configuration and run secret scanning. | ARCH-COMP-011 | The stated constraints require managed identity and Key Vault for secrets, and prohibit secrets in source control (PRD-NFR-004). |
| NFR-004 | Security | Users access Azure SQL only through the API, which uses Entity Framework Core for data access. | All application database access goes through the API and EF Core; users do not access the database directly. | Review access configuration and verify through integration tests. | ARCH-COMP-002, ARCH-COMP-009, ARCH-COMP-010 | The stated constraints specify Azure SQL through EF Core, and the approved architecture requires that only the API access the database (PRD-NFR-003). |
| NFR-005 | Auditability | Every request status change has one audit record containing the actor, timestamp, old status, and new status. | Every status change has a record containing all four fields. | Exercise each status transition and verify the corresponding audit record and fields. | ARCH-COMP-007, ARCH-COMP-010 | The approved architecture requires an audit record at every status change with these fields (PRD-NFR-005). |

## Target

The five requirements above have source-supported, verifiable targets. No performance, scalability, availability, audit retention, privacy/compliance, observability, maintainability, accessibility, or disaster-recovery targets are specified.

## Verification

Verify NFR-001–005 using the methods in the table. No approval gate or additional acceptance condition is established for the open questions below.

## Open Questions

- What performance targets are required?
- What scalability targets are required?
- What availability and recovery targets are required?
- What is the audit retention period?
- What privacy or compliance obligations apply?
- What observability and monitoring targets are required?
- What maintainability expectations apply?
- What accessibility standard or target applies?
- What backup and disaster-recovery objectives are required?