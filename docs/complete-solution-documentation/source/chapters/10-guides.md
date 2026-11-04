# Local Development Guide {#local-development-guide}

## Prerequisites

| Software | Version (evidence) |
|---|---|
| .NET SDK | 8.0.x (`net8.0`; CI uses `8.0.x`; verified locally with 8.0.427) |
| Node.js / npm | Node 20 (CI and App Service `NODE 20-lts`) |
| Python | 3.13 for the Agentic SDLC (`agentic-sdlc.yml`); `test.yml` uses 3.11 |
| Git, VS Code | Any current version (no `.vscode/` launch configuration is committed) |
| Optional | Azure CLI and GitHub CLI for deployment and SDLC operations; Copilot CLI for LLM-backed SDLC runs |

Table: Table 27.1 — Developer prerequisites

## Backend

```bash
cd src/backend
dotnet build SmartServe.sln -c Release
dotnet test  SmartServe.sln -c Release          # 16 tests
dotnet run --project SmartServe.Api             # In-Memory DB when no connection string; Swagger at /swagger
```

- **Port:** no `launchSettings.json` is committed, so Kestrel listens on the .NET default `http://localhost:5000`. The Vite proxy targets that address.
- **Database:** with `ConnectionStrings:SmartServeDb` empty (as in `appsettings.Development.json`), the EF In-Memory provider is used and the data is lost on restart.
- **Authentication:** `AzureAd` values in `appsettings.json` are placeholders. To call protected endpoints locally, configure a real API app registration through user secrets or environment variables (`AzureAd__TenantId=<TENANT_ID>`, `AzureAd__ClientId=<API_CLIENT_ID>`, `AzureAd__Audience=<API_APP_ID_URI>`). Swagger UI has no OAuth configuration, so it can only call `/health` without a token.

## Frontend

```bash
cd src/frontend
npm install
cp .env.example .env.local                       # then set the values below (never commit .env.local)
npm run dev                                      # http://localhost:5173, proxies /api and /health to :5000
npm run lint
npm run build
```

| Variable | Purpose | Required | Format |
|---|---|---|---|
| `VITE_API_BASE_URL` | API base URL (empty = same origin / proxy) | No | URL |
| `VITE_ENTRA_CLIENT_ID` | SPA app registration client ID; empty disables auth headers | For auth | GUID (`<SPA_CLIENT_ID>`) |
| `VITE_ENTRA_TENANT_ID` | Tenant (defaults to `common`) | For auth | GUID or `common` (`<TENANT_ID>`) |
| `VITE_API_SCOPE` | API scope (default `api://smartserve-api/access_as_user`) | For auth | `api://<API_APP_ID_URI>/access_as_user` |

Table: Table 27.2 — Frontend environment variables

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
| Every API call returns 401 from the SPA | No signed-in MSAL account (sign-in not implemented) or `VITE_ENTRA_CLIENT_ID` empty | Configure `.env.local`. Interactive sign-in must be added (roadmap 1.2) |
| `POST /api/requests` returns 400 for valid input | Enum string vs number mismatch | Register `JsonStringEnumConverter` (roadmap 1.3) |
| CORS error in the browser | Origin not in `Cors:AllowedOrigins` | Add the origin to configuration |
| Warning "Failed to determine the https port" | No HTTPS URL configured locally | Harmless for local HTTP; or run with an HTTPS profile |
| `npm ci` fails | No `package-lock.json` committed | Use `npm install` (CI falls back automatically) |

Table: Table 27.3 — Local troubleshooting

# Deployment Guide {#deployment-guide}

## One-time platform setup (manual — not automated in the workspace)

1. **Entra ID app registrations:**
    - **API:** expose the scope `access_as_user` and define the six app roles.
    - **SPA:** public client (SPA platform), redirect URIs for the web app URLs, and the API permission.
2. **Deployment identity:** create an Entra app with a **GitHub OIDC federated credential** for this repository. Grant it rights on each resource group (scope **not confirmed**; least privilege recommended).
3. **Resource groups and Key Vault secret:** create the resource groups. Store `sql-admin-password` in the Key Vault referenced by `infra/*.parameters.json`, replacing the `<sub>`, `<rg>`, `<kv>`, `<tenant-id>` and `<api-client-id>` placeholders.
4. **GitHub environments:** create `dev`, `staging` and `production`. Production must have **required reviewers**.
5. **GitHub secrets (names only):**
    - Azure identity: `AZURE_CLIENT_ID`, `AZURE_TENANT_ID`, `AZURE_SUBSCRIPTION_ID`
    - DEV: `AZURE_RESOURCE_GROUP_DEV`, `AZURE_API_APP_DEV`, `AZURE_WEB_APP_DEV`, `AZURE_API_URL_DEV`
    - STAGING: `AZURE_API_APP_STAGING`, `AZURE_API_URL_STAGING`, `AZURE_WEB_URL_STAGING`
    - PRODUCTION: `AZURE_RESOURCE_GROUP_PROD`, `AZURE_API_APP_PROD`, `AZURE_API_URL_PROD`
    - Agentic SDLC: `COPILOT_GITHUB_TOKEN`, and optionally `GH_TOKEN`
