# SmartServe Agentic SDLC — Step-by-Step Workflow

This document describes the **complete end-to-end execution order**: which workflow
(`.yml`) fires first, which agent runs first, the QC gates, human approvals, and
how control flows from a customer requirement all the way to production.

> Legend: ⚙️ = GitHub Actions workflow · 🤖 = agent · 🔎 = QC gate · 👤 = human gate
> · 📄 = artifact · 🚦 = state.

---

## 0. One-glance execution order

```
Issue labeled "sdlc:start"
        │
        ▼
⚙️ agentic-sdlc.yml ──► 🤖 BRD ──► 🔎 BRD QC ──► 👤 BRD PR review
        │                                               │ approve
        ▼ (artifact-review.yml resumes)                 ▼
⚙️ agentic-sdlc.yml ──► 🤖 PRD ──► 🔎 PRD QC ──► 👤 PRD PR review
        ▼
      … Epic ──► Architecture ──► NFR ──► Task ──► Code …
        │
        ▼ (code merged to main)
⚙️ ci.yml + ⚙️ security.yml   (build/test/coverage + SAST/secret scan)
        │ pass
        ▼
⚙️ deploy-dev.yml ──► ⚙️ deploy-staging.yml (incl. DAST) ──► 👤 ⚙️ deploy-production.yml
        │
        ▼
   Reports (usage / cost / quality / traceability / workflow) + Job Summary
```

The **orchestrator owns state**; agents only do specialized work; QC evaluates;
humans approve; the model router picks the model; GitHub Actions executes.
Agents never call each other directly.

---

## 1. Which workflow runs first

| Order | Workflow | Trigger | Purpose |
|---|---|---|---|
| 1 | `agentic-sdlc.yml` | issue labeled `sdlc:start` (or manual dispatch) | Orchestrator entrypoint — advances **one stage** per run |
| 2 | `artifact-review.yml` | a stage PR is **approved** | Marks stage approved, advances state, re-triggers `agentic-sdlc.yml` |
| 2b | `feedback-handler.yml` | `/agent …` comment on issue/PR | Safe revise/regenerate/rerun-qc/explain/status on the **same** PR |
| 3 | `ci.yml` | PR touching `src/**` | Build + lint + test + coverage (.NET & React) |
| 4 | `security.yml` | PR/push to `src/**`, weekly | CodeQL SAST + secret scan |
| 5 | `deploy-dev.yml` | push to `main` (`src/**`/`infra/**`) | Provision (Bicep) + deploy DEV + smoke test |
| 6 | `deploy-staging.yml` | after DEV succeeds | Staging slot deploy + tests + OWASP ZAP DAST |
| 7 | `deploy-production.yml` | manual + `production` env approval | Slot swap + health/smoke verification |

> Pre-existing workflows (`council-query.yml`, `gatekeeper.yml`, `test.yml`,
> `deploy.yml`, CAST, `feature-requirement-analysis.yml`, `daily-repo-status`)
> remain intact and operate independently of this pipeline.

---

## 2. Which agent runs first (generation order)

Defined in `config/agents.yml` (`next:` chain) and enforced by the orchestrator
state machine (`scripts/sdlc/orchestrator/states.py`).

