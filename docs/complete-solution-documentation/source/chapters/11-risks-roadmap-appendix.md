# Risks and Technical Debt {#risks-technical-debt}

## Risk register

Probability and impact use a High/Medium/Low scale. Owners are **not confirmed from the current workspace**, so a suggested owner team is given (placeholder CODEOWNERS teams). Every status is *Open*.

::: {.landscape}

| ID | Risk | Category | Evidence | Affected | P | I | Rating | Mitigation | Suggested owner |
|---|---|---|---|---|---|---|---|---|---|
| R-01 | Shell injection through comment body in workflow scripts | Security / supply chain | `feedback-handler.yml` L34, L98; `automate_pr.yml` L43 | GitHub repo, runners | High | High | **Critical** | Pass via `env:`; restrict to members; least-privilege permissions | Platform + Security |
| R-02 | Graph application permissions not granted and sender mailbox not set in DEV, so manager routing and e-mail fail | Functional / operations | `Graph__SenderUserId` empty; no Graph app-role assignment for the API identity | Routing, notifications | High | High | High | Entra admin grants directory read + `Mail.Send`; set `graphSenderUserId` | Identity team |
| R-03 | Staging and production not set up; their workflows lack Bicep, web deployment and a 401-aware health check | Deployment | `deploy-staging.yml`, `deploy-production.yml`; `STAGING_ENABLED` unset | Release path | High | Medium | High | Decide design (§34 Q3); extend the workflows like DEV | Platform |
| R-04 | API identity is the SQL server's Entra admin (needed for startup migrations) and will also hold Graph application permissions | Security | `main.bicep` SQL administrators | SQL, Graph | Medium | High | High | Run migrations from the pipeline with a separate identity; give the runtime identity a contained user with least rights | Platform + Backend |
| R-05 | Any Manager can decide any routed access request; no check against the routed `ManagerId` or self-approval; decision notes not stored | Security / compliance | `WorkflowService.DecideAsync` | Approvals | Medium | Medium | Medium | Check `ManagerId == caller`; persist notes | Backend |
| R-06 | App Service health probe receives 401 from `/health` | Operations | `healthCheckPath: /health`, `RequireAuthorization()` | API availability | Medium | Medium | Medium | Decide an anonymous liveness path vs NFR-001 (§34 Q4) | Architect |
| R-07 | No approver, IT, auditor or security-review screens in the SPA | Functional | `App.tsx` | Users | High | Medium | Medium | Build screens on the existing `api.ts` calls | Frontend |
| R-08 | Service-request workflow beyond submission undefined | Functional | `WorkflowService.SubmitAsync` *(open question)* | Service requests | Medium | Medium | Medium | Obtain the business decision | Product owner |
| R-09 | Tenant consent policy may block sign-in in other tenants | Identity | DEV required SPA pre-authorization | Sign-in | Low | Medium | Low | Keep pre-authorization; document admin consent | Identity team |
| R-10 | Dependency, coverage and frontend-test gates non-blocking; no Dependabot | Supply chain / quality | `ci.yml` `continue-on-error`, test echo fallback | CI | Medium | Medium | Medium | Make blocking; add Dependabot | Platform |
| R-11 | No rate limiting, HSTS or CSP; no global exception handler | Security | `Program.cs` | API, Web | Medium | Medium | Medium | Rate limiter, headers, ProblemDetails | Backend |
| R-12 | AI Code agent runs with `--allow-all-tools` on CI runner; code QC gate lowered to 60 | AI governance | `common/llm.py`, `quality-gates.yml` (`7f25d07`) | SDLC | Medium | Medium | Medium | Keep human code review mandatory; restore stricter gate when stable; per-tool allowlist | Platform |
| R-13 | No alerting on failures (5xx, *Failed* notifications) | Operations | No alert rules in Bicep | All | Medium | Medium | Medium | Alerts and availability tests | Platform |
| R-14 | RPO/RTO, retention and performance targets undefined | Operations / compliance | NFR-23 open questions | All | Medium | Medium | Medium | Obtain targets; configure backup/LTR | Product owner |
| R-15 | Legacy assets (`deploy.yml`, `copilot-setup-steps.yaml` reference absent Flask files) and `AZURE_CREDENTIALS` SP JSON in auxiliary workflows | Maintainability / security | Workflow files | Repo | Low | Low | Low | Remove or migrate to OIDC | Platform |

