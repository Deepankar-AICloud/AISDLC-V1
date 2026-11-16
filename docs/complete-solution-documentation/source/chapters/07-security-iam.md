# Security Architecture {#security-architecture}

## Overview

![Figure 22 — Security architecture: implemented controls (green) and gaps (red, dashed)](diagrams/rendered/16-security-architecture.png)

## Trust boundaries

![Figure 23 — Trust boundaries across browser, App Service, Azure data plane and GitHub runners](diagrams/rendered/17-trust-boundaries.png)

## Authentication and token handling

- **API:** `AddMicrosoftIdentityWebApi(AzureAd)` validates the issuer, audience, signature and lifetime of the Entra ID access token. `AzureAd:Instance`, `TenantId` and `ClientId` come from App Service settings set by Bicep; with no explicit `Audience`, the API accepts tokens whose audience is its own client ID (v2 tokens, `requestedAccessTokenVersion: 2`).
- **Fixed during the DEV deployment:** `appsettings.json` contained a placeholder `"Audience": "<api-app-id-uri>"`, which made the API reject every real token with 401. The placeholder has been removed in the working tree (pending push), and the DEV app was patched with `AzureAd__Audience=<API_CLIENT_ID>` until the next deployment.
- **SPA:** an MSAL `PublicClientApplication` (authorization code with PKCE). `MsalAuthenticationTemplate` performs a **redirect sign-in** before the app renders, requesting `api://<API_CLIENT_ID>/access_as_user`. Tokens are cached in `sessionStorage`; when silent renewal needs interaction, `api.ts` starts an interactive redirect.
- **Consent:** the tenant only allows users to consent to low-risk permissions. The *SmartServe Web* app is therefore **pre-authorized** on the *SmartServe API* app for `access_as_user`, so no consent prompt appears for the API scope (`setup-dev.ps1`). If the tenant also blocks consent for the basic OpenID scopes, an administrator must grant consent once.
- **Sessions:** the API is stateless (bearer tokens, no cookies). Session lifetime is governed by Entra ID policies (**not confirmed from the current workspace**).

## Authorization and access-control matrix

Authorization is enforced **server-side**: a fallback policy requires an authenticated user everywhere, named policies (`Program.cs`) restrict each endpoint, own-request reads are filtered by `RequesterId`, and a middleware blocks every write for principals holding the Auditor role.

| Action \ Role | Employee | Manager | SecurityReviewer | ItAdmin | AppAdmin | Auditor |
|---|---|---|---|---|---|---|
| Submit request | ✔ | ✔ *(p)* | ✘ | ✔ *(p)* | ✔ *(p)* | ✘ |
| List / read own requests | ✔ | ✘ | ✘ | ✘ | ✘ | ✘ |
| Approve / reject access request | ✘ | ✔ *(p)* | ✘ | ✘ | ✘ | ✘ |
| Fulfil approved request | ✘ | ✘ | ✘ | ✔ *(p)* | ✘ | ✘ |
| Retry manager routing | ✘ | ✘ | ✘ | ✔ *(p)* | ✘ | ✘ |
| Read request types | ✔ | ✔ | ✔ | ✔ | ✔ | ✔ |
| Create / edit / deactivate request types | ✘ | ✘ | ✘ | ✘ | ✔ *(p)* | ✘ |
| Read all requests and histories | ✘ | ✘ | ✘ | ✘ | ✔ *(p)* | ✔ |
| Read access requests (security review) | ✘ | ✘ | ✔ | ✘ | ✘ | ✘ |
| Any write (POST/PUT/PATCH/DELETE) | — | — | — | — | — | **blocked** |
| `/health` | ✔ | ✔ | ✔ | ✔ | ✔ | ✔ |

Table: Table 18.1 — Access-control matrix as implemented (✔ allowed, ✘ denied, *(p)* mapping marked *(proposed)* in code; `/health` requires any valid token)

> Two gaps remain. The decision endpoint does not check that the caller is the manager the request was routed to, and does not prevent approving one's own request (R-05). Decision notes are accepted but not stored.

## Secret management

