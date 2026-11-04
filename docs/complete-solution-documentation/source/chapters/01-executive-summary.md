# Executive Summary {#executive-summary}

## Purpose of the application

**SmartServe** is an *Enterprise IT Service & Access Request Portal*. Employees use it to request access (GitHub, Azure, VPN, applications, databases, production) and IT services (software installation, laptops, hardware, password support, general support). Requests move through a role-based approval chain: Manager → (Security reviewer for sensitive categories) → IT administrator → requester confirmation. Every action is written to an audit trail.

The repository also hosts an **Agentic SDLC platform**. It drives a requirement from a GitHub issue through BRD → PRD → Epic → Architecture → NFR → Task → Code, using AI agents (GitHub Copilot CLI), independent quality-control (QC) gates, human pull-request approval, a model router and token/cost telemetry. Issue #23 used this platform to produce the SmartServe requirements and architecture artifacts in `docs/`.

## Business problem

Requests for IT access and services are typically fragmented across e-mail, chat and tickets. Approvals are inconsistent, security-sensitive access is not always reviewed, and auditors cannot reconstruct who approved what. SmartServe centralises submission, enforces a server-side approval policy and records an audit trail (`docs/brd/BRD-23.md`, BRD-REQ-001 … BRD-REQ-009).

## Summary of the current state

| Area | Summary | Status |
|---|---|---|
| Users | Employee, Manager, SecurityReviewer, ItAdmin, AppAdmin, Auditor (Entra ID app roles) | [IMPLEMENTED]{.badge .ok} in API policies |
| Core capability | Create request, list/read, stage decisions, confirm provisioning, comments, audit read | [IMPLEMENTED]{.badge .ok} (API) · [PARTIAL]{.badge .partial} (UI covers create + list only) |
| Architecture | React 18 SPA (Vite) → .NET 8 Web API → EF Core 8 → Azure SQL; Entra ID; Key Vault; App Insights | [IMPLEMENTED]{.badge .ok} |
| Hosting | Azure App Service (Linux) with an API `staging` slot; Bicep IaC per environment | [IMPLEMENTED]{.badge .ok} |
| Security | JWT validation, role policies, ownership and stage checks, managed identity, TLS 1.2, security headers, CodeQL, gitleaks, OWASP ZAP | [IMPLEMENTED]{.badge .ok} with gaps (see §18) |
| Delivery | CI on PRs; DEV auto-deploy; STAGING slot + DAST; PRODUCTION slot swap behind a mandatory approval | [IMPLEMENTED]{.badge .ok} with gaps (see §21) |
| Notifications | E-mail on status changes (required by BRD/PRD/ARCH) | [PLANNED]{.badge .planned} — not in code |
| Tests | 16 xUnit tests pass (2 integration, 14 unit) — executed during this analysis | [IMPLEMENTED]{.badge .ok}; frontend tests absent |
| AI / agents | 12 configured SDLC agents, 7 driven by the orchestrator; Copilot CLI runner; QC with a different evaluator model | [IMPLEMENTED]{.badge .ok} |

Table: Table 1.1 — Solution status at a glance

## Key risks

1. **Critical — workflow script injection.** `.github/workflows/feedback-handler.yml` (lines 34 and 98) inserts `github.event.comment.body` directly into a shell script. The job holds `contents: write` and `actions: write` on a public repository (§18.9).
2. **High — the application cannot complete an end-to-end user journey yet.**
    - The SPA never signs the user in (no `loginRedirect`/`loginPopup`).
    - The API returns enums as numbers while the SPA sends and expects strings.
    - No EF Core migrations are committed, so `Database.Migrate()` creates no schema in Azure SQL.
    - The SQL managed-identity login is not provisioned by the IaC.
3. **High — staging and production promotion is incomplete.**
    - Only the API is deployed to staging/production; the web app is not.
    - The staging slot's managed identity has no Key Vault role.
    - CORS is not configured for deployed origins.
