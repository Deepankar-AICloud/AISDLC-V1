# AISDLC-V1 — SmartServe + Agentic SDLC Platform

This repository contains two integrated systems:

1. **SmartServe** — an Enterprise IT Service & Access Request Management Portal.
2. **An Agentic SDLC automation platform** that drives a requirement from a
   GitHub issue through the full software lifecycle with QC gates,
   human-in-the-loop PR review, a model router, token/cost telemetry, and
   end-to-end traceability.

---

## SmartServe application

| Layer | Technology | Location |
|---|---|---|
| Frontend | React + TypeScript (Vite), MSAL | `src/frontend` |
| Backend | .NET 8 Web API, EF Core | `src/backend/SmartServe.Api` |
| Tests | xUnit (unit + integration) | `src/backend/SmartServe.Tests` |
| Database | Azure SQL (In-Memory for local dev) | — |
| Auth | Microsoft Entra ID (server-side policies) | — |
| Secrets | Azure Key Vault + Managed Identity | — |
| Monitoring | Application Insights, `/health` endpoint | — |
| Hosting | Azure App Service (+ staging slot) | `infra/` |

**Roles:** Employee, Manager, SecurityReviewer, ItAdmin, AppAdmin, Auditor —
authorization is enforced **server-side** (API authorization policies), not only
in the UI.

## Run locally

Backend:
```bash
cd src/backend
dotnet build SmartServe.sln -c Release
dotnet test  SmartServe.sln -c Release          # 16 tests
dotnet run --project SmartServe.Api             # In-Memory DB when no conn string
```

Frontend:
```bash
cd src/frontend
npm install
npm run dev                                      # http://localhost:5173 (proxies /api)
```

Secrets/config are supplied via environment or Key Vault — never committed.
Copy `src/frontend/.env.example` to `.env.local` for Entra settings.

---

## Agentic SDLC platform

The orchestrator owns workflow **state**; agents own **specialized work**; QC
**evaluates**; humans own **approvals**; the model router owns **model
selection**; GitHub Actions owns **execution**.

```
GitHub Issue → Orchestrator → (Model Router) → Agent → QC
   → PASS → stage PR → human review → approve/merge → next stage
   → FAIL → retry (escalate model) → after max retries → NEEDS_HUMAN_INTERVENTION
```

| Component | Location |
|---|---|
| Agent definitions | `.github/agents/*.agent.md` |
| Orchestrator / state machine | `scripts/sdlc/orchestrator/` |
| Model router | `scripts/sdlc/model_router/` |
| QC evaluator | `scripts/sdlc/quality/` |
| Token/cost telemetry | `scripts/sdlc/telemetry/` |
| Traceability engine | `scripts/sdlc/traceability/` |
| Reports | `scripts/sdlc/reporting.py` → `reports/<run-id>/` |
| Configuration | `config/agents.yml`, `models.yml`, `quality-gates.yml`, `pricing.yml`, `environments.yml` |
| Workflows | `.github/workflows/agentic-sdlc.yml`, `artifact-review.yml`, `feedback-handler.yml` |

### Trigger

Label an issue `sdlc:start` (or dispatch `agentic-sdlc.yml` with an issue
number). Each run advances **one stage**, opens/updates a stage PR, and waits
for human approval. Approving the PR resumes the orchestrator.

Safe feedback commands in PR/issue comments (allowlisted):
`/agent revise|regenerate|rerun-qc|explain|status`.

### Run the orchestrator locally

```bash
pip install -r scripts/requirements.txt
# Deterministic dry-run (no LLM calls), validates the full pipeline:
python -m scripts.sdlc.run --issue 1 --context "..." --no-llm
```

## Traceability

`REQ → BRD-REQ → PRD-FR → EPIC → FEATURE → US → ARCH-COMP → TASK → CODE → UT → FT → SEC → RELEASE`

Reports per run: `usage.json`, `usage.csv`, `model-cost-report.md`,
`quality-report.md`, `traceability-report.md`, `workflow-report.md`, plus a
GitHub Actions Job Summary. Cost figures are labeled `estimated` / `unavailable`
— never presented as provider billing, and token counts are never fabricated.

---

## CI / Security / Deployment

| Workflow | Purpose |
|---|---|
| `ci.yml` | Build/lint/test/coverage for .NET + React (paths `src/**`) |
| `security.yml` | CodeQL SAST + secret scan |
| `deploy-dev.yml` | OIDC login → Bicep → deploy to DEV App Service → smoke test |
| `deploy-staging.yml` | Deploy to staging slot → tests → OWASP ZAP DAST |
| `deploy-production.yml` | Mandatory `production` environment approval → slot swap → health checks |

Azure auth uses **GitHub OIDC** (no long-lived secrets) and **Managed
Identity**. Infrastructure is defined in `infra/main.bicep` and parameterized
per environment.

> The legacy Ticket Tracker (Flask) assets and the auto-healing
> `deploy.yml` (Azure Container Apps), council, and gatekeeper workflows remain
> intact for reference and are independent of the SmartServe pipeline.