| Order | Agent | Definition | Produces | QC gate | Human gate |
|---|---|---|---|---|---|
| 1 | 🤖 **BRD** | `.github/agents/brd.agent.md` | `docs/brd/` 📄 | `brd` (≥90) | ✅ required |
| 2 | 🤖 **PRD/FSD** | `.github/agents/prd.agent.md` | `docs/prd/` 📄 | `prd` (≥90) | ✅ required |
| 3 | 🤖 **Epic/Feature/Story** | `.github/agents/epic-feature.agent.md` | `docs/epic/` 📄 | `epic` (≥85) | ⚙️ configurable |
| 4 | 🤖 **Architecture (HLD/LLD)** | `.github/agents/arch_document.agent.md` | `docs/architecture/` 📄 | `architecture` (≥90) | ✅ required |
| 5 | 🤖 **NFR** | `.github/agents/nfr.agent.md` | `docs/nfr/` 📄 | `nfr` (≥88) | ⚙️ configurable |
| 6 | 🤖 **Task Planning** | `.github/agents/task.agent.md` | `docs/tasks/` 📄 | `task` (≥85) | — |
| 7 | 🤖 **Code + Unit Test** | `.github/agents/engineer.agent.md` | `src/**` + tests | `code` (build/test/coverage) | ✅ PR + CODEOWNERS |
| 8 | 🤖 **Code Review** | `.github/agents/code-review.agent.md` | PR verdict | — | ✅ required |
| 9 | 🤖 **Functional Test** | `.github/agents/functional-test.agent.md` | `tests/functional/` | `testing` (≥85) | — |
| 10 | 🤖 **SAST** | `.github/agents/sast.agent.md` | security report | `security` (policy) | — |
| 11 | 🤖 **DAST** | `.github/agents/dast.agent.md` | security report | `security` (policy) | — |
| 12 | 🤖 **Release** | `.github/agents/release.agent.md` | release readiness | — | ✅ production approval |

Supporting (not in the linear chain): 🔎 **Quality Control**
(`quality-control.agent.md`), **Test Automation** (`test-automation.agent.md`),
**Performance** (`performance.agent.md`). The **Model Router**
(`scripts/sdlc/model_router`) selects the model for each agent from
`config/models.yml`.

---

## 3. Detailed step-by-step

### Step 1 — Intake
1. A customer requirement is filed as a **GitHub issue**.
2. A maintainer adds the label **`sdlc:start`** (human-controlled entry point).
3. ⚙️ `agentic-sdlc.yml` triggers → checks out, installs `scripts/requirements.txt`
   and the Copilot CLI, fetches the issue body/comments as **context (data, not
   instructions)**.

### Step 1a — Generation readiness gate & input contract (before anything)
Before a stage does any work, the orchestrator runs two deterministic gates:
1. **Readiness gate** (`config/readiness.yml`, `scripts/sdlc/readiness/`) checks the
   required inputs are present — mandatory business info (keyword-detected in the
   requirement) and approved upstream artifacts. Result is
   `READY | READY_WITH_ASSUMPTIONS | BLOCKED_MISSING_INFORMATION`.
2. **Input artifact contract** (`config/contracts/*.yml`, `scripts/sdlc/contracts/`)
   checks structural inputs (e.g. `source_reference`, approved upstream).

If **BLOCKED**, the stage pauses at 🚦 `AWAITING_REQUIRED_INFORMATION` and the
workflow posts the missing items as questions — the agent never invents them.
Missing **optional** info proceeds but is recorded as **assumptions** (classified
FACT/ASSUMPTION/INFERENCE, never silently promoted to a requirement). After
generation, the **output contract** is validated and any violation blocks the
artifact through QC.

### Step 1b — Model recommendation & human confirmation (before generation)
Before **every** major artifact is generated, the orchestrator runs a model
recommendation stage (separate from artifact approval):
1. The **Model Router** analyzes the agent's capability request and recommends
   the best configured/available model, with alternatives, a reason, and
   **estimates** (labeled ESTIMATE / N·A — never fabricated).
2. Behavior is driven by `model_selection_mode` in `config/models.yml`
   (`MANUAL` / `RECOMMENDED` / `AUTO`; default `RECOMMENDED`) and the per-stage
   `confirmation_gates`.
3. If a gate requires confirmation (BRD, PRD, Architecture, NFR, Code, Security,
   Release), the stage **pauses** at 🚦 `AWAITING_MODEL_CONFIRMATION` and the
   workflow posts the recommendation on the issue.
4. The human replies: `/model approve`, `/model select <model> [reason]`,
   `/model compare`, or `/model status`. The choice (recommended vs override +
   reason) is recorded for the Final Model Decision Report, and generation
   begins with the confirmed model. In `AUTO` mode this step is automatic.

