> Extracted from `source/Complete-Application-Solution-Document.md` by `tools/build.mjs`. Edit the chapter files, not this file.

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