4. **Medium — network exposure.** SQL is reachable on its public endpoint (an `AllowAzureServices` rule); there is no VNet and there are no private endpoints.
5. **Medium — confirmed requirements not yet implemented:** notifications, request-type management, the service-request workflow and an anonymous-free `/health`.

## Recommended next steps

Fix the workflow injection first. Then close the end-to-end blockers in this order:

1. Sign-in UI.
2. JSON enum converter.
3. Initial migration and SQL managed-identity user.
4. Key Vault role for the slot.
5. Frontend deployment and CORS for staging and production.

After that, implement notifications and harden the network and supply chain. The prioritised roadmap is in §33 and the readiness checklist in §31.

## One-page solution summary

![Figure 1 — System context: SmartServe, its users and external systems](diagrams/rendered/01-system-context.png)

| Question | Answer (evidence) |
|---|---|
| What is it? | IT service and access request portal with an approval workflow and audit trail (`src/backend`, `src/frontend`) |
| Who uses it? | Employees, managers, security reviewers, IT admins, application admins, auditors (`Domain/Enums.cs`) |
| How does it work? | The SPA calls the REST API with an Entra ID bearer token. The API enforces role, ownership and stage rules, persists to Azure SQL and writes audit rows. |
| Where does it run? | Azure App Service (API + web), Azure SQL, Key Vault, Storage, App Insights/Log Analytics (`infra/main.bicep`) |
| How is it delivered? | GitHub Actions: CI → DEV → STAGING slot (+ ZAP) → PRODUCTION slot swap with mandatory approval (`.github/workflows/deploy-*.yml`) |
| How is it secured? | Entra ID JWT, server-side policies, managed identity, Key Vault RBAC, TLS 1.2, CodeQL, gitleaks, ZAP, OIDC to Azure |
| What is missing? | Sign-in UI, enum contract, migrations, notifications, private networking, staging/production frontend deployment (§30) |
| How was it built? | With the Agentic SDLC platform (`scripts/sdlc`, `.github/agents`), which produced `docs/*/*-23.md` through QC-gated, human-approved PRs |

Table: Table 1.2 — One-page solution summary

# Business Context {#business-context}

## Problem statement

According to the issue #23 requirement and `docs/brd/BRD-23.md`, employees and IT teams need a secure, centralised way to handle IT service and access requests. The complete request workflow, approval rules and status expectations had to be confirmed before implementation. The constraints are:

- Entra ID authentication.
- API-side authorization.
- Azure SQL through EF Core.
- Managed identity with Key Vault.
- No secrets in source control.

## Business objectives

| ID | Objective | Source |
|---|---|---|
| BO-1 | Employees can submit IT service and access requests | BRD-REQ-001 |
| BO-2 | Authorized staff review, approve, reject and track requests | BRD-REQ-002 |
| BO-3 | Access is enforced according to each user's role, server-side | BRD-REQ-003, BRD-REQ-006 |
| BO-4 | Required notifications, request history and audit information are captured | BRD-REQ-004, BRD-REQ-009 |
| BO-5 | Platform constraints (Entra ID, Azure SQL/EF Core, Key Vault/managed identity) are respected | BRD-REQ-005, -007, -008 |

Table: Table 2.1 — Business objectives (from `docs/brd/BRD-23.md`)

## Stakeholders

Employees, managers, security reviewers, IT administrators, application administrators and auditors (BRD-23 *Stakeholders*). Executive sponsor, product owner and support owner are **not confirmed from the current workspace** (see §34).

## Value delivered by the current implementation

- One request record per need, with a computed `RequiresSecurityReview` flag for Production, Database, Azure and VPN access (`Services/WorkflowService.cs`).
- Separation of duties: approvers cannot decide on their own requests, and each stage requires its specific role (`AccessRequestsController.Decide`).
- An append-only audit trail with actor, action and correlation ID, readable by Auditor and AppAdmin (`AuditController`).
