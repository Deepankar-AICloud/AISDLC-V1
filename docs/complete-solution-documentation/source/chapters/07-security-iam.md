# Security Architecture {#security-architecture}

## Overview

![Figure 22 — Security architecture: implemented controls (green) and gaps (red, dashed)](diagrams/rendered/16-security-architecture.png)

## Trust boundaries

![Figure 23 — Trust boundaries across browser, App Service, Azure data plane and GitHub runners](diagrams/rendered/17-trust-boundaries.png)

## Authentication and token handling

- **API:** `AddMicrosoftIdentityWebApi(AzureAd)` validates the issuer, audience, signature and lifetime of the Entra ID access token. The settings `AzureAd:Instance`, `TenantId`, `ClientId` and `Audience` come from configuration (placeholders `<TENANT_ID>`, `<CLIENT_ID>`, `<API_APP_ID_URI>` in `appsettings.json`; Bicep app settings in Azure).
- **SPA:** an MSAL `PublicClientApplication` (authorization code with PKCE by default). Tokens are cached in `sessionStorage`; the default scope is `api://smartserve-api/access_as_user`. **No interactive sign-in is implemented.** Without an existing account, requests are sent without a token and return 401.
- **Sessions:** the API is stateless (bearer tokens, no cookies). Session lifetime is governed by Entra ID policies (**not confirmed from the current workspace**).

## Authorization and access-control matrix

Authorization is enforced **server-side** through policies (`Program.cs` L29–L36) and resource checks in `AccessRequestsController`:

- Ownership via `OnlyEmployee()`.
- Requester-only confirmation.
- No self-approval.
- Stage-specific roles.

| Action \ Role | Employee | Manager | SecurityReviewer | ItAdmin | AppAdmin | Auditor |
|---|---|---|---|---|---|---|
| Create request | ✔ | ✔ | ✔ | ✔ | ✔ | ✘ |
| List / read own | ✔ | ✔ | ✔ | ✔ | ✔ | ✔ |
| List / read all | ✘ | ✔ | ✔ | ✔ | ✔ | ✔ |
| Decide — Manager stage | ✘ | ✔ (not own) | ✘ | ✘ | ✘ | ✘ |
| Decide — Security stage | ✘ | ✘ | ✔ (not own) | ✘ | ✘ | ✘ |
| Decide — IT stage | ✘ | ✘ | ✘ | ✔ (not own) | ✘ | ✘ |
| Confirm provisioning | own only | own only | own only | own only | own only | own only |
| Comment | own only | any | any | any | any | any |
| Read audit trail | ✘ | ✘ | ✘ | ✘ | ✔ | ✔ |
| `/health` | anonymous | anonymous | anonymous | anonymous | anonymous | anonymous |

Table: Table 18.1 — Access-control matrix as implemented (✔ allowed, ✘ denied)

> The ARCH-23 decisions differ in two places. They confirm only "Employee: own requests" and "Auditor: all requests, read-only", and mark all other mappings as *(proposed)*. They also require that **no endpoint is anonymous** (NFR-001). The code grants broader reads and keeps `/health` anonymous. See §34.

## Secret management

- Application secrets are pulled from **Key Vault** through `DefaultAzureCredential` when `KeyVault:Uri` is set.
- The API's system-assigned identity holds **Key Vault Secrets User** (`infra/main.bicep`).
- **Gap:** the `staging` slot has its own identity but **no** role assignment, yet receives the same `KeyVault__Uri`. Startup in the slot is likely to fail until a role is granted (**requires validation**).
- **SQL:** the connection string uses `Authentication=Active Directory Managed Identity` with no password. However:
    - The SQL server is created with SQL authentication (admin login plus a `@secure()` password from a Key Vault reference).
    - **No Entra administrator** is configured.
    - **No database user** for the API identity is created.

  Managed-identity login therefore cannot succeed without manual steps.
- **No secrets in source control:** `appsettings.json` holds placeholders only, the parameter files use placeholders and a Key Vault reference, and gitleaks runs on PRs, pushes and weekly.
- **CI/CD:** Azure access uses **OIDC federated credentials** (`AZURE_CLIENT_ID`, `AZURE_TENANT_ID`, `AZURE_SUBSCRIPTION_ID` — identifiers, not secrets). The SDLC platform uses `COPILOT_GITHUB_TOKEN` and optional `GH_TOKEN` repository secrets.

## Application security controls