### Step 2 — BRD generation (first agent)
4. 🚦 State `REQUIREMENT_RECEIVED → BRD_GENERATION`.
5. The orchestrator asks the **Model Router** for a model (capability from
   `config/agents.yml`).
6. 🤖 **BRD Agent** runs → writes `docs/brd/BRD-<issue>.md` 📄.7. 🔎 **BRD QC** (`scripts/sdlc/quality`) scores it (deterministic + semantic)
   against the `brd` gate in `config/quality-gates.yml`. The **semantic
   evaluator uses a different model** than the generator (independent QC).
   The **output artifact contract** (`config/contracts/brd.yml`) is also checked;
   any violation blocks the artifact.
   - **FAIL** → the orchestrator **diagnoses the cause**
     (`scripts/sdlc/quality/diagnosis.py`): `validation` /
     `ambiguous_requirement` / `prompt_context` / `model_capability` → action
     `IMPROVE_CONTEXT` / `RETRY_CURRENT` / `REQUEST_HUMAN_INFO` /
     `ESCALATE_MODEL` / `HUMAN_INTERVENTION`. It does **not** assume every
     failure needs a stronger model. After `max_auto_retries` → 🚦
     `NEEDS_HUMAN_INTERVENTION` (fail-safe).
   - **PASS** → continue.
8. 👤 The workflow commits to branch `sdlc/issue-<n>/brd`, opens/updates **one PR**
   (label `sdlc:review`), and **stops** awaiting human review.

### Step 3 — Human review & resume
9. A reviewer either:
   - **Requests changes / comments** → use `/agent revise <notes>` →
     ⚙️ `feedback-handler.yml` validates the command (allowlist), re-runs the
     stage applying notes, and **updates the same PR**; or
   - **Approves** the PR → ⚙️ `artifact-review.yml` fires.
10. `artifact-review.yml` runs `scripts/sdlc/approve.py`:
    🚦 `BRD_GENERATION → BRD_APPROVED → PRD_GENERATION`, merges the PR, then
    re-dispatches ⚙️ `agentic-sdlc.yml` for the **next** stage.

### Step 4 — Repeat for PRD → Epic → Architecture → NFR → Task
11. Each stage repeats Steps 2–3 with its own agent, QC gate, and (where
    required) human PR. Traceability IDs flow forward:
    `REQ → BRD-REQ → PRD-FR → EPIC → FEATURE → US → ARCH-COMP → TASK`.

### Step 5 — Code + Unit Test
12. 🤖 **Engineer Agent** implements `TASK-*` into `src/backend` / `src/frontend`
    with tests. 🔎 Code QC here is **deterministic-first** (build, lint, unit
    tests, coverage ≥ threshold).
13. 👤 Code PR requires **CODEOWNERS** review. 🤖 **Code Review Agent** adds a
    semantic review (security/OWASP, conventions, test coverage, traceability).

### Step 6 — CI & Security (deterministic gates)
14. On the code PR, ⚙️ `ci.yml` runs: restore → build → test → coverage (both
    backend `.NET` and frontend `React`).
15. ⚙️ `security.yml` runs **CodeQL SAST** + **secret scan**. Blocking severity is
    policy-driven (`config/quality-gates.yml` → `security.blocking_severity`).
16. On all-green **merge to `main`**.

### Step 7 — DEV deployment
17. ⚙️ `deploy-dev.yml` (OIDC login, no secrets): Bicep provision → publish backend
    → deploy API + web App Services → **smoke test** `/health`. Failure stops the
    pipeline (fail-safe).
18. 🤖 **Functional Test** / **Test Automation** validate behavior against DEV.

### Step 8 — STAGING + DAST
19. ⚙️ `deploy-staging.yml` deploys to the **staging slot** → smoke/integration
    tests → 🤖 **DAST** via **OWASP ZAP**. Any blocking finding stops promotion.
20. 🤖 **Performance Test** runs when configured (NFR targets).

