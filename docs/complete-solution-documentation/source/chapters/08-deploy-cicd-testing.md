# Deployment Architecture {#deployment-architecture}

## Azure resources

![Figure 24 — Azure deployment architecture per environment (`infra/main.bicep`)](diagrams/rendered/19-azure-deployment.png)

| Resource | Type / API version | Naming | Key settings | DEV (B1) | Staging / Production |
|---|---|---|---|---|---|
| API identity | `Microsoft.ManagedIdentity/userAssignedIdentities@2023-01-31` | `smartserve-<env>-api-id-<suffix>` | Shared by the API app and its slot | ✔ | ✔ |
| Log Analytics | `Microsoft.OperationalInsights/workspaces@2023-09-01` | `…-law-…` | PerGB2018 | 30-day retention | 30 / 90 days |
| Application Insights | `Microsoft.Insights/components@2020-02-02` | `…-ai-…` | Workspace-based | ✔ | ✔ |
| Key Vault | `Microsoft.KeyVault/vaults@2023-07-01` | `smartserve<env>kv<suffix>` (≤24) | Standard, RBAC, soft delete, **public access disabled**, network ACL deny (purge protection **not set**) | ✔ | ✔ |
| SQL server | `Microsoft.Sql/servers@2023-08-01-preview` | `…-sql-…` | **Entra-only auth**, admin = API identity, TLS 1.2, **public access disabled** | ✔ | ✔ |
| SQL database | `…/databases` | `SmartServeDb` | — | Basic | Basic / S1 zone-redundant |
| Storage account | `Microsoft.Storage/storageAccounts@2023-05-01` | `smartserve<env>st<suffix>` | StorageV2, TLS 1.2, HTTPS only, no public blob, **public access disabled, shared keys disabled** | Standard_LRS | LRS / ZRS |
| Virtual network | `Microsoft.Network/virtualNetworks@2023-11-01` | `…-vnet-…` | `10.40.0.0/16`; subnet `app` (delegated to App Service), subnet `private-endpoints` | ✔ | ✔ |
| Private endpoints | `Microsoft.Network/privateEndpoints@2023-11-01` | `…-sql-pe-…`, `…-kv-pe-…` | SQL (`sqlServer`), Key Vault (`vault`) | ✔ | ✔ |
| Private DNS zones | `Microsoft.Network/privateDnsZones@2020-06-01` | `privatelink.database.windows.net`, `privatelink.vaultcore.azure.net` | Linked to the VNet; zone groups on each endpoint | ✔ | ✔ |
| App Service plan | `Microsoft.Web/serverfarms@2023-12-01` | `…-plan-…` | Linux, capacity 1 | B1 (no slot support) | S1 / P1v3 |
| API app | `Microsoft.Web/sites@2023-12-01` | `…-api-…` | .NET 8, httpsOnly, FTPS disabled, TLS 1.2, health `/health`, user-assigned identity, **VNet integration with route-all** | ✔ | ✔ |
| API `staging` slot | `Microsoft.Web/sites/slots` | `staging` | Same runtime, settings, identity and VNet | **not created** | ✔ |
| Web app | `Microsoft.Web/sites@2023-12-01` | `…-web-…` | Node 22 LTS, `pm2 serve /home/site/wwwroot --no-daemon --spa`, httpsOnly, FTPS disabled, TLS 1.2 | ✔ | ✔ |
| Role assignments | `Microsoft.Authorization/roleAssignments@2022-04-01` | GUID | API identity → Key Vault Secrets User; API identity → Storage Blob Data Contributor | ✔ | ✔ |

Table: Table 20.1 — Azure resources provisioned by Bicep

Outputs: `apiAppName`, `webAppName`, `apiUrl`, `webUrl`, `appInsightsConnectionString`. The DEV workflow reads the app names and URLs from these outputs, so no per-app secrets are needed. App settings injected into the API (and its slot):

