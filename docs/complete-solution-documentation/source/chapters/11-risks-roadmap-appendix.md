# Risks and Technical Debt {#risks-technical-debt}

## Risk register

Probability and impact use a High/Medium/Low scale. Owners are **not confirmed from the current workspace**, so a suggested owner team is given (placeholder CODEOWNERS teams). Every status is *Open*.

::: {.landscape}

| ID | Risk | Category | Evidence | Affected | P | I | Rating | Mitigation | Suggested owner |
|---|---|---|---|---|---|---|---|---|---|
| R-01 | Shell injection through comment body in workflow scripts | Security / supply chain | `feedback-handler.yml` L34, L98; `automate_pr.yml` L43 | GitHub repo, runners | High | High | **Critical** | Pass via `env:`; restrict to members; least-privilege permissions | Platform + Security |
| R-02 | SPA has no interactive sign-in, so users cannot obtain tokens | Functional / security | No `loginRedirect`/`loginPopup` in `src/frontend` | C-01, C-02 | High | High | High | Add MSAL sign-in (redirect) and `MsalAuthenticationTemplate` | Frontend |
| R-03 | Enum JSON contract mismatch breaks create and list | Functional | No `JsonStringEnumConverter`; `api.ts` uses strings | API, SPA | High | High | High | Add converter + contract test | Backend |
| R-04 | No EF migrations, so Azure SQL schema never created | Deployment | No `Migrations/`; `Migrate()` in `Program.cs` L68 | API, SQL | High | High | High | Commit migrations; apply in pipeline | Backend |
| R-05 | API managed identity has no SQL login; SQL password admin enabled; no Entra admin | Security / deployment | `main.bicep` SQL server properties | SQL | High | High | High | Entra admin, MI users, Entra-only auth | Platform |
| R-06 | Staging-slot identity lacks Key Vault role but has `KeyVault__Uri` | Deployment | `main.bicep` role assignments (API only) | Staging slot | Medium | High | High (requires validation) | Grant the slot MI Key Vault Secrets User | Platform |
| R-07 | Web app not deployed to staging/production; `VITE_*` and CORS origins not configured | Deployment | `deploy-staging.yml`, `deploy-production.yml`, `main.bicep` | Web, API | High | Medium | High | Deploy web per environment; set build variables and `Cors__AllowedOrigins` | Platform |
| R-08 | Public network access to SQL with AllowAzureServices rule; no private networking | Security | `main.bicep` | SQL, KV, Storage | Medium | High | High | Private endpoints, VNet integration, disable public access | Platform + Security |
| R-09 | `/health` anonymous contradicts NFR-001 | Compliance | `Program.cs` L95; NFR-23 | API | Medium | Low | Medium | Decide: keep anonymous minimal liveness or secure it; update NFR | Architect |
| R-10 | Notifications, request-type management and service-request workflow not implemented | Functional | No code; ARCH-23, TASK-010/011/012/015 | API, SPA | High | Medium | Medium | Implement per task plan | Product + Backend |
| R-11 | Dependency and coverage gates non-blocking; no Dependabot | Supply chain / quality | `ci.yml` `continue-on-error`, unused `COVERAGE_THRESHOLD` | CI | Medium | Medium | Medium | Make blocking; add Dependabot | Platform |
| R-12 | Broad read access for all non-employee roles; no manager scoping | Security / privacy | `List()`, `OnlyEmployee()` | API | Medium | Medium | Medium | Confirm requirements; scope queries | Architect + Backend |
| R-13 | Audit incomplete (no old/new status, separate save, 500 cap) | Compliance | `AuditAsync`, `AuditController` | Audit | Medium | Medium | Medium | Transactional audit with old/new status; paging | Backend |
| R-14 | No rate limiting, HSTS or CSP; no global exception handler | Security | `Program.cs` | API, Web | Medium | Medium | Medium | Rate limiter, headers, ProblemDetails | Backend |
| R-15 | AI Code agent runs with `--allow-all-tools` on CI runner; code QC gate lowered to 60 | AI governance | `common/llm.py`, `quality-gates.yml` (`7f25d07`) | SDLC | Medium | Medium | Medium | Keep human code review mandatory; restore stricter gate when stable; per-tool allowlist | Platform |
| R-16 | No automatic rollback; frontend has no slot | Operations | `deploy-production.yml` | Production | Low | Medium | Low | Documented swap-back; optional auto swap-back | Release manager |
| R-17 | RPO/RTO, retention and performance targets undefined | Operations / compliance | NFR-23 open questions | All | Medium | Medium | Medium | Obtain targets; configure backup/LTR | Product owner |
| R-18 | Legacy assets (`deploy.yml`, `copilot-setup-steps.yaml` reference absent Flask files) and `AZURE_CREDENTIALS` SP JSON in auxiliary workflows | Maintainability / security | Workflow files | Repo | Low | Low | Low | Remove or migrate to OIDC | Platform |

