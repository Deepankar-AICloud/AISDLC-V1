> Extracted from `source/Complete-Application-Solution-Document.md` by `tools/build.mjs`. Edit the chapter files, not this file.

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