Table: Table 30.1 — Risk register

:::

## Resolved since version 1.0

| Version 1.0 finding | Resolution | Evidence |
|---|---|---|
| SPA had no interactive sign-in | Redirect sign-in gate and interactive token fallback | `main.tsx`, `api.ts` (`6429a22`) |
| Enum JSON contract mismatch | `JsonStringEnumConverter` + contract tests | `Program.cs`, `EnumJsonSerializationTests`, `apiFixture.test.ts` |
| No EF migrations | Initial migration committed and applied at startup; verified in DEV | `Migrations/20261103093414_InitialPortalRequestModel.cs` |
| SQL managed-identity login not provisioned; SQL password admin | Entra-only SQL with the user-assigned identity as admin; no password anywhere | `main.bicep` |
| Staging-slot identity lacked Key Vault role | Slot shares the user-assigned identity, which holds the role | `main.bicep` |
| Public SQL endpoint with `AllowAzureServices` rule | VNet integration, private endpoints and private DNS; public access disabled | `main.bicep` |
| CORS and `VITE_*` not configured for deployed origins | Bicep sets `Cors__AllowedOrigins__0`; the DEV pipeline sets `VITE_*` | `main.bicep`, `deploy-dev.yml` |
| `/health` anonymous (contradicted NFR-001) | `/health` requires authorization | `Program.cs` |
| Audit without old/new status, saved separately | `RequestAudit` with old/new status in the same `SaveChanges` | `WorkflowService` |
| Broad read access for non-employee roles | Own-request reads only; read-all limited to Auditor/AppAdmin | `RequestsController`, `AuditController` |
| Notifications, request types not implemented | Implemented with outcome tracking and admin UI | `Services/`, `RequestTypesController`, `AdminRequestTypesPage.tsx` |
| No frontend tests; 16 backend tests | 5 frontend tests; 32 backend test cases | `__tests__/`, `SmartServe.Tests` |
| No `package-lock.json` | Lockfile committed | `src/frontend/package-lock.json` |
| DEV deployment needed hand-made secrets per app and failed | App names and URLs come from Bicep outputs; one-time setup script; DEV deployed | `deploy-dev.yml`, `infra/scripts/setup-dev.ps1` |
| Orchestrator reported "FUNCTIONAL_TESTING paused — QC None" after code approval | Hand-off to CI/CD (`HANDED_OFF`) | `states.py`, `orchestrator/__init__.py` |
| API rejected every token (placeholder audience) | Placeholder removed (pending push); DEV patched | `appsettings.json` |

Table: Table 30.2 — Findings resolved since version 1.0

## Technical-debt register

| ID | Description | Location | Business impact | Technical impact | Priority | Recommendation | Complexity |
|---|---|---|---|---|---|---|---|
| TD-01 | Database migrations run at application startup | `Program.cs` | Risky with several instances | Startup coupling, elevated DB rights | Medium | Apply migrations from the pipeline | Medium |
| TD-02 | Concurrent transitions return 400 instead of 409 | `RequestsController` | Unclear client handling | API semantics | Low | Map `ConcurrentTransitionException` to 409 | Low |
| TD-03 | `api.ts` defines calls no screen uses yet | `src/frontend/src/api.ts` | — | Untested code paths | Low | Build the screens or trim | Low |
| TD-04 | Stale committed logs (`build-release.log`, `test-release.log`) | `src/backend` | Misleading evidence | — | Low | Remove; publish CI artifacts | Low |
| TD-05 | Single-component SPA without router/state structure | `App.tsx` | Slower feature delivery | Maintainability | Medium | Introduce routing as screens are added | Medium |
| TD-06 | `model-routing.yml` weights not used in selection; `pricing.yml` lacks configured models | `config/` | Misleading cost/routing expectations | — | Low | Implement or simplify; update pricing | Low |
| TD-07 | Staging/production workflows lack Bicep, web deployment and a 401-aware health check | workflows | IaC drift between environments | Drift | Medium | Mirror `deploy-dev.yml` | Medium |
| TD-08 | `test.yml` Python 3.11 vs runtime 3.13; CI frontend on Node 20 vs DEV on 22 | workflows | Version skew | — | Low | Align versions | Low |
| TD-09 | Third-party actions pinned by tag | workflows | Supply-chain risk | — | Medium | Pin by commit SHA | Low |
| TD-10 | Bicep linter warning: hard-coded `login.microsoftonline.com` | `main.bicep` | Sovereign-cloud portability | — | Low | Use `environment().authentication.loginEndpoint` | Low |