Table: Table 30.1 — Risk register

:::

## Technical-debt register

| ID | Description | Location | Business impact | Technical impact | Priority | Recommendation | Complexity |
|---|---|---|---|---|---|---|---|
| TD-01 | Request + audit saved in two `SaveChanges` calls | `AccessRequestsController.AuditAsync` | Possible unaudited changes | Consistency | High | Single unit of work | Low |
| TD-02 | Unused enum states (`Draft`, `ManagerApproval`, `AwaitingConfirmation`) and unused `AssignedToId`, `CanAdminister` | `Domain`, `Program.cs` | Confusing behaviour | Dead code | Low | Implement or remove | Low |
| TD-03 | Stage names as magic strings ("Manager", "Security", "IT") | `WorkflowService`, controller | Fragile changes | Maintainability | Medium | Enum/constants | Low |
| TD-04 | Stale committed logs (`build-release.log`, `test-release.log`) | `src/backend` | Misleading evidence | — | Low | Remove; publish CI artifacts | Low |
| TD-05 | No `package-lock.json`; CI falls back to `npm install` | `src/frontend` | Non-reproducible builds | Supply chain | Medium | Commit the lockfile; use `npm ci` | Low |
| TD-06 | Single-component SPA without router/state structure | `App.tsx` | Slower feature delivery | Maintainability | Medium | Introduce routing and feature folders | Medium |
| TD-07 | `model-routing.yml` weights not used in selection; `pricing.yml` lacks configured models | `config/` | Misleading cost/routing expectations | — | Low | Implement or simplify; update pricing | Low |
| TD-08 | Staging/production parameter files unused by workflows | `infra/`, workflows | IaC drift between environments | Drift | Medium | Run Bicep per environment in staging/production workflows | Medium |
| TD-09 | `test.yml` Python 3.11 vs runtime 3.13 | `.github/workflows/test.yml` | Version skew | — | Low | Align versions | Low |
| TD-10 | Third-party actions pinned by tag | workflows | Supply-chain risk | — | Medium | Pin by commit SHA | Low |

Table: Table 30.2 — Technical-debt register

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

# Recommendations {#recommendations}

All items below are **recommendations** and are not part of the current implementation.

1. **Secure the automation first.** Remove script interpolation from workflows and restrict comment-driven automation to repository members (R-01).
2. **Make the application work end to end:**
    - SPA sign-in.
    - JSON enum converter.
    - Committed migrations.
    - SQL managed-identity users.
    - Slot Key Vault role.
    - Web deployment, `VITE_*` values, CORS and audience settings per environment.
3. **Close functional gaps from the approved artifacts:**
    - Notifications, preferably delivered asynchronously.
    - Request-type management.
    - Service-request workflow.
    - Audit with old/new status in the same transaction.
    - Paging.
4. **Harden security:**
    - Private endpoints and VNet integration.
    - Entra-only SQL authentication.
    - Rate limiting, HSTS/CSP and a ProblemDetails handler.
    - Key Vault purge protection.
5. **Strengthen DevSecOps:**
    - Blocking SCA and coverage gates.
    - Dependabot.
    - SHA-pinned actions.
    - Branch protection with real CODEOWNERS teams.
    - SBOM and artifact attestation.
6. **Operational readiness:** alerts, availability tests, diagnostic settings, dashboards, and agreed RPO/RTO, retention and performance targets.
7. **Agentic SDLC governance:**
    - Keep human review mandatory for code.
    - Restore a stricter code QC threshold once the stage is stable.
    - Add a per-tool allowlist for the Code agent.
    - Update the pricing table for the configured models.

# Implementation Roadmap {#implementation-roadmap}