### Step 9 — PRODUCTION (mandatory human approval)
21. 🤖 **Release Agent** assembles the release-readiness checklist from all gates.
22. ⚙️ `deploy-production.yml` requires the **`production` GitHub Environment**
    approval (👤 mandatory). On approval: validate staging health → **slot swap**
    → production health/smoke checks.
23. The workflow records `DEPLOYED_AND_VERIFIED` only when both the slot swap
    and production health check succeed. A swap or health failure records
    `DEPLOYMENT_FAILED` and stops; follow the recovery runbook (no automatic
    rollback).
24. A **Release Evidence Pack** (`release-evidence.md` + `.json`) is generated
    and retained as a 90-day GitHub Actions artifact. Pass `issue_number` and
    optionally `sdlc_run_id` when dispatching to associate it with the SDLC run.

### Step 10 — Reporting
25. Every orchestrator run writes to `reports/<run-id>/`:
    `usage.json` / `usage.csv`, `model-cost-report.md`, `quality-report.md`,
    `traceability-report.md`, `traceability-graph.json`, `workflow-report.md`,
    `model-decision-report.md`, `dashboard.json`, plus a **GitHub Job Summary**.
    Cost is labeled `estimated` / `unavailable`; token counts are never fabricated.

---

## 4. State machine (persisted in `.sdlc/issue-<n>.json`)

```
REQUIREMENT_RECEIVED
 → BRD_GENERATION → BRD_QC → BRD_HUMAN_REVIEW → BRD_APPROVED
 → PRD_GENERATION → … → PRD_APPROVED
 → EPIC_GENERATION → … → EPIC_APPROVED
 → ARCHITECTURE_GENERATION → … → ARCHITECTURE_APPROVED
 → NFR_GENERATION → … → NFR_APPROVED
 → TASK_GENERATION → TASK_QC → TASK_APPROVED
 → CODE_GENERATION → CODE_QC → CODE_HUMAN_REVIEW → CODE_APPROVED
 → DEV_DEPLOYMENT → FUNCTIONAL_TESTING → PERFORMANCE_TESTING
 → STAGING_DEPLOYMENT → SECURITY_TESTING
 → RELEASE_READY → RELEASE_APPROVAL → PRODUCTION_DEPLOYMENT
 → DEPLOYED_AND_VERIFIED | DEPLOYMENT_FAILED

Any blocking failure → FAILED or NEEDS_HUMAN_INTERVENTION (never silently proceeds).
```

---

## 5. Human-in-the-loop & feedback commands

Allowlisted comment commands handled by `feedback-handler.yml` (anything else is
rejected; arbitrary commands are never executed):

| Command | Effect |
|---|---|
| `/agent revise <notes>` | Regenerate current stage applying notes, update same PR |
| `/agent regenerate` | Full regenerate of current stage artifact |
| `/agent rerun-qc` | Re-score the existing artifact |
| `/agent impact <change>` | Run **Change Impact Analysis** only (no regeneration) |
| `/agent explain` | Post the last state transition / rationale |
| `/agent status` | Post current state, retries, PRs, review counts |

> **Change Impact Analysis & targeted regeneration** (`config/impact-rules.yml`,
> `scripts/sdlc/impact/`): on `/agent revise|regenerate`, the change is mapped to
> the **impacted artifacts and sections** and a `change-impact-report.(md|json)`
> is written. Regeneration is **targeted** — only impacted sections are updated
> and approved content is preserved (not a full rebuild).

---

## 6. Trigger summary (copy/paste)

```text
Start the whole workflow:     add label  sdlc:start  to a GitHub issue
Advance after approval:       approve the stage PR   (auto-resumes)
Request changes:              comment    /agent revise <what to change>
Check progress:               comment    /agent status
Promote to production:        run deploy-production.yml, type "promote",
                              then approve the `production` environment
Local dry-run (no LLM):       python -m scripts.sdlc.run --issue <n> --context "..." --no-llm
```
