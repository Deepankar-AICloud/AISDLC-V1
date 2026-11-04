> Extracted from `source/Complete-Application-Solution-Document.md` by `tools/build.mjs`. Edit the chapter files, not this file.

# Production Readiness Checklist {#production-readiness}

| Area | Status | Evidence |
|---|---|---|
| Architecture review | Partially ready | ARCH-23 approved through SDLC; implementation diverges (§11, §16.4) |
| Security review | Not ready | R-01 critical; network exposure R-08 |
| Identity configuration | Not ready | SPA sign-in missing (R-02); app registrations not in workspace |
| Secrets management | Partially ready | Key Vault + MI + OIDC; slot role missing (R-06); SQL password admin (R-05) |
| API validation | Partially ready | DataAnnotations; enum contract broken (R-03) |
| Database readiness | Not ready | No migrations (R-04); no MI user (R-05) |
| Backup | Requires confirmation | Platform defaults only |
| Disaster recovery | Not ready | No RPO/RTO or DR design |
| Testing | Partially ready | 16 backend tests pass; no frontend/e2e/role tests |
| Performance | Requires confirmation | No targets or load tests |
| Monitoring | Partially ready | App Insights + `/health`; no alerts/dashboards |
| Alerting | Not ready | No alert rules |
| Operational runbooks | Partially ready | This document (§29); not yet exercised |
| CI/CD | Partially ready | DEV/STAGING/PROD workflows; web not promoted (R-07) |
| Rollback | Partially ready | Manual slot swap-back documented |
| Environment separation | Requires confirmation | Depends on secrets/resource groups (§34) |
| Data privacy | Requires confirmation | Personal identifiers stored; retention/erasure undefined |
| Cost controls | Requires confirmation | No budgets/alerts in IaC; SDLC budget null |
| Access review | Requires confirmation | Role-assignment process not documented |
| Documentation | Partially ready | This document set; ownership pending |
| Support ownership | Requires confirmation | CODEOWNERS placeholders |
| Go-live approval | Not ready | Mandatory approval exists in workflow; preconditions above unmet |

Table: Table 31.1 — Production readiness (statuses: Ready, Partially ready, Not ready, Not applicable, Requires confirmation)
