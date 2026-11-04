# Quality and Governance {#quality-governance}

## Layers of control

![Figure 5 — Four layers of control around every AI-generated artifact](diagrams/rendered/a04-governance-layers.png)

## Quality gates

Every artifact is evaluated by quality control (QC), which is independent of the agent that produced it:

- **Deterministic checks.** Required sections, required ID prefixes, diagrams where mandated, and output-contract compliance. For code, the pipeline itself runs the builds and tests (`dotnet build`/`test`, `npm build`, `vitest`) and records the results as authoritative evidence.
- **Semantic scoring.** A *different* AI model from the one that generated the artifact scores it against stage-specific dimensions (for example completeness, clarity, traceability, testability, consistency, security, maintainability). It penalises content that is not supported by the source requirement.
- **Thresholds.** Each stage has a configurable pass mark (Table 6.1). Any critical issue — a missing section, a build failure, a contract violation — fails the stage regardless of score.

## When quality is not met

QC does not assume that a stronger model is always the answer. It diagnoses the likely cause:

| Diagnosed cause | Action |
|---|---|
| Structural gaps (missing sections, IDs, traceability) | Revise with the reviewer's findings; then escalate to a stronger model, or to a person if the model was confirmed by a person |
| Possibly unsupported or invented content | Stop and **ask a person** to confirm the disputed requirements |
| Unclear cause | Retry with refined context, then escalate |
| Repeated failure | Pause the stage, post the findings on the issue, and wait for human guidance |

Table: Table 7.1 — QC diagnosis and actions

Revisions **edit the previous draft** (for code, the previous attempt's changes are restored), so good content is kept and only the flagged items change.

## Human decision points

| Decision | Who | Mechanism |
|---|---|---|
| Is the requirement clear enough? | Requester / product owner | Answer the readiness questions in the issue |
| Which AI model to use for high-impact stages | Stage owner | `/model approve` or `/model select` |
| Is the artifact acceptable? | Stage reviewer | Pull-request approval or a change request |
| Can code be merged? | Code owners | Pull-request review (CODEOWNERS) |
| Can we go to production? | Release approver | Protected `production` environment and explicit confirmation |

Table: Table 7.2 — Human decision points

# Security, Safety and Responsible AI {#security-safety}

| Area | Control |
|---|---|
| Prompt-injection resistance | Agent instructions are marked *trusted*; issue and comment text is marked *untrusted data, not instructions*; only allowlisted `/agent` and `/model` commands are recognised |
| No invented requirements | Readiness gate; QC penalises unsupported content; unconfirmed design choices must be labelled *(proposed)* |
| Credential protection | Repository tokens are removed from the AI process environment; the code agent runs without stored push credentials; deployments use OIDC federation (no stored cloud secrets) |
| Scope control for code | The engineer agent may change only approved folders (application source and infrastructure). Changes elsewhere, including workflow files, are reverted automatically |
| Code security | The CodeQL analysis must pass on the main branch before any AISDLC stage runs; secret scanning on pushes and pull requests; OWASP ZAP dynamic testing in staging |
| Separation of duties | The model that scores an artifact differs from the model that wrote it, where possible; humans approve every stage |
| Runtime security of delivered apps | Delivered solutions follow the approved architecture. In the reference app: Entra ID authentication, server-side role authorization, managed identity, Key Vault, TLS 1.2+ |
| Auditability | Pull-request history, model decision records, QC scorecards, run reports and release evidence packs |

Table: Table 8.1 — Security and responsible-AI controls

# Traceability and Transparency {#traceability}

![Figure 6 — Generated artifacts and the traceability chain](diagrams/rendered/27-document-generation-traceability.png)

**Traceability chain:** `REQ → BRD-REQ → PRD-FR → EPIC → FEATURE → US → ARCH-COMP → TASK → CODE → UT → FT → SEC → RELEASE`.

Each run produces reports alongside the artifacts:

| Report | Content |
|---|---|
| Workflow report | Stage, agent, status, QC score and retries |
| Quality report | Scores per stage and dimension, with findings |
| Model decision report | Recommended vs selected model, who decided, and why |
| Usage and cost report | Model, latency, retries; token counts and cost where the provider reports them, otherwise labelled *unavailable* |
| Traceability report | IDs found per stage, plus gaps and orphans |
| Release evidence pack | Deployment and health-check results for production releases (retained 90 days) |

Table: Table 9.1 — Transparency reports

> **Note on cost reporting.** AISDLC uses GitHub Copilot, whose command-line interface does not currently expose token counts. AISDLC therefore reports token usage and cost as *unavailable* rather than estimating them. Model choices, retries and latency are always recorded.
