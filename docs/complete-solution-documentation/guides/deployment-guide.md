> Extracted from `source/Complete-Application-Solution-Document.md` by `tools/build.mjs`. Edit the chapter files, not this file.

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