- `ApplicationInsights__ConnectionString`
- `AzureAd__TenantId`, `AzureAd__ClientId`, `AzureAd__Instance`
- `KeyVault__Uri`
- `ConnectionStrings__SmartServeDb` (managed-identity authentication with the identity's client ID, no password)
- `AZURE_CLIENT_ID` (selects the user-assigned identity for `DefaultAzureCredential`)
- `Cors__AllowedOrigins__0` (the deployed web origin)
- `Graph__SenderUserId` (empty unless the `graphSenderUserId` parameter is set)

**DEV as deployed (resource group `rg-aisdlc-v1`, West US 3):** web `https://smartserve-dev-web-<suffix>.azurewebsites.net`, API `https://smartserve-dev-api-<suffix>.azurewebsites.net`. An unrelated, pre-existing web app (`aisdlc-v1`, Node, F1) in the same resource group is not used by SmartServe.

## Network view

![Figure 25 — Network architecture: VNet integration and private endpoints](diagrams/rendered/20-network-architecture.png)

## Environment views

![Figure 26 — Environment topology and which environments are confirmed](diagrams/rendered/30-environment-topology.png)

| Environment | Confirmed? | How it is created / updated | Notes |
|---|---|---|---|
| Local | Confirmed | `dotnet run`, `npm run dev` | In-Memory DB, in-memory directory, unconfigured e-mail, Swagger, Vite proxy |
| Development | **Deployed** | One-time `infra/scripts/setup-dev.ps1`, then `deploy-dev.yml` on every push to `main` touching `src/**` or `infra/**` (Bicep + API + web + smoke test) | GitHub environment `dev`; Azure resource group `rg-aisdlc-v1` |
| Test | **Not defined** | — | No workflow or parameter file |
| Staging | **Not set up** | `deploy-staging.yml` exists but is skipped until the repository variable `STAGING_ENABLED` is `true` | No infrastructure, secrets or Bicep step yet; design undecided (§34) |
| Production | **Not set up** | `deploy-production.yml` swaps the API `staging` slot into production after mandatory approval | GitHub environment `production` does not exist yet; no Bicep step |

Table: Table 20.2 — Environments

> The production workflow swaps the `staging` **slot of the production API app**, so staging is designed as a slot of production, not a separate app. Setting it up means creating the production infrastructure, choosing its size and resource group, and naming the production approver (§34).

## Production runtime

![Figure 27 — Production runtime view and slot-swap rollback path](diagrams/rendered/23-production-runtime.png)

## Scaling, availability, backup and rollback

- **Scaling:** a single instance (`capacity: 1`). No autoscale rules are defined; scale-out is manual (§25).
- **Availability:** production is designed with zone-redundant SQL (S1) and ZRS storage. The App Service plan is not zone-redundant; no SLA target is defined.
- **Health check:** App Service probes `/health`, which requires a token and therefore answers 401 to the platform probe. With one instance this does not remove the app from rotation, but the platform may treat the instance as unhealthy; see §34 Q4.
- **Backup:** Azure SQL platform backups (defaults); no LTR or geo-restore configuration (§26).
- **Rollback:** swap the `staging` slot back into production (manual, §28). In DEV, redeploy the previous commit. No automatic rollback.

# DevSecOps and CI/CD {#devsecops-cicd}

![Figure 28 — SmartServe CI/CD pipeline from pull request to production](diagrams/rendered/21-cicd-pipeline.png)

## Pipeline stages

::: {.landscape}

| Stage | Trigger | Inputs | Commands / actions | Outputs | Quality gate | Security control | Environment | Approval | Failure handling | Rollback |
|---|---|---|---|---|---|---|---|---|---|---|
| CI backend (`ci.yml`) | PR to `main` on `src/**`, `tests/**` | Source | `dotnet restore/build -c Release`, `dotnet test --collect "XPlat Code Coverage"` | trx, coverage files (not uploaded) | Build + tests must pass | `dotnet list package --vulnerable` (non-blocking) | — | PR review | Job fails | n/a |
| CI frontend (`ci.yml`) | same | Source | `npm ci` (falls back to `npm install`), `npm run lint`, `npm run build`, tests (failures ignored via an echo fallback) | dist (not uploaded) | Lint + build | `npm audit --audit-level=high` (non-blocking) | — | PR review | Job fails | n/a |
| Secret scan (`security.yml`) | PR, push to main, weekly, manual | Full history | gitleaks | Findings | Fails on secrets | Secret detection | — | — | Job fails | n/a |
| CodeQL | GitHub default setup | Source | CodeQL analysis | Alerts | Gates Agentic SDLC stages | SAST | — | — | Alerts | n/a |
| Deploy DEV (`deploy-dev.yml`) | Push to `main` on `src/**`, `infra/**`, the workflow; manual | Commit | OIDC login; `arm-deploy` (Bicep, deployment `smartserve-dev`, Entra IDs from environment secrets/variables); `dotnet publish` of the API project; `webapps-deploy` API; `npm run build` with `VITE_*` from Bicep outputs and variables; `webapps-deploy` web; smoke test | Deployed DEV | API `/health` returns 401 or 200 (up to 30 × 20 s), web root reachable | OIDC, no stored cloud secrets | `dev` | None | Job fails, no rollback | Redeploy previous commit |
| Deploy STAGING (`deploy-staging.yml`) | DEV success or manual, **only when `STAGING_ENABLED == 'true'`** | Commit | OIDC, `dotnet publish`, deploy to `staging` slot, `curl /health`; ZAP baseline | Staging slot build, ZAP report | Smoke + ZAP (`fail_action: true`) | DAST | `staging` | Environment rules (**not confirmed**) | Skipped today | Redeploy |
| Deploy PRODUCTION (`deploy-production.yml`) | Manual, `confirm == 'promote'` | Staging slot | Staging health → `az webapp deployment slot swap` → prod `/health` → `deployment_status` → `release_evidence` | Swapped prod, evidence pack (90 days) | Pre- and post-swap health | Mandatory environment reviewers, OIDC | `production` | **Mandatory** | `DEPLOYMENT_FAILED`, job fails | Manual swap back |

Table: Table 21.1 — SmartServe pipeline stages

:::

## Agentic SDLC and auxiliary workflows

| Workflow | Purpose | Trigger | Notable permissions |
|---|---|---|---|
| `agentic-sdlc-codeql-gate.yml` | Waits for CodeQL; dispatches or resumes SDLC issues; creates intake issue for new commits | issues labelled/edited, `issue_comment`, `workflow_run` (CodeQL) | `actions: write`, `issues: write` |
| `agentic-sdlc.yml` | Runs one orchestrator stage; opens stage PR; posts gate comments | `workflow_dispatch` (issue, state run ID) | `contents/issues/pull-requests: write`, `actions: read` |
| `artifact-review.yml` | On PR approval: approve state, merge, dispatch next stage | `pull_request_review`, manual | `contents/pull-requests/issues/actions: write` |
| `feedback-handler.yml` | `/agent` and `/model` commands | `issue_comment` | write permissions (see §18.9) |
| `test.yml` | Python compile + deterministic `--no-llm` smoke run | `scripts/**` changes | `contents: read` (uses Python 3.11; runtime uses 3.13) |
| `deploy.yml`, `automate_pr.yml`, `gatekeeper.yml`, `council-query.yml`, `feature-requirement-analysis.yml`, `cast-*.yml`, `azure-resource-analysis.yml`, `daily-repo-status.lock.yml` | Legacy Ticket Tracker auto-heal and auxiliary AI analysis | various | `deploy.yml` / `azure-resource-analysis.yml` use `AZURE_CREDENTIALS` (service-principal JSON) rather than OIDC |

Table: Table 21.2 — Other workflows

## Branching, PR and release process

- **Trunk-based on `main`.** Application PRs run CI and secret scanning. SDLC artifacts arrive through `sdlc/issue-<n>/<agent>` branches and PRs labelled `sdlc:review`.
- **`[skip ci]` and `chore(sdlc):` conventions.** Document-stage commits are prefixed `chore(sdlc):` with `[skip ci]` to prevent loops; the CodeQL gate skips intake for them. Code-stage commits omit `[skip ci]` so that CI and the DEV deployment run after the merge.
- **Release.** DEV deploys automatically on every relevant push. STAGING follows a successful DEV run once enabled. PRODUCTION is a deliberate manual promotion with environment reviewers, and `release_evidence.py` produces an evidence pack.
- **Known staging/production gaps (to address when they are set up):** the staging and production workflows do not run Bicep or deploy the web app, and their health checks use `curl --fail` on `/health`, which now always returns 401 without a token.
- **Not confirmed from the current workspace:** branch-protection rules, required reviewers, signed commits, artifact signing/SBOM and environment protection rules for `staging`.

# Testing Strategy {#testing-strategy}

## Existing tests

| Test file | Tests | Type | Verifies |
|---|---|---|---|
| `ApiIntegrationTests.cs` | 1 | Integration (`WebApplicationFactory`, In-Memory DB) | `GET /api/requests` → 401 without a token |
| `EndpointAuthorizationTests.cs` | 1 (data-driven over every endpoint) | Integration | Each endpoint returns 401 without a token, 403 with the wrong role, and succeeds with the right role |
| `EnumJsonSerializationTests.cs` | 1 | Contract | Enums serialise as strings in API responses |
| `RoleScopeTests.cs` | 4 (one theory) | Integration | Auditor read-all with paged history; Auditor writes blocked even with another role; SecurityReviewer sees access requests only and cannot decide |
| `WorkflowAuditTests.cs` | 17 | Workflow / integration | One audit record per transition with all fields; status committed before each notification; unresolved manager and retry routing; directory outages recorded as *Failed*; invalid e-mail as *NotSent*; reconciliation of stale sends; concurrent decisions produce exactly one transition; cancellation handling |
| `RelationalAtomicityTests.cs` | 2 | Relational (SQLite) | A losing concurrent decision rolls back its audit row with its status change; a failed notification finalize is reported as *Failed* |
| `App.test.tsx` | 1 | Frontend (Vitest) | Navigation to the request-type admin page and back |
| `apiFixture.test.ts` | 2 | Frontend contract | The backend-shaped `PortalRequest` payload parses; malformed shapes are rejected |
| `AdminRequestTypesPage.test.tsx` | 2 | Frontend | Listing and creating request types; deactivation without reactivation |

Table: Table 22.1 — Test inventory (26 backend test methods = 32 test cases; 5 frontend tests)

**Execution evidence:** `dotnet test SmartServe.sln -c Release` was run during this update on .NET SDK 8. Result: **Passed 32, Failed 0, Skipped 0** (about 1 s). The DEV deployment pipeline also passed its smoke test (API `/health` → 401 with the app started, web root → 200). The committed `src/backend/test-release.log` is stale.

**Coverage:** coverlet collects coverage in CI. The `COVERAGE_THRESHOLD: 80` environment variable in `ci.yml` is **not enforced**, and `coverage_min: 50` in `quality-gates.yml` is not implemented.

**Frontend:** 5 Vitest tests exist, but the CI step is still non-blocking (`|| echo "no tests yet"`).

**Security tests:** authorization tests per endpoint and role (above); ZAP baseline defined for staging but not running while staging is off.

**Performance tests:** none. The `performance.agent.md` component exists, but no load tests or targets are defined.

**AI evaluation tests:** QC gates and the `--no-llm` deterministic smoke run in `test.yml`.

## Requirements traceability (tests)

| Requirement | Covered by | Gap |
|---|---|---|
| BRD-REQ-002 workflow | `WorkflowAuditTests` (lifecycle, rejection, retry routing, concurrency) | Decision restricted to the routed manager (not implemented) |
| NFR-001 / NFR-002 authentication and authorization | `EndpointAuthorizationTests`, `RoleScopeTests`, `ApiIntegrationTests` | — |
| NFR-005 audit | `WorkflowAuditTests`, `RelationalAtomicityTests` | Persistence tests against SQL Server itself |
| PRD-FR-001 submission | `EnumJsonSerializationTests`, `apiFixture.test.ts` | End-to-end UI test |
| BRD-REQ-004 notifications | `WorkflowAuditTests` (outcomes, ordering, reconciliation) | Real Graph delivery in an environment |
| TASK-012 request types | `AdminRequestTypesPage.test.tsx` | API tests for request-type validation |

Table: Table 22.2 — Test traceability and gaps

## Recommended test plan

1. **Persistence tests** against SQL Server (container or the DEV database), including the committed migration.
2. **Frontend tests** for the request form, the error alert and the sign-in gate.
3. **End-to-end tests** (Playwright) in DEV: sign-in → submit → manager decision → fulfilment, once Graph permissions are granted and approver screens exist.
4. **Performance tests** once targets are defined (§34).
5. **Make CI gates blocking:** coverage threshold, frontend tests, `npm audit` and the vulnerable-package scan.