| Control | Status | Evidence / note |
|---|---|---|
| Input validation | [IMPLEMENTED]{.badge .ok} | DataAnnotations (required, max length) with `[ApiController]` automatic 400 |
| Output encoding | [IMPLEMENTED]{.badge .ok} | React escapes rendered text by default; API returns JSON |
| CORS | [PARTIAL]{.badge .partial} | Policy `spa` from `Cors:AllowedOrigins`; defaults to `http://localhost:5173`; **no deployed-origin setting in Bicep** |
| Security headers | [PARTIAL]{.badge .partial} | `X-Content-Type-Options`, `X-Frame-Options: DENY`, `Referrer-Policy: no-referrer`; **no HSTS, no Content-Security-Policy** (API and web) |
| HTTPS | [IMPLEMENTED]{.badge .ok} | `UseHttpsRedirection`, App Service `httpsOnly`, TLS ≥ 1.2 |
| Rate limiting / throttling | [NOT CONFIRMED]{.badge .nc} | No `AddRateLimiter`; no API Management or Front Door in IaC |
| Error disclosure | [PARTIAL]{.badge .partial} | No exception handler. Production does not show the developer page by default, but no ProblemDetails is standardised |
| Audit logging | [PARTIAL]{.badge .partial} | Actions audited with actor and correlation ID; reads not audited; no old/new status |
| File security | n/a | No file upload in code |

Table: Table 18.2 — Application security controls

## Data protection and network security

- **Encryption in transit:** TLS 1.2 minimum on App Service, SQL and Storage; `Encrypt=True` for SQL.
- **Encryption at rest:** Azure platform defaults (TDE for Azure SQL, Storage Service Encryption). These are **not explicitly configured** in Bicep and customer-managed keys are not used.
- **Network:** every resource uses a public endpoint. SQL has `publicNetworkAccess: Enabled` and the `AllowAzureServices` (0.0.0.0) firewall rule, which admits traffic from any Azure tenant's services. There is no VNet integration, private endpoint, NSG, WAF or Front Door. `config/environments.yml` sets `front_door_enabled: true` for production, but this is **not implemented** in IaC.

## Supply-chain and DevSecOps security

| Control | Status | Evidence |
|---|---|---|
| CodeQL | [IMPLEMENTED]{.badge .ok} | GitHub default setup (no workflow file); gates the Agentic SDLC on the current `main` commit |
| Secret scanning | [IMPLEMENTED]{.badge .ok} | `security.yml` (gitleaks, `fetch-depth: 0`) |
| Dependency scanning | [PARTIAL]{.badge .partial} | `dotnet list package --vulnerable` and `npm audit --audit-level=high` run with `continue-on-error: true` (non-blocking); no Dependabot configuration |
| DAST | [PARTIAL]{.badge .partial} | ZAP baseline on `AZURE_WEB_URL_STAGING`, but the web app is not deployed to staging by any workflow |
| Action pinning | [PARTIAL]{.badge .partial} | Actions pinned by tag (e.g. `gitleaks/gitleaks-action@v2`, `zaproxy/action-baseline@v0.12.0`), not commit SHA, except the generated `daily-repo-status.lock.yml` |
| Least-privilege tokens | [PARTIAL]{.badge .partial} | App workflows use `contents: read` + `id-token: write`; SDLC workflows need `contents/issues/pull-requests: write` and `actions: write` |
| CODEOWNERS | [PARTIAL]{.badge .partial} | `.github/CODEOWNERS` uses placeholder teams (`@smartserve/*`); branch-protection enforcement not confirmed |

Table: Table 18.3 — Supply-chain controls

## Finding — script injection in workflows {#script-injection}

[CRITICAL]{.badge .bad} In `.github/workflows/feedback-handler.yml`, lines 34 and 98 assign `BODY="${{ github.event.comment.body }}"` inside a `run:` script.

- **How it works:** GitHub expands the expression before the shell runs. A comment such as `/agent status $(<command>)` therefore executes `<command>` on the runner.
- **Exposure:** the job has `contents: write`, `issues: write`, `pull-requests: write` and `actions: write` on a public repository, so any GitHub user who can comment can modify the repository or dispatch workflows.
- **Other occurrences:** the legacy `automate_pr.yml` (line 43, `github.event.issue.title`) has the same pattern. `feature-requirement-analysis.yml` interpolates the issue title and body into a prompt, which is a lower-risk prompt-injection rather than shell-injection issue.
- **Already safe:** `agentic-sdlc-codeql-gate.yml` passes the comment body through `env:`.
- **Remediation:** pass event fields through `env:` and reference them as `"$BODY"`. Additionally restrict the trigger to repository members using `github.event.comment.author_association`.