6. **SQL access for the API identity** (*required for the current connection string; not in IaC*):
    1. Set an Entra administrator on the SQL server.
    2. In `SmartServeDb`, run `CREATE USER [<api-app-name>] FROM EXTERNAL PROVIDER;` and grant the needed roles.
    3. Do the same for the `staging` slot identity.
7. **Schema:** create and commit an initial EF Core migration (`dotnet ef migrations add Initial`). Without it, `Migrate()` creates no tables.

## Standard release flow

1. Merge to `main`. `deploy-dev.yml` provisions or updates DEV through Bicep, deploys the API and web app, and checks `/health`.
2. On DEV success, `deploy-staging.yml` publishes the API to the `staging` slot, checks `/health`, and runs the ZAP baseline.
3. Run **Deploy — PRODUCTION** manually. Enter `confirm = promote`, and optionally `issue_number` and `sdlc_run_id`.
4. The `production` environment reviewer approves.
5. The workflow validates staging health, swaps the slot, verifies production `/health`, records `DEPLOYED_AND_VERIFIED` or `DEPLOYMENT_FAILED`, and uploads the release evidence pack (90 days).

## Rollback

Swap the slots back:

```bash
az webapp deployment slot swap --resource-group <RG_PROD> --name <API_APP_PROD> --slot staging --target-slot production
```

Then verify `/health` and record the outcome. The frontend has no slot, so redeploy the previous build.

## Known deployment gaps

- The staging and production workflows do not deploy the **web app** and do not run Bicep.
- `VITE_*` values are not supplied in workflow builds.
- `Cors__AllowedOrigins` and `AzureAd__Audience` are not set in app settings.
- The staging-slot identity has no Key Vault role.

See §30 and roadmap phase 1.

# Operational Runbook {#operational-runbook}

::: {.landscape}

| Issue | Symptoms | Possible cause | Validation steps | Resolution | Escalation | Prevention |
|---|---|---|---|---|---|---|
| Application unavailable | Portal or API returns 5xx/timeout; App Service health check failing | Crash at startup (Key Vault, DB), plan outage, bad deployment | `az webapp log tail`; App Insights failures; `curl https://<API_HOST>/health` | Restart; swap back; fix configuration | Platform team → Azure support | Alerts on `/health` and 5xx; staged rollout |
| API failure (500) | Errors in UI; exceptions in App Insights | Unhandled exception, DB error | App Insights *Failures* by operation; correlation ID from audit | Hotfix; roll back | Backend owner | Exception handler, tests |
| Authentication failure | 401 for all users | Wrong `AzureAd` settings, audience mismatch, expired consent, SPA without sign-in | Decode the token (aud, iss, roles) in a safe tool; compare with app settings | Correct the app registration or settings | Identity team | Configuration validation at startup; sign-in UI |
| Authorization failure | 403 for valid users | Missing app-role assignment, wrong stage role | Check the `roles` claim; request status / stage | Assign roles in Entra ID | Identity team / AppAdmin | Documented role-assignment process |
| Database connectivity failure | `/health` Unhealthy; SQL exceptions | MI user missing, firewall, DTU exhaustion, outage | App Insights dependency failures; SQL metrics; `az sql db show` | Create the MI user; scale; fail over | DBA / platform | Provision the MI user in automation; alerts |
| External service failure (Entra / Key Vault) | Startup failure or token validation errors | Service incident, RBAC change | Azure status; Key Vault logs; role assignments | Restore RBAC; retry | Platform / Microsoft support | Diagnostic settings, alerts |
| AI service failure (SDLC only) | Stage comment "generation failed"; QC unavailable | Copilot token expired, model not available | Workflow logs; `COPILOT_GITHUB_TOKEN` validity | Rotate token; `/model select` another model | Platform team | Token expiry monitoring |
| High latency | Slow UI; long request durations | B1 plan, DTU limits, large unpaged lists | App Insights performance; SQL DTU % | Scale up/out; add paging and indexes | Backend / platform | Load tests, autoscale |
| Deployment failure | Workflow red; `DEPLOYMENT_FAILED` | Bicep error, publish error, failed health | Workflow logs; release evidence pack | Fix and rerun; swap back if production | Release manager | Pre-deployment validation (what-if) |
| Configuration failure | Startup exceptions; wrong origins / audience | Missing app settings | `az webapp config appsettings list` (redact values) | Correct the settings in Bicep and redeploy | Platform | Configuration in IaC; startup validation |
| Secret expiration | Key Vault / SQL / token errors; SDLC token failures | Expired PAT or secret | Key Vault expiry dates; token expiry | Rotate; update secret | Security / platform | Expiry alerts; prefer MI / OIDC |
| Storage failure | (No code uses storage today) | — | — | — | — | Implement when attachments are added |
| Rollback | Bad release in production | Defect after swap | Production `/health`, error rates | Slot swap back (§28); redeploy previous web build | Release manager | Smoke tests, canary checks |

Table: Table 29.1 — Operational runbook

:::
