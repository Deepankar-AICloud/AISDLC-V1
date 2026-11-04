# Technology Stack {#technology-stack}

| Layer | Technology (version) | Evidence |
|---|---|---|
| Frontend runtime | React 18.3, React DOM 18.3, TypeScript 5.6 (strict) | `src/frontend/package.json`, `tsconfig.json` |
| Frontend build/dev | Vite 5.4 (`@vitejs/plugin-react` 4.3), ESLint 8.57 + typescript-eslint 8.8, Vitest 2.1 | `package.json`, `vite.config.ts`, `.eslintrc.cjs` |
| Frontend identity | `@azure/msal-browser` 3.26, `@azure/msal-react` 2.2 (public client, PKCE) | `src/frontend/src/auth.ts` |
| Backend | .NET 8 (`net8.0`), ASP.NET Core Web API, nullable enabled | `SmartServe.Api.csproj` |
| Identity (API) | Microsoft.Identity.Web 3.8.2 (JWT bearer) | `SmartServe.Api.csproj`, `Program.cs` |
| Data access | EF Core 8.0.8 (SqlServer, InMemory), EF Core health check | `SmartServe.Api.csproj`, `Data/SmartServeDbContext.cs` |
| Secrets | Azure.Identity 1.12.1, Azure.Extensions.AspNetCore.Configuration.Secrets 1.3.2 | `Program.cs` |
| Telemetry | Microsoft.ApplicationInsights.AspNetCore 2.22.0 | `Program.cs` |
| API docs | Swashbuckle.AspNetCore 6.7.3 (Development only) | `Program.cs` |
| Tests | xUnit 2.9.2, Microsoft.AspNetCore.Mvc.Testing 8.0.8, coverlet 6.0.2 | `SmartServe.Tests.csproj` |
| Database | Azure SQL Database (`SmartServeDb`); EF In-Memory locally | `infra/main.bicep`, `Program.cs` |
| Hosting | Azure App Service on Linux: runtime `DOTNETCORE 8.0` (API + `staging` slot) and `NODE 20-lts` (web) | `infra/main.bicep` |
| IaC | Bicep (resource-group scope) + per-environment parameter files | `infra/` |
| CI/CD | GitHub Actions; OIDC to Azure (`azure/login@v2`), `azure/arm-deploy@v2`, `azure/webapps-deploy@v3` | `.github/workflows/` |
| Security tooling | CodeQL (GitHub default setup), gitleaks, OWASP ZAP baseline 0.12.0, `dotnet list package --vulnerable`, `npm audit` | `security.yml`, `deploy-staging.yml`, `ci.yml` |
| Agentic SDLC | Python 3.13 (PyYAML), GitHub Copilot CLI, Pandoc-free Markdown artifacts | `scripts/sdlc`, `scripts/requirements.txt`, `agentic-sdlc.yml` |
| AI models (configured) | gpt-5-mini, claude-haiku-4.5, gpt-5.5, claude-sonnet-4.6, claude-sonnet-5; fallback `auto` | `config/models.yml` |
| Package managers | NuGet, npm, pip | project files |
| Licence | MIT | `LICENSE` |

Table: Table 8.1 — Technology stack

**Not used / not detected:** containers for SmartServe (no Dockerfile), Kubernetes/Helm, message queues/event buses, caching (Redis), Azure OpenAI/Foundry in the application runtime, Terraform/ARM, Azure DevOps pipelines.

# Workspace and Repository Structure {#workspace-structure}

| Path | Content | Owner (CODEOWNERS, placeholder teams) |
|---|---|---|
| `src/backend/SmartServe.Api/` | Web API: `Program.cs`, `Controllers/`, `Domain/`, `Dtos/`, `Data/`, `Services/`, `appsettings*.json` | `@smartserve/backend` |
| `src/backend/SmartServe.Tests/` | xUnit unit and integration tests | `@smartserve/backend` |
| `src/backend/*.log` | Committed build/test logs (stale: test log shows 14 tests, the current suite has 16) | — |
| `src/frontend/` | Vite React SPA: `index.html`, `src/main.tsx`, `App.tsx`, `api.ts`, `auth.ts`, `.env.example` | `@smartserve/frontend` |
| `infra/` | `main.bicep`, `dev.parameters.json`, `staging.parameters.json`, `production.parameters.json` | `@smartserve/platform @smartserve/security` |
| `.github/workflows/` | 19 workflow files (app CI/CD, Agentic SDLC, legacy/auxiliary) | `@smartserve/platform` |
| `.github/agents/` | 18 agent definition files (`*.agent.md`) | `@smartserve/architects` |
| `.github/skills/` | Copilot skills (6 files) | — |
| `scripts/sdlc/` | Orchestrator, model router, QC, readiness, contracts, budget, telemetry, traceability, impact, reporting, CLIs | `@smartserve/platform` |
| `config/` | `agents.yml`, `models.yml`, `model-routing.yml`, `quality-gates.yml`, `readiness.yml`, `budgets.yml`, `pricing.yml`, `environments.yml`, `impact-rules.yml`, `contracts/*.yml` | `@smartserve/platform` |
| `docs/` | Generated SDLC artifacts per stage (BRD/PRD/EPIC/ARCH/NFR/TASK) and this documentation set | `@smartserve/architects` |
| `README.md`, `step-by-step.md` | Overview and Agentic SDLC operating guide | — |

Table: Table 9.1 — Repository structure

The repository has 152 tracked files at commit `605e414`. The full inventory is in `analysis/file-inspection-log.md`, and component-to-code mappings are in `analysis/source-code-mapping.md`.