This document does not change the workflow (documentation-only mandate). The fix is roadmap item 1.1.

## Threat model (STRIDE)

| STRIDE | Threat | Affected asset | Existing mitigation | Residual risk / recommendation |
|---|---|---|---|---|
| Spoofing | Forged or replayed tokens | API | JWT validation (issuer, audience, signature, lifetime) | Low; add Conditional Access (not confirmed) |
| Spoofing | Malicious commenter impersonates a maintainer command | SDLC workflows | Allowlisted commands | **High**: shell injection (§18.9); restrict to members |
| Tampering | Modify another user's request | Requests | Ownership and stage checks; no self-approval | Medium: broad read/comment for non-employees |
| Tampering | Alter the audit trail | AuditEntries | No write API | Medium: no DB-level immutability; DB admins can edit |
| Repudiation | Deny a decision | Approvals | ApprovalStep + AuditEntry with actor and correlation ID | Low; old/new status missing (NFR-005) |
| Information disclosure | Read others' requests | Requests | Ownership for plain employees | Medium: all non-employee roles read everything |
| Information disclosure | DB reachable from the internet / any Azure tenant | Azure SQL | TLS, MI auth intent | Medium: public network and AllowAzureServices rule |
| Denial of service | Request flooding | API | App Service scale (manual) | Medium: no rate limiting or WAF |
| Elevation of privilege | Role mis-assignment in Entra ID | API | Role-based policies | Medium: app-role assignment process not documented |
| Elevation of privilege | AI agent misuses tools in CI | Repo / runner | Path revert, stripped tokens, human PR review | Medium: `--allow-all-tools`; keep human review mandatory |

Table: Table 18.4 — STRIDE threat model

## Security-control matrix

| Domain | Implemented | Partially implemented | Not detected | Requires validation | Recommended |
|---|---|---|---|---|---|
| Identity | Entra JWT, role policies, MI, OIDC | SPA sign-in | Conditional Access evidence | App-role definitions in Entra | Sign-in UI, CA policies |
| Data | TLS, KV RBAC, no public blobs | Audit completeness | CMK, retention | SQL MI login | Entra-only SQL auth, retention policy |
| Network | HTTPS only | — | VNet, private endpoints, WAF | — | Private endpoints, Front Door/WAF |
| Application | Validation, headers, CORS allow-list | Error handling | Rate limiting, CSP, HSTS | CORS for deployed origins | Rate limiter, CSP/HSTS |
| DevSecOps | CodeQL, gitleaks, ZAP, OIDC | Dependency scans (non-blocking), DAST target | Dependabot, SBOM, signing | Branch protection | Blocking SCA, SHA pinning |

Table: Table 18.5 — Security-control classification

# Identity and Access Management {#identity-and-access-management}

| Identity | Type | Used by | Permissions | Evidence |
|---|---|---|---|---|
| End users | Entra ID accounts with app roles | SPA → API | Six app roles (Table 5.1) | `Domain/Enums.cs` (app-role manifest **not in workspace**) |
| SPA app registration | Public client (`VITE_ENTRA_CLIENT_ID`) | MSAL | Delegated scope `access_as_user` | `src/frontend/src/auth.ts` |
| API app registration | Resource / audience (`AzureAd:ClientId`) | JWT validation | Exposes the API scope and app roles | `appsettings.json`, Bicep `entraClientId` |
| API managed identity | System-assigned | API App Service | Key Vault Secrets User, Storage Blob Data Contributor, (intended) SQL access | `infra/main.bicep` |
| Staging-slot managed identity | System-assigned | API `staging` slot | **None assigned** | `infra/main.bicep` |
| Deployment identity | Entra app with GitHub OIDC federated credential | deploy-* workflows | Resource-group deployment (scope **not confirmed**) | `deploy-*.yml` |
| GitHub tokens | `GITHUB_TOKEN`, `GH_TOKEN`, `COPILOT_GITHUB_TOKEN` | SDLC and utility workflows | Workflow-scoped permissions / PAT scopes (not confirmed) | workflow files |

Table: Table 19.1 — Identities and permissions

The identity flow is shown in Figure 7 (§10). The role-to-action mapping is shown in Figure 3 (§5) and Table 18.1.
