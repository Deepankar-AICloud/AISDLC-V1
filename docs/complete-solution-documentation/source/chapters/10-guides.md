# Local Development Guide {#local-development-guide}

## Prerequisites

| Software | Version (evidence) |
|---|---|
| .NET SDK | 8.0.x (`net8.0`; CI uses `8.0.x`; verified locally with 8.0.427) |
| Node.js / npm | Node 20 or later (CI builds with 20, the DEV pipeline with 22, App Service runs `NODE 22-lts`) |
| Python | 3.13 for the Agentic SDLC (`agentic-sdlc.yml`); `test.yml` uses 3.11 |
| Git, VS Code | Any current version (no `.vscode/` launch configuration is committed) |
| Optional | Azure CLI, GitHub CLI and PowerShell 7.3+ for `setup-dev.ps1` and deployment; Copilot CLI for LLM-backed SDLC runs |

Table: Table 27.1 — Developer prerequisites

## Backend

```bash
cd src/backend
dotnet build SmartServe.sln -c Release
dotnet test  SmartServe.sln -c Release          # 32 test cases
dotnet run --project SmartServe.Api             # Development: In-Memory DB, in-memory directory, Swagger at /swagger
```

- **Port:** no `launchSettings.json` is committed, so Kestrel listens on the .NET default `http://localhost:5000`. The Vite proxy targets that address.
- **Database:** with `ConnectionStrings:SmartServeDb` empty (as in `appsettings.Development.json`), the EF In-Memory provider is used and the data is lost on restart. Outside Development and Testing, an empty connection string stops the app at startup.
- **Directory and e-mail:** in Development the API uses an in-memory directory (demo employee and manager) and an e-mail sender that records *NotSent*, so no Graph access is needed.
- **Authentication:** `AzureAd` values in `appsettings.json` are placeholders. To call protected endpoints locally, configure the API app registration through user secrets or environment variables (`AzureAd__TenantId=<TENANT_ID>`, `AzureAd__ClientId=<API_CLIENT_ID>`). Do not set `AzureAd__Audience` unless tokens use a different audience. Swagger UI has no OAuth configuration, and every endpoint (including `/health`) requires a token.

## Frontend

```bash
cd src/frontend
npm ci
cp .env.example .env.local                       # then set the values below (never commit .env.local)
npm run dev                                      # http://localhost:5173, proxies /api and /health to :5000
npm run lint
npm run build
npx vitest run                                   # 5 tests
```

| Variable | Purpose | Required | Format |
|---|---|---|---|
| `VITE_API_BASE_URL` | API base URL (empty = same origin / proxy) | No | URL |
| `VITE_ENTRA_CLIENT_ID` | SPA app registration client ID; when set, sign-in is required before the app renders | For auth | GUID (`<SPA_CLIENT_ID>`) |
| `VITE_ENTRA_TENANT_ID` | Tenant (defaults to `common`) | For auth | GUID (`<TENANT_ID>`) |
| `VITE_API_SCOPE` | API scope (default `api://smartserve-api/access_as_user`) | For auth | `api://<API_CLIENT_ID>/access_as_user` |

Table: Table 27.2 — Frontend environment variables (set automatically by the DEV pipeline)

## Agentic SDLC (local dry run)

```bash
pip install -r scripts/requirements.txt
python -m scripts.sdlc.run --issue 1 --context "Business problem: … Objective: … Stakeholders: …" --no-llm
```

`--no-llm` exercises the readiness gate, contracts, state machine, QC and reporting without calling a model. State is written to `.sdlc/` and reports to `reports/<run-id>/`; both are git-ignored.

## Debugging in VS Code

No launch or tasks configuration is committed.

- **API:** use the C# Dev Kit *Run and Debug* on `SmartServe.Api.csproj`.
- **SPA:** start `npm run dev` and attach the browser debugger to `http://localhost:5173`.

## Common problems