| # | Phase | Recommendation | Reason | Priority | Dependency | Expected benefit | Suggested owner | Complexity |
|---|---|---|---|---|---|---|---|---|
| 1.1 | Immediate critical fixes | Fix workflow script injection (`env:` + member check) | R-01 | P0 | — | Removes remote code execution on runners | Platform + Security | Low |
| 1.2 | Immediate critical fixes | Implement SPA sign-in (MSAL redirect) | R-02 | P0 | Entra app registrations | Users can authenticate | Frontend | Low |
| 1.3 | Immediate critical fixes | Add `JsonStringEnumConverter` + contract test | R-03 | P0 | — | Create/list work from UI | Backend | Low |
| 1.4 | Immediate critical fixes | Commit the initial EF migration; provision SQL MI users (+ slot) | R-04, R-05 | P0 | Entra SQL admin | Database usable in Azure | Backend + Platform | Medium |
| 1.5 | Immediate critical fixes | Grant the slot MI Key Vault role; set `Cors__AllowedOrigins`, `AzureAd__Audience`; deploy web + `VITE_*` per environment | R-06, R-07 | P0 | 1.2 | Staging/production functional | Platform | Medium |
| 2.1 | Architecture and security | Private endpoints, VNet integration, disable public SQL | R-08 | P1 | Network design | Reduced attack surface | Platform + Security | High |
| 2.2 | Architecture and security | Entra-only SQL auth; Key Vault purge protection | R-05 | P1 | 1.4 | Stronger identity posture | Platform | Low |
| 2.3 | Architecture and security | Rate limiting, HSTS/CSP, ProblemDetails, transactional audit with old/new status | R-13, R-14, TD-01 | P1 | — | Compliance with NFR-005, resilience | Backend | Medium |
| 2.4 | Architecture and security | Confirm and implement role scoping (manager direct reports, `/health` policy) | R-09, R-12 | P1 | Business decision | Least privilege | Architect + Backend | Medium |
| 3.1 | Test and quality | Role × endpoint integration tests, frontend tests, e2e | Test gaps | P1 | 1.2, 1.3 | Regression safety | QA + teams | Medium |
| 3.2 | Test and quality | Enforce coverage threshold and blocking SCA; Dependabot; lockfile | R-11, TD-05 | P1 | — | Supply-chain assurance | Platform | Low |
| 4.1 | Deployment | Run Bicep for staging/production; separate slot settings; optional auto swap-back | TD-08, R-16 | P2 | 1.5 | Consistent environments | Platform | Medium |
| 4.2 | Deployment | Migrate auxiliary workflows to OIDC; pin actions by SHA; remove legacy assets | R-18, TD-10 | P2 | — | Smaller attack surface | Platform | Low |
| 5.1 | Monitoring and operations | Alerts, availability test, diagnostic settings, dashboards, SPA telemetry | Observability gaps | P1 | — | Faster detection and response | Platform | Medium |
| 5.2 | Monitoring and operations | Define RPO/RTO, retention, LTR backups; DR runbook | R-17 | P2 | Business input | Recoverability | Product + Platform | Medium |
| 6.1 | Performance and scalability | Define targets; load tests; autoscale; paging | Open questions | P2 | 5.1 | Predictable performance | Platform + Backend | Medium |
| 7.1 | Future enhancements | Notifications (queue-based), request-type management, service-request workflow, approval UI | R-10 | P1 | 1.x | Completes approved scope | Product + teams | High |
| 7.2 | Future enhancements | Agentic SDLC: per-tool allowlist, stricter code gate, pricing update | R-15, TD-07 | P2 | — | Safer automation | Platform | Medium |

Table: Table 33.1 — Prioritised roadmap (no delivery dates are given)

# Open Questions {#open-questions}

| # | Question | Why it matters | Source / gap |
|---|---|---|---|
| Q1 | Who are the product owner, data owner, support owner and approvers of this document? | Governance | Not in workspace |
| Q2 | Where are the Entra app registrations (API, SPA, app roles) defined, and who assigns roles? | Access control | Not in workspace |
| Q3 | Are staging and production separate App Service apps and resource groups? | Environment isolation | Secrets `AZURE_API_APP_STAGING` / `_PROD` |
| Q4 | Should `/health` be anonymous (App Service probes) or authenticated (NFR-001)? | Compliance | `Program.cs` vs NFR-23 |
| Q5 | Which roles may read which requests (manager scoping, security reviewer, AppAdmin)? | Least privilege | ARCH-23 *(proposed)* |
| Q6 | Notification channel, recipients, content, failure handling | Functional | PRD-FR-004, TASK-010/011 |
| Q7 | Required submission fields per request type; request-type lifecycle | Functional | TASK-005/012 |
| Q8 | Service-request workflow beyond submission | Functional | TASK-015 |
| Q9 | Performance, availability, scalability, RPO/RTO targets | NFRs | NFR-23 |
| Q10 | Audit and data retention, erasure, privacy obligations | Compliance | NFR-23, BRD-23 |
| Q11 | Is Blob Storage needed (attachments)? If not, remove its role assignment | Least privilege | `main.bicep` |
| Q12 | Branch-protection, environment protection and CODEOWNERS teams | Governance | Repository settings |
| Q13 | Is Front Door required for production (`front_door_enabled: true`)? | Network/WAF | `config/environments.yml` |
| Q14 | Data residency / Azure region | Compliance | Parameter `location` defaults to the resource-group location |

Table: Table 34.1 — Open questions and missing information

# Glossary {#glossary}

