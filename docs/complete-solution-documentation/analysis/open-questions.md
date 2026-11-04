# Open Questions and Missing Information

Mirrors §34 of the solution document. Each item is **not confirmed from the current workspace**.

| # | Question | Why it matters | Where the gap is |
|---|---|---|---|
| Q1 | Who are the product owner, data owner, support owner and document approvers? | Governance, sign-off | Not in workspace |
| Q2 | Where are the Entra app registrations (API, SPA, app roles) defined, and who assigns roles? | Access control | Not in workspace |
| Q3 | Are staging and production separate App Service apps and resource groups? | Environment isolation | GitHub secrets only |
| Q4 | Should `/health` stay anonymous (App Service probes) or require authentication (NFR-001)? | Compliance | `Program.cs` vs `docs/nfr/NFR-23.md` |
| Q5 | Which roles may read which requests (manager scoping, security reviewer, AppAdmin)? | Least privilege | `docs/architecture/ARCH-23.md` marks mappings *(proposed)* |
| Q6 | Notification channel, recipients, content and failure handling | Functional scope | PRD-FR-004, TASK-010/011 |
| Q7 | Required submission fields per request type; request-type lifecycle | Functional scope | TASK-005/012 |
| Q8 | Service-request workflow beyond submission | Functional scope | TASK-015 |
| Q9 | Performance, availability, scalability, RPO/RTO targets | Non-functional requirements | NFR-23 open questions |
| Q10 | Audit and data retention, erasure, privacy obligations | Compliance | NFR-23, BRD-23 |
| Q11 | Is Blob Storage needed (attachments)? If not, remove its role assignment | Least privilege | `infra/main.bicep` |
| Q12 | Branch protection, environment protection rules and real CODEOWNERS teams | Governance | Repository settings, `.github/CODEOWNERS` |
| Q13 | Is Front Door required for production (`front_door_enabled: true`)? | Network / WAF | `config/environments.yml` |
| Q14 | Data residency and Azure region | Compliance | `location` defaults to the resource-group location |