| Symptom | Cause | Fix |
|---|---|---|
| Every API call returns 401 after signing in | API audience mismatch (for example a leftover `AzureAd:Audience` placeholder) or wrong `AzureAd__ClientId` | Remove the placeholder; the API accepts tokens for its own client ID |
| "Need admin approval" at sign-in | Tenant restricts user consent | Pre-authorize the SPA on the API (`setup-dev.ps1` does this); otherwise ask an admin to grant consent |
| Access request stays *Submitted* | Manager not found, or Graph directory permission missing | Grant the permission; IT admin calls `retry-routing` |
| CORS error in the browser | Origin not in `Cors:AllowedOrigins` | Add the origin to configuration (Bicep sets the deployed web origin) |
| Warning "Failed to determine the https port" | No HTTPS URL configured locally | Harmless for local HTTP; or run with an HTTPS profile |
| `npm ci` fails with 404 | The machine's npm registry configuration cannot resolve a package | Check `npm config get registry` and any `.npmrc`; CI runners use the public registry |

Table: Table 27.3 — Local troubleshooting

# Deployment Guide {#deployment-guide}

## One-time DEV setup

Run once, from the repository root, by a person with Owner on the resource group and permission to create app registrations:

```powershell
az login --tenant <TENANT_ID>
az account set --subscription <SUBSCRIPTION_ID>
gh auth status
pwsh infra/scripts/setup-dev.ps1                 # defaults: -ResourceGroup rg-aisdlc-v1 -Repo <OWNER>/<REPO>
```

The script is idempotent and does only what a pipeline cannot do for itself:

1. Registers the resource providers (Web, Sql, KeyVault, Storage, Network, Insights, OperationalInsights, ManagedIdentity).
2. Creates the deployment identity `id-smartserve-github-dev` with GitHub OIDC federated credentials for the `dev` environment (classic and ID-based subjects), and grants it Contributor and Role Based Access Control Administrator on the resource group.
3. Creates the Entra app registrations *SmartServe API (dev)* (scope `access_as_user`, six app roles, v2 tokens) and *SmartServe Web (dev)* (SPA redirect URIs), pre-authorizes the SPA on the API, and assigns the person running it the Employee role.
4. Writes the GitHub `dev` environment secrets (`AZURE_CLIENT_ID`, `AZURE_TENANT_ID`, `AZURE_SUBSCRIPTION_ID`, `AZURE_RESOURCE_GROUP_DEV`) and variables (`ENTRA_API_CLIENT_ID`, `ENTRA_SPA_CLIENT_ID`).

**Manual step for an Entra administrator (not automated):** grant the API identity (`smartserve-dev-api-id-<suffix>`) the Microsoft Graph application permissions it needs for manager lookup and e-mail (directory read and `Mail.Send`), and set the `graphSenderUserId` parameter to the sending mailbox. Until then, routing and e-mail are recorded as *Failed*.

## Standard release flow

1. Merge to `main`. `deploy-dev.yml` provisions or updates DEV through Bicep, deploys the API and web app with the correct `VITE_*` values, and runs the smoke test.
2. *(When enabled)* On DEV success, `deploy-staging.yml` publishes the API to the `staging` slot, checks `/health`, and runs the ZAP baseline.
3. *(When enabled)* Run **Deploy — PRODUCTION** manually. Enter `confirm = promote`, and optionally `issue_number` and `sdlc_run_id`.
4. The `production` environment reviewer approves.
5. The workflow validates staging health, swaps the slot, verifies production `/health`, records `DEPLOYED_AND_VERIFIED` or `DEPLOYMENT_FAILED`, and uploads the release evidence pack (90 days).

## Rollback

- **DEV:** re-run Deploy — DEV for the previous good commit.
- **Production (once set up):** swap the slots back, then verify and record the outcome.

```bash
az webapp deployment slot swap --resource-group <RG_PROD> --name <API_APP_PROD> --slot staging --target-slot production
```

The frontend has no slot, so redeploy the previous build.

## Known deployment gaps

- Staging and production are not set up: no infrastructure, secrets or `production` environment; `STAGING_ENABLED` is unset.
- The staging and production workflows do not run Bicep, do not deploy the web app, and treat the 401 from `/health` as a failure.
- Graph permissions and the sender mailbox must be granted manually.