- **No SQL password exists.** The SQL server uses **Entra-only authentication**; the API's **user-assigned managed identity** is the server's Entra administrator, because EF Core migrations run at startup and need schema rights. The connection string names that identity (`Authentication=Active Directory Managed Identity; User Id=<IDENTITY_CLIENT_ID>`).
- **Key Vault:** the same identity holds **Key Vault Secrets User**, assigned before the app is created so startup never races the role assignment. The identity is selected through the `AZURE_CLIENT_ID` app setting and shared with the `staging` slot where one exists.
- **No secrets in source control:** `appsettings.json` holds placeholders only; the parameter files no longer contain any secret reference; gitleaks runs on PRs, pushes and weekly.
- **CI/CD:** Azure access uses an **OIDC federated credential** on the user-assigned identity `id-smartserve-github-dev`, which has Contributor and Role Based Access Control Administrator on the DEV resource group. Two federated subjects are registered, because GitHub issues this repository's token with the newer ID-based subject (`repo:<OWNER>@<OWNER_ID>/<REPO>@<REPO_ID>:environment:dev`). The GitHub `dev` environment holds the identifiers `AZURE_CLIENT_ID`, `AZURE_TENANT_ID`, `AZURE_SUBSCRIPTION_ID`, `AZURE_RESOURCE_GROUP_DEV` (not secrets) and the variables `ENTRA_API_CLIENT_ID`, `ENTRA_SPA_CLIENT_ID`. The SDLC platform uses `COPILOT_GITHUB_TOKEN` and an optional `GH_TOKEN`.

## Application security controls

| Control | Status | Evidence / note |
|---|---|---|
| Input validation | [IMPLEMENTED]{.badge .ok} | DataAnnotations (required, max length) with `[ApiController]` automatic 400; active request type checked at submission |
| Output encoding | [IMPLEMENTED]{.badge .ok} | React escapes rendered text by default; API returns JSON |
| CORS | [IMPLEMENTED]{.badge .ok} | Policy `spa`; Bicep sets `Cors__AllowedOrigins__0` to the deployed web origin |
| Security headers | [PARTIAL]{.badge .partial} | `X-Content-Type-Options`, `X-Frame-Options: DENY`, `Referrer-Policy: no-referrer`; **no HSTS, no Content-Security-Policy** |
| HTTPS | [IMPLEMENTED]{.badge .ok} | `UseHttpsRedirection`, App Service `httpsOnly`, TLS ≥ 1.2, FTPS disabled |
| Rate limiting / throttling | [NOT CONFIRMED]{.badge .nc} | No `AddRateLimiter`; no API Management or Front Door in IaC |
| Error disclosure | [PARTIAL]{.badge .partial} | No exception handler; workflow errors return plain-text 400 messages |
| Audit logging | [IMPLEMENTED]{.badge .ok} | Status changes audited with old/new status in the same transaction; reads and request-type changes are not audited |
| Concurrency | [IMPLEMENTED]{.badge .ok} | GUID concurrency tokens; losing transitions roll back with their audit row |
| File security | n/a | No file upload in code |

Table: Table 18.2 — Application security controls

## Data protection and network security

- **Encryption in transit:** TLS 1.2 minimum on App Service, SQL and Storage; `Encrypt=True` for SQL.
- **Encryption at rest:** Azure platform defaults (TDE for Azure SQL, Storage Service Encryption). These are **not explicitly configured** in Bicep and customer-managed keys are not used.
- **Network:** SQL, Key Vault and Storage have **public network access disabled** (also enforced by a subscription policy). The API is integrated into the subnet `app` of a virtual network (`10.40.0.0/16`) with all outbound traffic routed through it, and reaches SQL and Key Vault through **private endpoints** in the subnet `private-endpoints`, resolved by private DNS zones (`privatelink.database.windows.net`, `privatelink.vaultcore.azure.net`). There is no SQL firewall rule. The API and web apps remain publicly reachable over HTTPS. There is no WAF or Front Door; `config/environments.yml` sets `front_door_enabled: true` for production, but this is **not implemented** in IaC.

## Supply-chain and DevSecOps security

