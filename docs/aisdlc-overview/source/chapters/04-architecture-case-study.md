# Architecture and Technology {#architecture-technology}

![Figure 7 — AISDLC platform architecture](diagrams/rendered/a05-platform-architecture.png)

| Layer | Technology |
|---|---|
| Collaboration and execution | GitHub Issues, Pull Requests, Actions, CODEOWNERS, environments |
| AI | GitHub Copilot (model families configured in tiers: fast, balanced, high-reasoning, with automatic fallback) |
| Control plane | Python 3.13 orchestrator, model router, quality control, readiness and contract gates, telemetry, traceability |
| Configuration | YAML: agents, models and routing, quality gates, artifact contracts, readiness rules, budgets, environments, impact rules |
| Code security | GitHub CodeQL, secret scanning (gitleaks), OWASP ZAP |
| Target platform (reference) | Azure App Service with deployment slots, Azure SQL, Key Vault, Application Insights, Bicep infrastructure as code, GitHub OIDC |

Table: Table 10.1 — Technology stack

**Model tiers (configurable).**

| Tier | Typical use | Preferred / fallback |
|---|---|---|
| Fast | Classification, formatting, simple summaries | gpt-5-mini / claude-haiku-4.5 |
| Balanced | BRD, PRD, epics, stories, test cases | gpt-5.5 / claude-sonnet-4.6 |
| High reasoning | Architecture, complex code, security reasoning | claude-sonnet-5 / gpt-5.5 |

Model names are configuration, not code, and change as the provider's catalogue evolves.

**Design choices that keep you in control:**

- **No external AI platform to operate.** The control plane is code in your repository and runs on GitHub Actions.
- **Model-agnostic.** Swap or add models in configuration. When a model is not available to your account, AISDLC records the fallback it used.
- **Repository-native artifacts.** Every document is Markdown with Mermaid diagrams, version-controlled and reviewable like code.
- **Composable.** Stages can be enabled or disabled, their reviewers changed and thresholds tuned without code changes.

# Case Study — SmartServe {#case-study}

**Requirement.** Employees and IT teams needed a secure, centralised way to submit, review and track IT service and access requests. The constraints were Microsoft Entra ID authentication, server-side authorization, Azure SQL via Entity Framework Core, and managed identity with Key Vault.

**What AISDLC delivered from one GitHub issue (#23):**

![Figure 8 — Artifacts AISDLC produced for SmartServe, each approved through a pull request](diagrams/rendered/a06-case-study-outputs.png)

| Stage | Artifact | Content | Approved in |
|---|---|---|---|
| BRD | `docs/brd/BRD-23.md` | 9 business requirements, stakeholders, scope, acceptance criteria | PR #24 |
| PRD | `docs/prd/PRD-23.md` | 4 functional + 5 non-functional requirements traced to the BRD | PR #25 |
| Epics and stories | `docs/epic/EPIC-23.md` | 6 epics, 8 features, 13 user stories | PR #26 |
| Architecture | `docs/architecture/ARCH-23.md` | 13 architecture components, diagrams; confirmed vs *(proposed)* choices labelled | PR #28 |
| NFRs | `docs/nfr/NFR-23.md` | 5 verifiable NFRs; performance, retention and DR recorded as open questions rather than invented | PR #30 |
| Task plan | `docs/tasks/TASK-23.md` | 16 tasks, 16 unit-test tasks, 3 functional-test tasks | PR #32 |
| Code | `src/backend`, `src/frontend`, `infra` | 55 files changed (+8,531 / −513 lines), built and tested by the pipeline | PR #34 |

Table: Table 11.1 — SmartServe artifacts

**What the case study demonstrated:**

- **The platform asks instead of guessing.** When the intake lacked business context, it paused and requested the problem, objective and stakeholders. Later stages surfaced open decisions (notification triggers, role scoping, retention) as questions for the business.
- **Quality gates change the outcome.** Several stages needed more than one iteration. Reviewer findings were posted on the issue, product owners answered them in comments, and the agents revised their drafts until the gate passed.
- **People stayed in control.** Model choices were confirmed for high-impact stages, and every artifact was merged only after pull-request approval.
- **The output is consistent.** Every artifact follows its contract and carries traceable IDs back to the original requirement.

**Next steps for SmartServe** are the standard verification and release stages: CI, security scanning, DEV and STAGING deployment with DAST, and an approved production promotion. These are covered in the companion *SmartServe — Complete Application Solution Document*.

# Benefits and Value {#benefits}

| Benefit | How it is achieved | How to measure it in your organisation |
|---|---|---|
| Shorter time from idea to reviewable design | Agents draft each artifact; people review | Elapsed time from issue creation to approved architecture or task plan |
| Higher documentation quality and consistency | Contracts, quality thresholds, automatic revision | QC scores per stage; number of review rounds |
| Fewer requirement gaps reaching development | Readiness gate, open-question handling, NFR discipline | Clarification questions raised before vs after development |
| End-to-end traceability for audit | Stable IDs and traceability reports | Coverage of requirement-to-test links; audit preparation effort |
| Controlled, explainable AI use | Model router, decision log, human approvals | Share of stages with human-confirmed models; override reasons |
| Safer releases | Security gates, staged deployment, mandatory approval | Failed releases; security findings caught pre-production |

Table: Table 12.1 — Benefits and suggested measures

AISDLC records the data behind these measures (stage timestamps, QC scores, retries, model decisions) in its run reports. We recommend agreeing baseline values at the start of an engagement so that improvements can be measured objectively.