Table: Table 30.3 — Technical-debt register

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

# Recommendations {#recommendations}

All items below are **recommendations** and are not part of the current implementation.

1. **Secure the automation first.** Remove script interpolation from workflows and restrict comment-driven automation to repository members (R-01).
2. **Complete DEV:**
    - Grant the API identity its Graph permissions and set the sender mailbox (R-02).
    - Push the pending fixes (audience placeholder removal, staging switch, SPA pre-authorization in the setup script).
3. **Build the remaining screens** for managers, IT administrators, auditors and security reviewers (R-07).
4. **Tighten authorization and data rights:**
    - Restrict decisions to the routed manager and prevent self-approval; store decision notes (R-05).
    - Separate the migration identity from the runtime identity (R-04).
5. **Set up staging and production** once the design is decided, mirroring the DEV pipeline: Bicep, web deployment, 401-aware health check, `production` environment with required reviewers (R-03).
6. **Harden security:** rate limiting, HSTS/CSP and a ProblemDetails handler; Key Vault purge protection; Front Door/WAF for production.
7. **Strengthen DevSecOps:** blocking SCA, coverage and frontend-test gates; Dependabot; SHA-pinned actions; branch protection with real CODEOWNERS teams; SBOM and artifact attestation.
8. **Operational readiness:** alerts (including *Failed* notifications), availability tests, diagnostic settings, dashboards, and agreed RPO/RTO, retention and performance targets.
9. **Agentic SDLC governance:** keep human review mandatory for code; restore a stricter code QC threshold once stable; add a per-tool allowlist for the Code agent; update the pricing table.

# Implementation Roadmap {#implementation-roadmap}

| # | Phase | Recommendation | Reason | Priority | Dependency | Expected benefit | Suggested owner | Complexity |
|---|---|---|---|---|---|---|---|---|
| 1.1 | Immediate critical fixes | Fix workflow script injection (`env:` + member check) | R-01 | P0 | — | Removes remote code execution on runners | Platform + Security | Low |
| 1.2 | Immediate critical fixes | Grant Graph permissions; set sender mailbox | R-02 | P0 | Entra admin | Routing and e-mail work | Identity team | Low |
| 1.3 | Immediate critical fixes | Push pending fixes (audience, staging switch, setup script) | — | P0 | — | Repository matches DEV | Platform | Low |
| 2.1 | Functional completion | Approver, IT, auditor and security-review screens | R-07 | P1 | 1.2 | End-to-end journeys in the UI | Frontend | Medium |
| 2.2 | Functional completion | Service-request workflow decision and implementation | R-08 | P1 | Business decision | Completes approved scope | Product + Backend | Medium |
| 3.1 | Security | Routed-manager check, self-approval block, store notes | R-05 | P1 | — | Least privilege, auditability | Backend | Low |
| 3.2 | Security | Separate migration identity; least-privilege runtime DB user | R-04 | P1 | Pipeline change | Smaller blast radius | Platform + Backend | Medium |
| 3.3 | Security | Rate limiting, HSTS/CSP, ProblemDetails; Key Vault purge protection | R-11 | P1 | — | Hardened API | Backend + Platform | Low |
| 4.1 | Deployment | Staging and production environments mirroring DEV; `production` environment with reviewers | R-03, TD-07 | P1 | Design decision (§34 Q3) | Controlled releases | Platform | Medium |
| 4.2 | Deployment | Decide the health-probe approach | R-06 | P2 | NFR-001 decision | Reliable platform health | Architect | Low |
| 4.3 | Deployment | Migrate auxiliary workflows to OIDC; pin actions by SHA; remove legacy assets | R-15, TD-09 | P2 | — | Smaller attack surface | Platform | Low |
| 5.1 | Quality | Blocking gates, Dependabot, SQL Server and e2e tests | R-10 | P1 | 2.1 | Regression and supply-chain assurance | Platform + QA | Medium |
| 5.2 | Monitoring and operations | Alerts, availability test, diagnostic settings, dashboards, SPA telemetry | R-13 | P1 | — | Faster detection and response | Platform | Medium |
| 5.3 | Monitoring and operations | Define RPO/RTO, retention, LTR backups; DR runbook | R-14 | P2 | Business input | Recoverability | Product + Platform | Medium |
| 6.1 | Performance and scalability | Define targets; load tests; autoscale; move migrations out of startup | Open questions | P2 | 3.2 | Predictable performance | Platform + Backend | Medium |
| 7.1 | Agentic SDLC | Per-tool allowlist, stricter code gate, pricing update | R-12, TD-06 | P2 | — | Safer automation | Platform | Medium |

