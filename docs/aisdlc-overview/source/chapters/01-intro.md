# Executive Summary {#executive-summary}

**AISDLC (AI-Driven Software Development Lifecycle)** turns a business requirement into reviewed requirements, design, a delivery plan and working, tested code. It uses a team of specialised AI agents, each governed by automated quality controls and **human approval at every stage**. It runs entirely inside your GitHub repository, using GitHub Issues, Pull Requests, Actions and GitHub Copilot, and deploys to your cloud platform (Azure in the reference implementation).

**AISDLC in one paragraph.** A business user describes a need in a GitHub issue. AISDLC first checks that the description is complete enough to work with. If it is not, it asks for the missing details instead of guessing. It then drafts each standard delivery artifact in turn: Business Requirements (BRD), Product Requirements (PRD), Epics and User Stories, Architecture, Non-Functional Requirements (NFRs), a Task Plan, and finally Code with tests. Every draft is scored by an independent AI reviewer against configurable quality thresholds, revised if needed, and then submitted as a pull request for a human to approve. Only after approval does the next stage start. Everything is traceable: each requirement has a stable ID that can be followed from the original request to the code and the release.

## Why it matters

| Business need | How AISDLC responds |
|---|---|
| Faster path from idea to working software | Agents draft each artifact in minutes. People spend their time reviewing and deciding, not writing boilerplate |
| Consistent, complete documentation | Every artifact follows a defined contract (required sections, ID formats, traceability links) |
| Control and accountability | Humans approve every stage; production release always needs explicit approval |
| Compliance and auditability | Stable requirement IDs, PR history, decision logs and quality scores form an audit trail |
| Safe use of AI | AI output is checked by a second model, by deterministic rules, and by people; requirement text is treated as data, never as instructions |

Table: Table 1.1 — Value summary

## Proven on a real application

AISDLC was used to deliver **SmartServe**, an Enterprise IT Service & Access Request Portal (.NET 8 API, React, Azure SQL, Microsoft Entra ID, Azure App Service). From a single GitHub issue it produced:

- Business requirements, product requirements, epics and stories.
- Architecture, NFRs and a 16-task delivery plan.
- A 55-file implementation with tests and infrastructure code.

All seven stages were approved through pull requests #24 to #34. Chapter 11 has the details.

## What we ask of you

1. Provide a GitHub repository with Actions and GitHub Copilot access, and a cloud subscription for deployment.
2. Nominate reviewers for each stage: business (BRD/PRD), architecture, engineering and security.
3. Write requirements as GitHub issues, answer the platform's clarification questions, and review the stage pull requests.

# What is AISDLC? {#what-is-aisdlc}

AISDLC is a **governed, AI-assisted delivery pipeline** that lives in your source repository. It is made of four parts.

| Part | What it does | Where it lives |
|---|---|---|
| **Orchestrator** | Owns the workflow state. Decides which stage runs next, runs one stage per execution, and never skips a gate | Python control plane in the repository |
| **AI agents** | Specialists that each produce one artifact type (BRD, PRD, Epics, Architecture, NFR, Tasks, Code) | Agent definitions (instructions) in the repository; models served by GitHub Copilot |
| **Quality control and model router** | Scores every artifact independently; picks the right AI model for each task and explains why | Configuration files plus control-plane code |
| **GitHub workflows** | Run each stage, open pull requests, react to approvals and comments, and deploy | GitHub Actions |

Table: Table 2.1 — AISDLC building blocks

AISDLC **does not replace** your people, tools or governance. It is designed so that:

- the **orchestrator owns state**;
- **agents** only do specialised work;
- **quality control** evaluates;
- **humans** own every approval;
- the **model router** owns model selection;
- **GitHub Actions** runs everything.

Agents never call each other directly. Every hand-off goes through the orchestrator and a human-approved pull request.

![Figure 1 — From fragmented manual delivery to a governed AI-assisted lifecycle](diagrams/rendered/a01-why-aisdlc.png)

# Why AISDLC? {#why-aisdlc}

## The problem with traditional delivery

- **Requirements are scattered** across e-mail, meetings and chat. Assumptions creep in and are rarely recorded.
- **Documentation is slow and inconsistent.** Business analysts, architects and engineers each write in their own format, and documents drift out of date.
- **Hand-offs lose context.** Each role re-interprets the previous one's output; design intent does not reach the code.
- **Traceability is rebuilt by hand** for audits and change requests, so the impact of a change is hard to see.
- **Quality checks happen late.** Gaps are found in testing or production, where they are most expensive to fix.
- **Ad-hoc use of AI tools** speeds up individuals but adds risk: invented requirements, unreviewed code, no record of which model produced what.

## What AISDLC changes

| Challenge | AISDLC capability |
|---|---|
| Incomplete requirements | A **readiness gate** checks for the business problem, objective and stakeholders, and **asks** for anything missing; it does not invent it |
| Inconsistent artifacts | **Artifact contracts** define required sections, ID formats and upstream references for every stage |
| Context lost between roles | Each agent receives the **approved upstream artifacts** as its input, so design builds on agreed requirements |
| Late quality feedback | An **independent quality gate** after every stage, with configurable thresholds and automatic revision |
| Weak traceability | **Stable IDs** (`BRD-REQ`, `PRD-FR`, `US`, `ARCH-COMP`, `NFR`, `TASK`, …) link each item to its source |
| Uncontrolled AI use | **Human approval** at each stage, **model confirmation** for high-impact stages, and a **decision log** of model choices |
| Slow, risky releases | Deterministic CI, security scanning, staged deployment and a **mandatory production approval** |

Table: Table 3.1 — Challenges and capabilities

## Who benefits

- **Business sponsors:** faster turnaround from idea to reviewable solution, with clear status at every stage.
- **Product owners and analysts:** structured first drafts to refine instead of blank pages; open questions surfaced early.
- **Architects:** consistent architecture documents that trace to requirements; "proposed" design choices are clearly labelled.
- **Engineering:** a dependency-ordered task plan and a first implementation with tests, built and tested by the pipeline before review.
- **Security and compliance:** an audit trail of decisions, reviewers, quality scores and releases, plus built-in security scanning.
