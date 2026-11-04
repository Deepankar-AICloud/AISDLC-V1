# Adopting AISDLC {#adoption}

## Prerequisites

| Area | Requirement |
|---|---|
| Source control | A GitHub repository (organisation or enterprise) with GitHub Actions enabled and permission for Actions to create pull requests |
| AI | GitHub Copilot access, and a token for the Copilot CLI stored as a repository secret |
| Security | GitHub CodeQL (default setup) and secret scanning enabled |
| Cloud (for deployment) | An Azure subscription, resource groups per environment, and an Entra ID application with a GitHub OIDC federated credential |
| Governance | GitHub environments (`dev`, `staging`, `production`) with required reviewers on production; CODEOWNERS teams |
| People | Named reviewers for business, product, architecture, engineering, security and release |

Table: Table 13.1 — Prerequisites

## Onboarding approach

| Phase | Activities | Outcome |
|---|---|---|
| 1 · Set-up | Install the control plane and workflows in your repository; configure secrets, environments, CODEOWNERS and models; tailor agent instructions to your standards | Platform ready |
| 2 · Pilot | Run one real requirement end to end with your reviewers; tune thresholds, contracts and reviewer assignments | Validated way of working; baseline metrics |
| 3 · Scale | Roll out to more teams and requirement types; add organisation-specific agents or contracts (for example, compliance checklists) | Repeatable delivery model |
| 4 · Optimise | Review QC and model-decision reports; adjust routing, thresholds and stage policies | Continuous improvement |

Table: Table 13.2 — Adoption phases (indicative; durations are agreed per engagement)

## Roles and responsibilities

| Activity | Requester | Product owner | Architect | Engineering lead | Security | Release manager | AISDLC |
|---|---|---|---|---|---|---|---|
| Write the requirement issue | R/A | C | | | | | I |
| Answer readiness questions | R | A | C | | | | I |
| Approve BRD / PRD / Epics | C | R/A | C | I | I | | Drafts |
| Approve architecture / NFRs | I | C | R/A | C | C | | Drafts |
| Approve task plan / code | | I | C | R/A | C | | Drafts, builds, tests |
| Approve production release | I | C | I | C | C | R/A | Evidence pack |

Table: Table 13.3 — RACI (R responsible, A accountable, C consulted, I informed)

## Writing a good requirement issue

A good issue covers the following, in plain business language:

- The **business problem**.
- The **objective** or outcome.
- The **stakeholders and roles**.
- The **scope**.
- Any **constraints** (technology, security, compliance).

State what you know, and say explicitly what is still undecided. AISDLC will record undecided items as open questions rather than guessing.

# Current Capabilities, Limitations and Roadmap {#capabilities-roadmap}

## Capabilities today

| Capability | Status |
|---|---|
| Requirement intake with readiness gate and clarification loop | [AVAILABLE]{.badge .ok} |
| AI-generated BRD, PRD, epics and stories, architecture, NFRs and task plan, with quality gates and PR approval | [AVAILABLE]{.badge .ok} |
| AI-generated code with pipeline-run build and tests, scoped file changes, and revision across attempts | [AVAILABLE]{.badge .ok} |
| Model router with human confirmation, escalation, fallback and decision log | [AVAILABLE]{.badge .ok} |
| CI, secret scanning, CodeQL gate, staged deployment with DAST, mandatory production approval, release evidence | [AVAILABLE]{.badge .ok} |
| AI agents for code review, functional testing, performance and release | [PLANNED]{.badge .planned} — handled today by deterministic CI/CD tools and human review |

Table: Table 14.1 — Capability status

## Known limitations

- **AI output still needs expert review.** Quality gates reduce rework but do not replace reviewers. Clear, complete requirements are the biggest driver of fast, high-scoring stages.
- **Iterations vary by stage.** Design stages with many open business decisions may need several review rounds. Answering clarifications in one consolidated comment works best.
- **Token and cost visibility** depend on the AI provider. With the Copilot CLI, tokens and costs are reported as *unavailable*.
- **The code-stage pass mark is currently 60/100.** The build and tests are mandatory, and human code review remains the deciding control. The threshold is configurable and is expected to rise as the stage matures.

## Roadmap

| Item | Benefit |
|---|---|
| Further hardening of comment-driven automation (input handling, member-only commands) | Stronger protection against malicious input |
| Fine-grained tool permissions for the engineer agent | Tighter least-privilege for AI-driven code changes |
| AI agents for code review and functional test generation as pipeline stages | More automation after the code stage, still human-approved |
| Per-stage dashboards (lead time, QC trends, review rounds) | Easier measurement of value |
| Provider-reported token usage and cost where available | Full cost transparency |
| Organisation templates (compliance checklists, architecture standards) as contracts | Built-in alignment with your standards |

Table: Table 14.2 — Roadmap (no dates implied)

# Frequently Asked Questions {#faq}

**Does AISDLC replace business analysts, architects or developers?**
No. It removes much of the drafting effort and enforces consistency. Every artifact is reviewed and approved by the responsible person, and accountability stays with your team.

**Can the AI invent requirements?**
AISDLC is designed to prevent this:

- The readiness gate stops when information is missing.
- The reviewer model penalises unsupported content.
- Unconfirmed design choices must be labelled *(proposed)*.
- A person approves every artifact.

**Which AI models are used, and can we choose?**
Models are configured in tiers and recommended per stage. For high-impact stages a person confirms the model or selects another, and every decision is logged with its reason.

**Where do our code and data go?**
Artifacts and code stay in your GitHub repository. AI calls go through GitHub Copilot under your organisation's Copilot terms and policies. Deployments go to your own cloud subscription using OIDC, without stored cloud credentials.

**Can we adapt it to our standards?**
Yes. Agent instructions, artifact contracts, quality thresholds, reviewers, environments and model routing are all configuration in your repository.

**What if a stage keeps failing the quality gate?**
The stage pauses and posts the reviewer's findings on the issue. A short reply with the missing decisions resumes it, and the agent revises its previous draft rather than starting over.

**Do we need Azure?**
The reference implementation deploys to Azure. The define, design and build stages are cloud-agnostic; the deployment workflows can be adapted to other targets.

# Glossary {#glossary}

| Term | Meaning |
|---|---|
| AISDLC | AI-Driven Software Development Lifecycle |
| BRD / PRD | Business Requirements Document / Product Requirements Document |
| NFR | Non-functional requirement (security, performance, availability, …) |
| Artifact contract | Rules an artifact must satisfy: required sections, ID formats, upstream references |
| Quality gate (QC) | Independent evaluation with a pass mark that an artifact must meet before review |
| Readiness gate | Check that the requirement contains the information needed before generation |
| Model router | Component that recommends and selects AI models by task complexity |
| Orchestrator | Control-plane component that owns the workflow state and runs one stage at a time |
| Pull request (PR) | GitHub review mechanism used for human approval of every stage |
| CodeQL / DAST | Static code analysis / dynamic application security testing |
| OIDC | OpenID Connect, used to deploy to the cloud without stored secrets |

Table: Table 16.1 — Glossary
