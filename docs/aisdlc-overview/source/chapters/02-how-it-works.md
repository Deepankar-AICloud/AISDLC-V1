# Guiding Principles {#guiding-principles}

AISDLC is built on principles that are enforced in configuration and code, not just written down.

| # | Principle | How it is enforced |
|---|---|---|
| 1 | **Human in the loop** before progression | Every stage ends in a pull request; the next stage starts only after approval |
| 2 | **Quality before advancing** | An artifact that scores below its threshold, or breaks its contract, cannot progress |
| 3 | **Never invent requirements** | The readiness gate pauses and asks; design choices that are not confirmed must be labelled *(proposed)* |
| 4 | **Full traceability** | Required ID prefixes and upstream references per stage; a traceability report per run |
| 5 | **Security by design** | Code scanning gate, secret scanning, least-privilege tokens, OIDC to the cloud, managed identities |
| 6 | **Configuration over hard-coding** | Agents, models, thresholds, contracts and environments are YAML configuration |
| 7 | **Honest telemetry** | Token usage and cost are recorded only when known; otherwise they are labelled *unavailable*, never estimated as fact |
| 8 | **Mandatory production approval** | Production release requires a named approver and an explicit confirmation |
| 9 | **Untrusted input is data, not instructions** | Issue and comment text is clearly separated from the agents' trusted instructions |

Table: Table 4.1 — Principles and enforcement

# How AISDLC Works {#how-it-works}

## The lifecycle

![Figure 2 — The AISDLC lifecycle: define, design, build, verify and release](diagrams/rendered/a02-lifecycle.png)

| Stage | Input | Output (artifact) | Reviewer |
|---|---|---|---|
| 0 · Intake | Business need written as a GitHub issue | Validated requirement context | Requester |
| 1 · BRD | Issue and clarifications | Business Requirements Document (`BRD-REQ-nnn`) | Business owner |
| 2 · PRD | Approved BRD | Product / functional specification (`PRD-FR`, `PRD-NFR`) | Product owner |
| 3 · Epics and stories | Approved PRD | Epics, features, user stories with acceptance criteria | Product owner |
| 4 · Architecture | Approved PRD | Architecture document with diagrams (`ARCH-COMP`) | Architect |
| 5 · NFRs | Approved architecture | Verifiable non-functional requirements (`NFR-nnn`) | Architect / security |
| 6 · Task plan | Architecture and NFRs | Dependency-ordered tasks with tests (`TASK`, `UT`, `FT`) | Engineering lead |
| 7 · Code | Task plan and architecture | Source code, tests and infrastructure code, built and tested by the pipeline | Engineering + code owners |
| 8 · Verify and release | Merged code | CI, security scans, DEV → STAGING (with DAST) → PRODUCTION | Release manager (mandatory) |

Table: Table 5.1 — Stages, artifacts and reviewers

## Inside one stage

Every stage follows the same governed pattern:

![Figure 3 — Anatomy of one stage: readiness, model choice, generation, quality control, human approval](diagrams/rendered/a03-stage-anatomy.png)

1. **Readiness check.** Is there enough information? If not, the issue is labelled *awaiting information* and the questions are posted. Answering in a comment resumes the stage automatically.
2. **Model recommendation.** The model router picks a model to match the task's complexity and explains why. For high-impact stages (BRD, PRD, Architecture, NFR, Code) a person confirms the choice with `/model approve`, or selects another model.
3. **Generation.** The specialised agent drafts the artifact against its contract, using the approved upstream artifacts.
4. **Quality control.** Deterministic checks (required sections, IDs, diagrams, build and tests for code) plus scoring by a *different* AI model. Below the threshold, the agent **revises its previous draft** using the reviewer's findings rather than starting over. After repeated failures the stage pauses and asks a person for guidance.
5. **Approval.** The artifact is committed to a pull request. A reviewer approves it, or comments to request changes, and the next stage starts automatically.

## End-to-end interaction

![Figure 4 — Interaction between people, GitHub, the orchestrator, the AI models and quality control](diagrams/rendered/25-agent-sequence.png)

## How people interact with AISDLC

| Action | How |
|---|---|
| Start a requirement | Create a GitHub issue describing the business problem, objective and stakeholders; add the label `sdlc:start` |
| Answer questions | Reply in the issue. The stage resumes automatically |
| Confirm or change the AI model | Comment `/model approve` or `/model select <model> <reason>` |
| Request a targeted change | Comment `/agent revise <notes>` on the stage pull request (also `regenerate`, `rerun-qc`, `explain`, `status`, `impact`) |
| Approve a stage | Approve the stage pull request |
| Release to production | Run the production workflow, type `promote`, and approve as the designated reviewer |

Table: Table 5.2 — Operating the platform

# The AI Agent Team {#agent-team}

| Agent | Role | Produces | Quality threshold | Human review |
|---|---|---|---|---|
| BRD Agent | Business analyst | Business problem, objectives, stakeholders, scope, requirements, acceptance criteria | 90 / 100 | Required |
| PRD Agent | Product manager | Functional and non-functional specification traced to the BRD | 90 / 100 | Required |
| Epic & Feature Agent | Product owner | Epics, features and user stories with acceptance criteria | 85 / 100 | Approval through PR |
| Architect Agent | Solution architect | Architecture document, Mermaid diagrams, components, security and deployment views | 90 / 100 | Required |
| NFR Agent | Quality engineer | Verifiable NFRs backed by the sources; open questions instead of invented targets | 88 / 100 | Approval through PR |
| Task Planning Agent | Engineering lead | Dependency-ordered tasks with unit and functional test tasks | 85 / 100 | Approval through PR |
| Engineer Agent | Software engineer | Source code, tests and infrastructure code; must build and pass tests in the pipeline | Build and tests must pass; score ≥ 60 (currently) | Required (code owners) |
| Quality Control | Independent reviewer | Scorecards, findings and recommendations for every artifact | — | — |
| Security, test and release functions | Scanners and pipelines | CodeQL, secret scanning, OWASP ZAP, CI tests, staged deployment, release evidence | Tool verdicts | Mandatory for production |

Table: Table 6.1 — The AI agent team (thresholds are configurable per stage)

Agent behaviour is defined in plain-language instruction files that your team can read, review and tailor. Changing an agent is a reviewed code change, not a hidden prompt.