Table: Table 33.1 — Prioritised roadmap (no delivery dates are given)

# Open Questions {#open-questions}

| # | Question | Why it matters | Source / gap |
|---|---|---|---|
| Q1 | Who are the product owner, data owner, support owner and approvers of this document? | Governance | Not in workspace |
| Q2 | Who assigns app roles in Entra ID, and which Entra administrator grants the Graph permissions? | Access control | Manual steps |
| Q3 | Staging/production design: plan size (S1 or P1v3), resource group, and the production approver | Environment isolation, cost | `deploy-production.yml` assumes a staging slot on the production app |
| Q4 | Should the API expose an anonymous liveness path for App Service probes, or keep every endpoint authenticated (NFR-001)? | Availability vs compliance | `Program.cs`, NFR-23 |
| Q5 | Confirm the *(proposed)* role mappings (Manager, ItAdmin, AppAdmin) and whether decisions must be limited to the routed manager | Least privilege | `Program.cs`, ARCH-23 |
| Q6 | Which mailbox sends notifications, and are the templates acceptable? | Functional | `Graph:SenderUserId`, `EmailTemplates.cs` |
| Q7 | Required submission fields per request type; additional seeded types | Functional | `DbSeeder.cs` *(proposed)* |
| Q8 | Service-request workflow beyond submission | Functional | `WorkflowService` *(open question)* |
| Q9 | Performance, availability, scalability, RPO/RTO targets | NFRs | NFR-23 |
| Q10 | Audit and data retention, erasure, privacy obligations | Compliance | NFR-23, BRD-23 |
| Q11 | Is Blob Storage needed (attachments)? If not, remove it and its role assignment | Least privilege | `main.bicep` |
| Q12 | Branch-protection, environment protection and CODEOWNERS teams | Governance | Repository settings |
| Q13 | Is Front Door / WAF required for production (`front_door_enabled: true`)? | Network/WAF | `config/environments.yml` |
| Q14 | Data residency / Azure region (DEV uses West US 3) | Compliance | Resource-group location |

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
| Managed identity (MI) | Azure-managed service identity used instead of stored credentials; *user-assigned* identities exist independently of the app and can be shared |
| Microsoft Graph | Microsoft 365 / Entra ID API used for manager lookup and sending e-mail |
| MSAL | Microsoft Authentication Library (browser) |
| OIDC | OpenID Connect; used by GitHub Actions to obtain Azure tokens without secrets |
| Pre-authorization | Setting on an API app registration that lets a named client app use a scope without a consent prompt |
| Private endpoint | Network interface that gives an Azure service a private IP address inside a virtual network |
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