See §30 and the roadmap.

# Operational Runbook {#operational-runbook}

::: {.landscape}

| Issue | Symptoms | Possible cause | Validation steps | Resolution | Escalation | Prevention |
|---|---|---|---|---|---|---|
| Application unavailable | Portal or API returns 5xx/timeout | Crash at startup (Key Vault, DB, missing connection string), plan outage, bad deployment | `az webapp log tail`; App Insights failures; `curl https://<API_HOST>/health` (401 = running, 5xx/timeout = down) | Restart; redeploy previous commit; fix configuration | Platform team → Azure support | Alerts on 5xx; staged rollout |
| API failure (500) | Errors in UI; exceptions in App Insights | Unhandled exception, DB error | App Insights *Failures* by operation | Hotfix; roll back | Backend owner | Exception handler, tests |
| Authentication failure | 401 for all users after sign-in | Wrong `AzureAd` settings, audience mismatch, wrong token version | Decode the token (aud, iss, roles) in a safe tool; compare with `AzureAd__ClientId` | Correct the app registration or settings | Identity team | Configuration validation at startup |
| Consent blocked | "Need admin approval" at sign-in | Tenant restricts user consent | Check pre-authorization on the API app registration | Pre-authorize the SPA; or admin consent | Identity team | Keep pre-authorization in `setup-dev.ps1` |
| Authorization failure | 403 for valid users | Missing app-role assignment; Auditor role blocks writes | Check the `roles` claim | Assign roles in Entra ID | Identity team / AppAdmin | Documented role-assignment process |
| Database connectivity failure | `/health` 503; SQL exceptions | Private endpoint or DNS misconfigured, identity not SQL admin, DTU exhaustion, outage | App Insights dependency failures; resolve the SQL host name from the app (Kudu console) to a private IP; SQL metrics | Fix DNS zone link or endpoint; scale; fail over | DBA / platform | Keep networking in Bicep; alerts |
| Graph failure | Access requests stay *Submitted*; notifications *Failed* | Graph permissions missing, sender not set, Graph outage | `NotificationRecords` reasons; App Insights dependency calls to `graph.microsoft.com` | Grant permissions / set sender; IT admin `retry-routing` | Identity team | Alert on *Failed* notifications |
| External service failure (Entra / Key Vault) | Startup failure or token validation errors | Service incident, RBAC change, private endpoint issue | Azure status; Key Vault logs; role assignments | Restore RBAC; retry | Platform / Microsoft support | Diagnostic settings, alerts |
| AI service failure (SDLC only) | Stage comment "generation failed"; QC unavailable | Copilot token expired, model not available | Workflow logs; `COPILOT_GITHUB_TOKEN` validity | Rotate token; `/model select` another model | Platform team | Token expiry monitoring |
| High latency | Slow UI; long request durations | B1 plan, DTU limits, large unpaged lists | App Insights performance; SQL DTU % | Scale up/out; add paging and indexes | Backend / platform | Load tests, autoscale |
| Deployment failure | Workflow red; `DEPLOYMENT_FAILED` | Azure login (OIDC subject mismatch), unregistered resource provider, policy denial, Bicep error, failed smoke test | Workflow logs; `az deployment operation group list` | Fix and re-run; swap back if production | Release manager | Pre-deployment validation (what-if) |
| Configuration failure | Startup exceptions; wrong origins / audience | Missing or placeholder settings | `az webapp config appsettings list` (redact values) | Correct the settings in Bicep or `appsettings.json` and redeploy | Platform | Configuration in IaC; startup validation |
| Secret expiration | Key Vault / SQL / token errors; SDLC token failures | Expired PAT or secret | Key Vault expiry dates; token expiry | Rotate; update secret | Security / platform | Expiry alerts; prefer MI / OIDC |
| Storage failure | (No code uses storage today) | — | — | — | — | Implement when attachments are added |
| Rollback | Bad release in production | Defect after swap | Production `/health`, error rates | Slot swap back (§28); redeploy previous web build | Release manager | Smoke tests, canary checks |

Table: Table 29.1 — Operational runbook

:::