| Control | Status | Evidence |
|---|---|---|
| CodeQL | [IMPLEMENTED]{.badge .ok} | GitHub default setup (no workflow file); gates the Agentic SDLC on the current `main` commit |
| Secret scanning | [IMPLEMENTED]{.badge .ok} | `security.yml` (gitleaks, `fetch-depth: 0`) |
| Dependency scanning | [PARTIAL]{.badge .partial} | `dotnet list package --vulnerable` and `npm audit --audit-level=high` run with `continue-on-error: true` (non-blocking); no Dependabot configuration |
| DAST | [PARTIAL]{.badge .partial} | ZAP baseline is defined in `deploy-staging.yml`, but staging is switched off (`STAGING_ENABLED`), so DAST does not run yet |
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
| Tampering | Modify another user's request | Requests | Own-request filter; role policies; concurrency tokens | Medium: any Manager can decide any routed request (R-05) |
| Tampering | Alter the audit trail | RequestAudits | No write API; audit in the same transaction | Medium: no DB-level immutability; the API identity is SQL admin |
| Repudiation | Deny a decision | RequestAudits | Actor, timestamp, old and new status per transition | Low; decision notes not stored |
| Information disclosure | Read others' requests | Requests | Own-request filter returns 404; read-all limited to Auditor/AppAdmin; SecurityReviewer limited to access requests | Low |
| Information disclosure | DB reachable from outside | Azure SQL | Public access disabled; private endpoint; Entra-only auth | Low |
| Denial of service | Request flooding | API | App Service scale (manual) | Medium: no rate limiting or WAF |
| Elevation of privilege | Role mis-assignment in Entra ID | API | Role-based policies; Auditor write-block | Medium: app-role assignment process not documented |
| Elevation of privilege | Compromise of the API identity | SQL, Key Vault, Graph | Managed identity (no secret to steal) | Medium: identity is SQL admin and will hold Graph application permissions; keep its scope minimal |
| Elevation of privilege | AI agent misuses tools in CI | Repo / runner | Path revert, stripped tokens, human PR review | Medium: `--allow-all-tools`; keep human review mandatory |

Table: Table 18.4 — STRIDE threat model

## Security-control matrix

| Domain | Implemented | Partially implemented | Not detected | Requires validation | Recommended |
|---|---|---|---|---|---|
| Identity | Entra JWT, SPA sign-in, role policies, user-assigned MI, OIDC, SPA pre-authorization | Role mappings *(proposed)* | Conditional Access evidence | Graph application permissions (admin) | CA policies; manager-scoped decisions |
| Data | TLS, KV RBAC, Entra-only SQL, transactional audit | — | CMK, retention | — | Retention policy; audit immutability |
| Network | HTTPS only, private endpoints, VNet integration, public access disabled on data services | — | WAF / Front Door | — | Front Door/WAF for production |
| Application | Validation, headers, CORS for the deployed origin, concurrency tokens | Error handling | Rate limiting, CSP, HSTS | — | Rate limiter, CSP/HSTS |
| DevSecOps | CodeQL, gitleaks, OIDC | Dependency scans (non-blocking), DAST (staging off) | Dependabot, SBOM, signing | Branch protection | Blocking SCA, SHA pinning |

Table: Table 18.5 — Security-control classification

# Identity and Access Management {#identity-and-access-management}

| Identity | Type | Used by | Permissions | Evidence |
|---|---|---|---|---|
| End users | Entra ID accounts with app roles | SPA → API | Six app roles (Table 5.1) | App roles on *SmartServe API (dev)* |
| SPA app registration *SmartServe Web (dev)* | Public client (SPA platform), redirect URIs: DEV web URL and `http://localhost:5173` | MSAL | Delegated `access_as_user`; pre-authorized on the API | `infra/scripts/setup-dev.ps1` |
| API app registration *SmartServe API (dev)* | Resource (`api://<API_CLIENT_ID>`), v2 tokens | JWT validation | Exposes `access_as_user` and six app roles | `setup-dev.ps1`, Bicep `entraClientId` |
| API identity `smartserve-<env>-api-id-<suffix>` | User-assigned managed identity | API app and its `staging` slot | Entra admin of the SQL server; Key Vault Secrets User; Storage Blob Data Contributor; **Graph application permissions to be granted by an admin** | `infra/main.bicep` |
| Deployment identity `id-smartserve-github-dev` | User-assigned managed identity with GitHub OIDC federated credentials (classic and ID-based subjects) | `deploy-dev.yml` | Contributor + Role Based Access Control Administrator on the DEV resource group | `setup-dev.ps1` |
| GitHub tokens | `GITHUB_TOKEN`, `GH_TOKEN`, `COPILOT_GITHUB_TOKEN` | SDLC and utility workflows | Workflow-scoped permissions / PAT scopes (not confirmed) | workflow files |

Table: Table 19.1 — Identities and permissions

The identity flow is shown in Figure 7 (§10). The role-to-action mapping is shown in Figure 3 (§5) and Table 18.1.
