# Executive Summary {#executive-summary}

## Purpose of the application

**SmartServe** is an *Enterprise IT Service & Access Request Portal*. Employees submit two kinds of request, each against an administrator-managed **request type**:

- **Access requests** (seeded examples: *Application Access*, *VPN Access*) go to the requester's line manager, who is looked up in Microsoft Entra ID. The manager approves or rejects, and an IT administrator fulfils approved requests.
- **Service requests** (seeded examples: *Laptop Request*, *Password Support*) are recorded as submitted. Their onward workflow is still an open question (§34).

Every status change is written to an audit trail in the same database transaction, and requesters and managers receive e-mail notifications through Microsoft Graph.

The repository also hosts an **Agentic SDLC platform**. It drives a requirement from a GitHub issue through BRD → PRD → Epic → Architecture → NFR → Task → Code, using AI agents (GitHub Copilot CLI), independent quality-control (QC) gates, human pull-request approval, a model router and token/cost telemetry. Issue #23 used this platform end to end: the stage PRs #24–#34 produced the SmartServe requirements, design, task plan and the application code described in this document. After the code stage, the platform hands over to the deterministic CI/CD pipeline.

## Business problem

Requests for IT access and services are typically fragmented across e-mail, chat and tickets. Approvals are inconsistent, security-sensitive access is not always reviewed, and auditors cannot reconstruct who approved what. SmartServe centralises submission, enforces a server-side approval policy and records an audit trail (`docs/brd/BRD-23.md`, BRD-REQ-001 … BRD-REQ-009).

## Summary of the current state

| Area | Summary | Status |
|---|---|---|
| Users | Employee, Manager, SecurityReviewer, ItAdmin, AppAdmin, Auditor (Entra ID app roles, defined on the DEV API app registration) | [IMPLEMENTED]{.badge .ok} |
| Core capability (API) | Submit, list/read own, manager decision, IT fulfilment, retry routing, request-type administration, audit read-all with history, security review of access requests | [IMPLEMENTED]{.badge .ok} |
| Core capability (UI) | Sign-in, submit, list own requests, administer request types | [PARTIAL]{.badge .partial} — no screens for decisions, fulfilment, audit or security review |
| Architecture | React 18 SPA (Vite) → .NET 8 Web API → EF Core 8 (committed migration) → Azure SQL; Entra ID; Key Vault; Microsoft Graph; App Insights | [IMPLEMENTED]{.badge .ok} |
| Hosting | Azure App Service (Linux) on a private virtual network for SQL and Key Vault; Bicep IaC; **DEV is deployed and running** | [IMPLEMENTED]{.badge .ok} DEV · [PLANNED]{.badge .planned} staging/production |
| Security | Entra JWT, role policies with ownership scoping, Auditor write-block, user-assigned managed identity, Entra-only SQL, private endpoints, TLS 1.2, CodeQL, gitleaks | [IMPLEMENTED]{.badge .ok} with gaps (see §18) |
| Delivery | CI on PRs; DEV provisioned and deployed by the pipeline through OIDC; staging/production workflows switched off until set up | [PARTIAL]{.badge .partial} |
| Notifications | E-mail to requester and manager through Microsoft Graph, with outcome records and a reconciliation job | [IMPLEMENTED]{.badge .ok} in code · [PARTIAL]{.badge .partial} in DEV (Graph permissions not granted) |
| Tests | 32 backend test cases (26 methods) pass; 5 frontend tests | [IMPLEMENTED]{.badge .ok} |
| AI / agents | 12 configured SDLC agents, 7 driven by the orchestrator; hand-off to CI/CD after the code stage | [IMPLEMENTED]{.badge .ok} |

Table: Table 1.1 — Solution status at a glance

## Key risks

1. **Critical — workflow script injection.** `.github/workflows/feedback-handler.yml` (lines 34 and 98) inserts `github.event.comment.body` directly into a shell script. The job holds `contents: write` and `actions: write` on a public repository (§18.9).
2. **High — notifications and manager routing do not work in DEV yet.** The API's managed identity has not been granted the Microsoft Graph application permissions (directory read, `Mail.Send`), and `Graph__SenderUserId` is empty. Access requests therefore stay *Submitted* with a failed manager notification until an Entra administrator grants the permissions (§30, R-02).
3. **High — staging and production do not exist yet.** Their workflows are switched off (`STAGING_ENABLED`), no infrastructure or GitHub secrets exist for them, and the size, resource group and production approver are undecided (§20, §34).
4. **Medium — tenant consent policy.** The Entra tenant only allows users to consent to low-risk permissions. The SPA is pre-authorized on the API, but sign-in may still need one-time admin consent for basic OpenID scopes in some tenants (§19).
5. **Medium — confirmed requirements still partially open:** the service-request workflow beyond submission, UI screens for managers, IT administrators and auditors, and several role mappings marked *(proposed)*.

## Recommended next steps

Fix the workflow injection first. Then:

1. Have an Entra administrator grant the API identity its Graph permissions and set a sender mailbox.
2. Decide the staging/production design (size, resource group, approver) and enable those environments.
3. Add the missing UI screens (decisions, fulfilment, audit, security review).
4. Close the open business questions (service-request workflow, role mappings, retention, performance targets).

The prioritised roadmap is in §33 and the readiness checklist in §31.

## One-page solution summary

![Figure 1 — System context: SmartServe, its users and external systems](diagrams/rendered/01-system-context.png)

| Question | Answer (evidence) |
|---|---|
| What is it? | IT service and access request portal with manager approval, IT fulfilment, notifications and an audit trail (`src/backend`, `src/frontend`) |
| Who uses it? | Employees, managers, security reviewers, IT admins, application admins, auditors (`Domain/Enums.cs`) |
| How does it work? | The SPA signs the user in with Entra ID and calls the REST API with a bearer token. The API enforces role and ownership rules, persists to Azure SQL with the audit row in the same transaction, looks up managers and sends e-mail through Microsoft Graph. |
| Where does it run? | Azure App Service (API + web) with VNet integration; Azure SQL and Key Vault behind private endpoints; Storage, App Insights/Log Analytics (`infra/main.bicep`). DEV is live. |
| How is it delivered? | GitHub Actions: CI → DEV (Bicep + code, OIDC) → STAGING slot (+ ZAP) → PRODUCTION slot swap with mandatory approval. Staging/production are switched off until set up. |
| How is it secured? | Entra JWT, server-side policies, user-assigned managed identity, Entra-only SQL, private endpoints, Key Vault RBAC, TLS 1.2, CodeQL, gitleaks, OIDC to Azure |
| What is missing? | Graph permissions in DEV, staging/production environments, approver/auditor UI screens, service-request workflow, alerting (§30) |
| How was it built? | With the Agentic SDLC platform (`scripts/sdlc`, `.github/agents`): issue #23 → PRs #24–#34, each QC-gated and human-approved |

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

- Two request kinds against administrator-managed request types; inactive types cannot be used for new requests (`Services/WorkflowService.cs`, `Controllers/RequestTypesController.cs`).
- Automatic routing of access requests to the requester's Entra ID manager, with an IT-admin retry when the manager cannot be resolved.
- An append-only audit trail with old and new status, actor and timestamp, written in the same transaction as the status change; Auditors read all requests and each request's history (`AuditController`).
- Notification outcomes (*Accepted*, *NotSent*, *Failed*) recorded per message, so missed e-mails are visible rather than silent (`NotificationService`).