| Term | Definition |
|---|---|
| Agentic SDLC | The repository's AI-assisted, human-governed delivery pipeline (`scripts/sdlc`) |
| App role | Entra ID role emitted in the `roles` claim and used by API policies |
| ARCH-COMP, BRD-REQ, PRD-FR, US, TASK, NFR | Traceability ID prefixes used in generated artifacts |
| CodeQL | GitHub static analysis (SAST) |
| DAST | Dynamic application security testing (OWASP ZAP baseline) |
| EF Core | Entity Framework Core, the .NET ORM |
| Entra ID | Microsoft Entra ID (formerly Azure AD), the identity provider |
| gitleaks | Secret-scanning tool |
| Managed identity (MI) | Azure-managed service identity used instead of stored credentials |
| MSAL | Microsoft Authentication Library (browser) |
| OIDC | OpenID Connect; used by GitHub Actions to obtain Azure tokens without secrets |
| QC | Quality control evaluation of generated artifacts |
| Slot swap | App Service deployment-slot exchange used for zero-downtime promotion and rollback |
| SPA | Single-page application |
| STRIDE | Threat categories: Spoofing, Tampering, Repudiation, Information disclosure, Denial of service, Elevation of privilege |

Table: Table 35.1 — Glossary

# Appendices {#appendices}

## Appendix A — Evidence and analysis files

| File | Content |
|---|---|
| `analysis/workspace-analysis.md` | Full workspace analysis (20 sections) |
| `analysis/component-inventory.md` | Component inventory |
| `analysis/source-code-mapping.md` | Architecture-to-source mapping |
| `analysis/assumptions.md` | Assumptions made |
| `analysis/open-questions.md` | Open questions (mirrors §34) |
| `analysis/file-inspection-log.md` | Files inspected and commands executed |
| `analysis/documentation-validation.md` | Validation results for this document |
| `guides/*.md` | Local development, deployment, operations, troubleshooting, production readiness |
| `diagrams/mermaid/*.mmd`, `diagrams/rendered/*` | Diagram sources and renderings (30) |

Table: Table 36.1 — Supporting files (relative to `docs/complete-solution-documentation/`)

## Appendix B — Figure index

| Figure | Title | Source |
|---|---|---|
| 1 | System context | `01-system-context.mmd` |
| 2 | Conceptual architecture | `02-conceptual-architecture.mmd` |
| 3 | Authorization model | `18-authorization-model.mmd` |
| 4 | High-level business workflow | `04-business-workflow.mmd` |
| 5 | Request lifecycle state machine | `05-request-state-machine.mmd` |
| 6 | Detailed application workflow | `06-detailed-application-workflow.mmd` |
| 7 | Authentication sequence | `07-authentication-sequence.mmd` |
| 8 | Submit request sequence | `08-submit-request-sequence.mmd` |
| 9 | Approval sequence | `09-approval-sequence.mmd` |
| 10 | Data-processing workflow | `10-data-processing-workflow.mmd` |
| 11 | Logical architecture | `03-logical-architecture.mmd` |
| 12 | Component diagram | `29-component-diagram.mmd` |
| 13 | Frontend architecture | `12-frontend-architecture.mmd` |
| 14 | Backend architecture | `13-backend-architecture.mmd` |
| 15 | Entity relationship diagram | `11-entity-relationship.mmd` |
| 16 | Integration architecture | `15-integration-architecture.mmd` |
| 17 | API architecture | `14-api-architecture.mmd` |
| 18 | Agent orchestration | `24-agent-orchestration.mmd` |
| 19 | Agent sequence | `25-agent-sequence.mmd` |
| 20 | Agentic SDLC state machine | `26-sdlc-state-machine.mmd` |
| 21 | Document generation and traceability | `27-document-generation-traceability.mmd` |
| 22 | Security architecture | `16-security-architecture.mmd` |
| 23 | Trust boundaries | `17-trust-boundaries.mmd` |
| 24 | Azure deployment architecture | `19-azure-deployment.mmd` |
| 25 | Network architecture | `20-network-architecture.mmd` |
| 26 | Environment topology | `30-environment-topology.mmd` |
| 27 | Production runtime | `23-production-runtime.mmd` |
| 28 | CI/CD pipeline | `21-cicd-pipeline.mmd` |
| 29 | Monitoring and observability | `22-monitoring-observability.mmd` |
| 30 | Error and retry workflow | `28-error-retry-workflow.mmd` |

Table: Table 36.2 — Figure index

## Appendix C — Regenerating this document

```bash
cd docs/complete-solution-documentation/tools
npm install          # once; set PUPPETEER_SKIP_DOWNLOAD=true to reuse the installed Chrome
npm run build        # diagrams → HTML (Pandoc) → PDF (Chrome)
```

Requirements: Node.js, Pandoc 3.x, and Google Chrome or Microsoft Edge (`CHROME_PATH` overrides detection).
