> Extracted from `source/Complete-Application-Solution-Document.md` by `tools/build.mjs`. Edit the chapter files, not this file.

# Production Readiness Checklist {#production-readiness}

| Area | Status | Evidence |
|---|---|---|
| Architecture review | Partially ready | ARCH-23 approved through SDLC; implementation follows it, several mappings *(proposed)* |
| Security review | Not ready | R-01 critical; R-04, R-05 |
| Identity configuration | Partially ready | DEV app registrations and roles created by script; Graph permissions pending (R-02) |
| Secrets management | Ready (DEV) | User-assigned MI, Key Vault, Entra-only SQL, OIDC; no stored secrets |
| API validation | Ready | DataAnnotations, active-type check, string enums |
| Database readiness | Ready (DEV) | Migration applied in DEV through the private endpoint |
| Network | Ready (DEV) | Private endpoints, VNet integration, public access disabled on data services |
| Backup | Requires confirmation | Platform defaults only |
| Disaster recovery | Not ready | No RPO/RTO or DR design |
| Testing | Partially ready | 32 backend + 5 frontend tests pass; no SQL Server, e2e or performance tests |
| Performance | Requires confirmation | No targets or load tests |
| Monitoring | Partially ready | App Insights; notification outcome records; no dashboards |
| Alerting | Not ready | No alert rules |
| Operational runbooks | Partially ready | This document (§29); partly exercised during the DEV deployment |
| CI/CD | Partially ready | DEV fully automated; staging/production not set up (R-03) |
| Rollback | Partially ready | DEV redeploy; production slot swap documented but not set up |
| Environment separation | Requires confirmation | Staging/production design undecided (§34) |
| Data privacy | Requires confirmation | Personal identifiers and e-mail addresses stored; retention/erasure undefined |
| Cost controls | Requires confirmation | No budgets/alerts in IaC; SDLC budget null |
| Access review | Requires confirmation | Role-assignment process not documented |
| Documentation | Partially ready | This document set (v2.0); ownership pending |
| Support ownership | Requires confirmation | CODEOWNERS placeholders |
| Go-live approval | Not ready | Mandatory approval exists in the workflow; production environment not created |

Table: Table 31.1 — Production readiness (statuses: Ready, Partially ready, Not ready, Not applicable, Requires confirmation)
