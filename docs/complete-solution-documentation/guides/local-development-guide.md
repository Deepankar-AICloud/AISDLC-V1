> Extracted from `source/Complete-Application-Solution-Document.md` by `tools/build.mjs`. Edit the chapter files, not this file.

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
