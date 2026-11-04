# Deployment Architecture {#deployment-architecture}

## Azure resources

![Figure 24 — Azure deployment architecture per environment (`infra/main.bicep`)](diagrams/rendered/19-azure-deployment.png)

| Resource | Type / API version | Naming | Key settings | Dev / Staging | Production |
|---|---|---|---|---|---|
| Log Analytics | `Microsoft.OperationalInsights/workspaces@2023-09-01` | `smartserve-<env>-law-<suffix>` | PerGB2018 | 30-day retention | 90-day retention |
| Application Insights | `Microsoft.Insights/components@2020-02-02` | `…-ai-…` | Workspace-based | ✔ | ✔ |
| Key Vault | `Microsoft.KeyVault/vaults@2023-07-01` | `smartserve<env>kv<suffix>` (≤24) | Standard, RBAC, soft delete (purge protection **not set**) | ✔ | ✔ |
| SQL server | `Microsoft.Sql/servers@2023-08-01-preview` | `…-sql-…` | SQL admin login + secure password, TLS 1.2, public access Enabled | ✔ | ✔ |
| SQL database | `…/databases` | `SmartServeDb` | — | Basic | S1 Standard, zone-redundant |
| SQL firewall | `…/firewallRules` | `AllowAzureServices` | 0.0.0.0–0.0.0.0 | ✔ | ✔ |
| Storage account | `Microsoft.Storage/storageAccounts@2023-05-01` | `smartserve<env>st<suffix>` | StorageV2, TLS 1.2, HTTPS only, no public blob | Standard_LRS | Standard_ZRS |
| App Service plan | `Microsoft.Web/serverfarms@2023-12-01` | `…-plan-…` | Linux, capacity 1 | B1 | P1v3 |
| API app | `Microsoft.Web/sites@2023-12-01` | `…-api-…` | .NET 8, httpsOnly, FTPS disabled, TLS 1.2, health `/health`, system MI, app settings | ✔ | ✔ |
| API `staging` slot | `Microsoft.Web/sites/slots` | `staging` | Same runtime and settings, own MI (FTPS state not set) | ✔ | ✔ |
| Web app | `Microsoft.Web/sites@2023-12-01` | `…-web-…` | Node 20 LTS, httpsOnly, TLS 1.2; **no app settings, no MI** | ✔ | ✔ |
| Role assignments | `Microsoft.Authorization/roleAssignments@2022-04-01` | GUID | API MI → Key Vault Secrets User; API MI → Storage Blob Data Contributor | ✔ | ✔ |

Table: Table 20.1 — Azure resources provisioned by Bicep

Outputs: `apiAppName`, `webAppName`, `apiUrl`, `webUrl`, `appInsightsConnectionString`. App settings injected into the API and its slot:

- `ApplicationInsights__ConnectionString`
- `AzureAd__TenantId`, `AzureAd__ClientId`, `AzureAd__Instance`
- `KeyVault__Uri`
- `ConnectionStrings__SmartServeDb` (managed-identity authentication, no password)

`AzureAd__Audience` and `Cors__AllowedOrigins` are **not** set.

## Network view

![Figure 25 — Network architecture (public endpoints; private networking recommended)](diagrams/rendered/20-network-architecture.png)

## Environment views

![Figure 26 — Environment topology and which environments are confirmed](diagrams/rendered/30-environment-topology.png)

| Environment | Confirmed? | How it is created / updated | Notes |
|---|---|---|---|
| Local | Confirmed | `dotnet run`, `npm run dev` | In-Memory DB, Swagger, Vite proxy |
| Development | Confirmed | `deploy-dev.yml` (Bicep with `dev.parameters.json` + API + web) | GitHub environment `dev` |
| Test | **Not defined** | — | No workflow or parameter file |
| Staging | Confirmed | `deploy-staging.yml` deploys the API to the `staging` slot only | Does **not** run Bicep; `staging.parameters.json` is unused by any workflow; web app not deployed |
| Production | Confirmed | `deploy-production.yml` swaps the API `staging` slot into production | Does **not** run Bicep or deploy the web app; `production.parameters.json` unused by workflows |

Table: Table 20.2 — Environments

> Promotion uses the `staging` **slot of the target environment's API app**. The secrets `AZURE_API_APP_STAGING` and `AZURE_API_APP_PROD` (and their resource groups) determine whether staging and production are separate apps or the same app. This is **not confirmed from the current workspace** (§34).

## Production runtime

![Figure 27 — Production runtime view and slot-swap rollback path](diagrams/rendered/23-production-runtime.png)

## Scaling, availability, backup and rollback

