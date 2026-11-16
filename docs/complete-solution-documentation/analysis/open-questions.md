# Open Questions and Missing Information

Mirrors §34 of the solution document. Each item is **not confirmed from the current workspace**.

| # | Question | Why it matters | Where the gap is |
|---|---|---|---|
| Q1 | Who are the product owner, data owner, support owner and document approvers? | Governance, sign-off | Not in workspace |
| Q2 | Who assigns app roles in Entra ID, and which Entra administrator grants the Graph permissions? | Access control | Manual steps |
| Q3 | Staging/production design: plan size (S1 or P1v3), resource group, production approver | Environment isolation, cost | `deploy-production.yml` assumes a staging slot on the production app |
| Q4 | Anonymous liveness path for App Service probes, or keep every endpoint authenticated (NFR-001)? | Availability vs compliance | `Program.cs`, `docs/nfr/NFR-23.md` |
| Q5 | Confirm the *(proposed)* role mappings and whether decisions must be limited to the routed manager | Least privilege | `Program.cs`, `docs/architecture/ARCH-23.md` |
| Q6 | Which mailbox sends notifications; are the templates acceptable? | Functional scope | `Graph:SenderUserId`, `EmailTemplates.cs` |
| Q7 | Required submission fields per request type; additional seeded types | Functional scope | `DbSeeder.cs` *(proposed)* |
| Q8 | Service-request workflow beyond submission | Functional scope | `WorkflowService` *(open question)* |
| Q9 | Performance, availability, scalability, RPO/RTO targets | Non-functional requirements | NFR-23 open questions |
| Q10 | Audit and data retention, erasure, privacy obligations | Compliance | NFR-23, BRD-23 |
| Q11 | Is Blob Storage needed (attachments)? If not, remove it and its role assignment | Least privilege | `infra/main.bicep` |
| Q12 | Branch protection, environment protection rules and real CODEOWNERS teams | Governance | Repository settings, `.github/CODEOWNERS` |
| Q13 | Is Front Door / WAF required for production (`front_door_enabled: true`)? | Network / WAF | `config/environments.yml` |
| Q14 | Data residency and Azure region (DEV uses West US 3) | Compliance | Resource-group location |
