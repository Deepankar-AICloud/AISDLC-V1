# References

## Workspace sources (primary)

| Area | Paths |
|---|---|
| Application | `src/backend/SmartServe.Api/**`, `src/backend/SmartServe.Tests/**`, `src/frontend/**` |
| Infrastructure | `infra/main.bicep`, `infra/*.parameters.json` |
| CI/CD and automation | `.github/workflows/*.yml`, `.github/CODEOWNERS` |
| Agentic SDLC | `scripts/sdlc/**`, `config/**`, `.github/agents/*.agent.md` |
| Requirements and design (issue #23) | `docs/brd/BRD-23.md`, `docs/prd/PRD-23.md`, `docs/epic/EPIC-23.md`, `docs/architecture/ARCH-23.md`, `docs/nfr/NFR-23.md`, `docs/tasks/TASK-23.md` |
| Overview | `README.md`, `step-by-step.md`, `docs/README.md` |

## External references (product documentation)

| Topic | Reference |
|---|---|
| Microsoft Identity Web (protected web API) | https://learn.microsoft.com/entra/identity-platform/scenario-protected-web-api-overview |
| MSAL.js for single-page applications | https://learn.microsoft.com/entra/identity-platform/scenario-spa-overview |
| App Service deployment slots | https://learn.microsoft.com/azure/app-service/deploy-staging-slots |
| Managed identity with Azure SQL | https://learn.microsoft.com/azure/azure-sql/database/authentication-azure-ad-user-assigned-managed-identity |
| GitHub Actions OIDC with Azure | https://docs.github.com/actions/security-for-github-actions/security-hardening-your-deployments/configuring-openid-connect-in-azure |
| GitHub Actions script-injection guidance | https://docs.github.com/actions/security-for-github-actions/security-guides/security-hardening-for-github-actions |
| EF Core migrations | https://learn.microsoft.com/ef/core/managing-schemas/migrations/ |
| ASP.NET Core rate limiting | https://learn.microsoft.com/aspnet/core/performance/rate-limit |

## Tooling used to generate this document

Mermaid CLI 11 (workspace-local), Pandoc 3.13, headless Google Chrome (puppeteer), Node.js 26.