- **Scaling:** a single instance (`capacity: 1`). No autoscale rules are defined; scale-out is manual (§25).
- **Availability:** production uses zone-redundant SQL (S1) and ZRS storage. The App Service plan is not zone-redundant; no SLA target is defined.
- **Backup:** Azure SQL platform backups (defaults); no LTR or geo-restore configuration (§26).
- **Rollback:** swap the `staging` slot back into production (manual, §28). No automatic rollback.

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
| Deploy DEV (`deploy-dev.yml`) | Push to `main` on `src/**`, `infra/**` | Commit | OIDC login, `arm-deploy` (Bicep), `dotnet publish`, `webapps-deploy` API and web, `curl /health` | Deployed DEV | Smoke `/health` (5 retries) | OIDC, no stored cloud secrets | `dev` | None | Job fails, no rollback | Redeploy previous commit |
| Deploy STAGING (`deploy-staging.yml`) | DEV success or manual | Commit | OIDC, `dotnet publish`, deploy to `staging` slot, `curl /health`; ZAP baseline | Staging slot build, ZAP report | Smoke + ZAP (`fail_action: true`) | DAST | `staging` | Environment rules (**not confirmed**) | Job fails | Redeploy |
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
- **`[skip ci]` and `chore(sdlc):` conventions.** Commits prefixed `chore(sdlc):` with `[skip ci]` prevent loops; the CodeQL gate skips intake for them.
- **Release.** DEV deploys automatically on merge. STAGING follows after DEV succeeds. PRODUCTION is a deliberate manual promotion with environment reviewers, and `release_evidence.py` produces an evidence pack.
- **Not confirmed from the current workspace:** branch-protection rules, required reviewers, signed commits, artifact signing/SBOM and environment protection rules for `staging`.

# Testing Strategy {#testing-strategy}

## Existing tests

| Test | Type | Verifies | Location |
|---|---|---|---|
| `Health_endpoint_is_anonymous_and_healthy` | Integration (`WebApplicationFactory`, In-Memory DB) | `GET /health` → 200 without a token | `ApiIntegrationTests.cs` |
| `Requests_endpoint_requires_authentication` | Integration | `GET /api/requests` → 401 without a token | `ApiIntegrationTests.cs` |
| `RequiresSecurityReview_flags_sensitive_categories` (×6) | Unit (theory) | Production/Database/Azure/VPN → true; Laptop/General → false | `WorkflowServiceTests.cs` |
| `Manager_approval_routes_to_security_when_sensitive` | Unit | Manager approve + sensitive → `SecurityApproval` | `WorkflowServiceTests.cs` |
| `Manager_approval_skips_security_when_not_sensitive` | Unit | → `ItProcessing` | `WorkflowServiceTests.cs` |
| `Rejection_at_any_stage_sets_rejected` | Unit | reject → `Rejected` | `WorkflowServiceTests.cs` |
| `It_processing_leads_to_provisioned` | Unit | IT approve → `Provisioned` | `WorkflowServiceTests.cs` |
| `CurrentStage_reflects_status` (×4) | Unit (theory) | Status → stage mapping | `WorkflowServiceTests.cs` |

Table: Table 22.1 — Test inventory (16 test cases)

**Execution evidence:** `dotnet test SmartServe.sln -c Release` was run during this analysis on .NET SDK 8.0.427. Result: **Passed 16, Failed 0, Skipped 0** (about 1 s). The committed `src/backend/test-release.log` (14 tests) is stale.

**Coverage:** coverlet collects coverage in CI. The `COVERAGE_THRESHOLD: 80` environment variable in `ci.yml` is **not enforced**, and `coverage_min: 50` in `quality-gates.yml` is not implemented.

**Frontend:** Vitest is configured but there are no test files. The CI step is non-blocking (`|| echo "no tests yet"`).

**Security tests:** ZAP baseline (staging); there are no authorization integration tests per role.

**Performance tests:** none. The `performance.agent.md` component exists, but no load tests or targets are defined.

**AI evaluation tests:** QC gates and the `--no-llm` deterministic smoke run in `test.yml`.

## Requirements traceability (tests)

| Requirement | Covered by | Gap |
|---|---|---|
| BRD-REQ-002 workflow routing | WorkflowService unit tests | Controller-level decision tests (self-approval, stage roles) |
| NFR-001 / NFR-002 authentication and authorization | `Requests_endpoint_requires_authentication` | Per-role and per-endpoint tests; `/health` contradicts NFR-001 |
| NFR-005 audit | none | Audit row per transition with old/new status |
| PRD-FR-001 submission | none | API + UI contract test (enum strings) |
| BRD-REQ-004 notifications | n/a (not implemented) | — |

Table: Table 22.2 — Test traceability and gaps

## Recommended test plan

1. **API integration tests** with a test authentication handler. Cover every endpoint × role matrix (Table 18.1), self-approval, stage mismatch, ownership, 404/400 paths, and the audit row per action.
2. **Contract tests:** JSON enum string round-trip; `RequestResponse` shape shared with `api.ts`.
3. **Persistence tests** against SQL Server (container or Azure SQL dev), including migrations.
4. **Frontend tests** (Vitest + Testing Library): form validation, error alert, auth header injection, list rendering.
5. **End-to-end tests** (Playwright) for sign-in → submit → approve → confirm in DEV.
6. **Performance tests** once targets are defined (§34).
7. **Make CI gates blocking:** coverage threshold, frontend tests, `npm audit` and the vulnerable-package scan.
