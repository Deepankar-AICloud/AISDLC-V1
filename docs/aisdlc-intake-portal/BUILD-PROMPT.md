# Prompt: Build the AISDLC Intake and Review Portal

Copy everything below the line into Claude (Claude Code works best, opened in the AISDLC repository).

---

You are a senior full-stack engineer. Build a web application called **AISDLC Portal**. A business user pastes a requirement and uploads supporting documents. On **Submit**, the backend hands the requirement to the existing AISDLC pipeline in GitHub. The same portal lets the right people **answer questions, review and approve** each stage without leaving the app. The portal does not re-implement AISDLC; it is the front door and the review desk for it.

## 1. Background: how AISDLC works today

Read these first so you build against reality, not assumptions:

- `README.md` (sections "Trigger", "Run the orchestrator locally", "Traceability")
- `.github/workflows/agentic-sdlc-codeql-gate.yml`, `agentic-sdlc.yml`, `artifact-review.yml`, `feedback-handler.yml`, `deploy-production.yml`
- `.github/CODEOWNERS`
- `scripts/sdlc/orchestrator/` (how requirement context is collected from the issue and comments)
- `config/` (readiness rules, quality gates, agents, environments)

Facts I already know (verify each in the code and tell me if anything differs):

- A requirement starts as a **GitHub issue** with the label **`sdlc:start`**. The label event triggers the pipeline.
- The issue must cover: business problem, objective, stakeholders, scope, constraints. A readiness gate checks this. If information is missing, the orchestrator adds `sdlc:awaiting-info` and asks questions. A **human issue comment** answering them resumes the run.
- The workflow treats a comment as human unless its author login is `github-actions` or `github-actions[bot]`. It does **not** check who a human is. A different bot or service account would be accepted as "human".
- A CodeQL gate on the current `main` commit must pass before a run starts.
- Each run advances one stage (BRD, PRD, Epics, Architecture, NFR, Task plan, Code), opens a stage pull request on a branch named `sdlc/issue-*`, and waits for human approval.
- `artifact-review.yml` fires on **any approved review** of a PR whose branch starts with `sdlc/issue-`. It marks the stage approved, **merges the PR** and starts the next stage. It does not check the approver. **Branch protection and CODEOWNERS are the real control** over who may approve.
- Production release uses a protected GitHub environment with required reviewers and an explicit confirmation.
- Issue and comment text is treated as **untrusted data, never instructions**.
- Safe commands in comments: `/agent revise|regenerate|rerun-qc|explain|status|impact`, `/model approve|select <model> <reason>`.

## 2. What users can do

1. **Enter requirement context** by pasting text into a large text area.
2. **Upload documents** by drag-and-drop or file picker, several at once: PDF, DOCX, PPTX, XLSX, CSV, TXT, MD, HTML, RTF. Images (PNG/JPG) are optional via OCR; make this a feature flag, off by default.
3. **Optionally fill structured fields**: title, business problem, objective, stakeholders, scope, constraints, target repository. Show inline guidance that mirrors the readiness gate and a completeness hint (not a block). Missing items are fine; AISDLC asks for them.
4. **Preview before sending**: show the extracted text per file (collapsible) with page or slide counts and extraction warnings, plus the final issue body that will be created. The user can remove a file or edit the text.
5. **Submit**, then see a **status page** for the request: link to the GitHub issue, labels, current stage, stage PR links, QC scores, and a clear state when AISDLC is asking for more information.
6. **Answer AISDLC's questions** (`sdlc:awaiting-info`) in the portal. The answer is posted as a GitHub issue comment that resumes the run.
7. **Review a stage** in the portal: show the artifact (rendered Markdown with diagrams), the PR diff, the QC scorecard and findings, and the model decision. Offer these actions:
   - **Approve** (this merges the PR and starts the next stage)
   - **Request changes** (posted as `/agent revise <notes>`)
   - **Confirm or change the model** (`/model approve` or `/model select <model> <reason>`)
   - Other safe commands: `regenerate`, `rerun-qc`, `explain`, `status`, `impact`
8. **Approve a production release** from the portal, only for users who are required reviewers of the `production` environment (see section 5).
9. See a **history list**: requesters see their own requests, reviewers see the requests they are assigned to.

## 3. What happens on Submit (backend)

1. Validate the request, authenticate the user, check authorisation, and compute an **idempotency key** so a double-click never creates two issues.
2. For each file: validate type by extension **and** magic bytes, enforce size and page limits, extract text and structure (headings, tables, slide titles and notes), and record warnings (scanned PDF with no text layer, password-protected file, empty extraction).
3. Build the **issue body** with fixed sections: `Business problem`, `Objective`, `Stakeholders`, `Scope`, `Constraints`, `Pasted requirement text`, `Source documents` (one subsection per file with extracted text), `Submitted by` and `Request ID`. Wrap pasted and extracted content in clearly labelled **untrusted source material** blocks.
4. GitHub limits an issue body to 65,536 characters. Design the overflow strategy after reading how the orchestrator collects context. Options to evaluate and pick one, and tell me why: split across follow-up human-authored comments, or commit full extracted Markdown and the originals to a non-`main` branch and link them. **Do not commit to `main`**, because that would restart the CodeQL gate and create unwanted intake issues.
5. Create the issue **first**, then add the **`sdlc:start`** label as a separate final call, so the pipeline starts only after all content is in place. This step uses the service identity (section 4).
6. Store a request record (ID, user, issue number, timestamps, file metadata, status) in a database. Do not store document contents beyond what the retention policy needs.
7. A background poller (or webhook receiver) updates status from GitHub: labels, workflow runs, PRs, reviews, deployments. Prefer webhooks with a polling fallback.

## 4. Technical decisions (default unless I say otherwise)

- **Backend:** Python 3.12 with FastAPI. Python has the best document libraries (`pypdf` or `pdfplumber`, `python-docx`, `python-pptx`, `openpyxl`, `beautifulsoup4`) and matches the AISDLC control plane.
- **Frontend:** React and TypeScript with Vite. Accessible, responsive, mobile-friendly.
- **Database:** SQLite for local development, PostgreSQL or Azure SQL for deployment, behind a repository layer.
- **Portal sign-in:** Microsoft Entra ID (OIDC) with **server-side** authorisation. Portal roles: `Requester` (own requests) and `Reviewer` (assigned requests). Provide a dev-mode auth bypass that is impossible to enable in production.
- **GitHub access: two kinds of token, never mixed.** Use one **GitHub App**.
  - **Service identity (installation token):** only for creating the intake issue, adding `sdlc:start`, uploading overflow content, and reading status. Never for comments that answer questions, reviews, approvals or approval commands.
  - **User identity (GitHub App user access token):** each user clicks **Connect GitHub** (OAuth web flow) once. Every comment, review, approval and `/agent` or `/model` command is made with that user's own token. Store tokens encrypted, keep them short-lived with refresh tokens, and request the minimum permissions.
- **Deployment target:** Azure App Service (reference), Dockerfile included, secrets from environment or Key Vault, health endpoint.
- Create everything in a new folder `apps/intake-portal/`. **Do not modify** existing AISDLC workflows, agents, config or the `src/` application.

## 5. Acting on behalf of users: comments, review and approval

This is the most sensitive part. Human approval must stay human.

**Rules**

1. **Act as the real user.** Comments, reviews, approvals and commands are sent with the signed-in user's own GitHub token so GitHub shows their real name and applies branch protection and CODEOWNERS normally. **Never** use the service identity or any shared account for these. A portal bot comment would be accepted as "human" by the workflow, so this rule is what keeps the gate honest.
2. **Identity mapping.** Map each Entra ID user to exactly one GitHub account, verified by the OAuth connect step. Block the action if the Entra user and the connected GitHub account are not linked, and show why.
3. **Permission pre-check before showing a button.** For each PR and user, check via the GitHub API: the user has write access, is a matching CODEOWNER for the changed paths, is not the PR author, and satisfies the branch-protection rules. Show "Approve" only when it would succeed. Explain clearly when it is hidden. **GitHub stays the authority**: if GitHub rejects the call, show the exact reason and do not retry with another identity.
4. **Informed approval.** Show the artifact, diff, QC scorecard and findings beside the button. Use a confirmation dialog that says the approval **merges the PR and starts the next stage**. No bulk approve, no auto-approve, no approve-by-default.
5. **Request changes** posts `/agent revise <notes>` as the user. Do not let free text change the command. Allow only the allowlisted commands.
6. **Production approval.** Only a user who is a required reviewer of the `production` environment can approve, using the deployment-review API with their own token. Require typed confirmation (for example the word `promote`) and show the release evidence (CI, scans, STAGING and DAST results). Never allow a service identity to approve production.
7. **Optional separation of duties policy** (configurable, off by default): the requester of a requirement cannot approve the BRD or PRD for it.
8. **Audit log** for every action: who (Entra ID and GitHub login), what, which PR or issue, when, GitHub response code, and the portal request ID. Do not log token values.
9. **Failure handling:** expired or revoked token (prompt to reconnect), rate limits (retry with backoff, never switch identity), GitHub conflicts (PR already merged, review already submitted), and branch-protection rejections.

**Discovery tasks for this section.** Read `artifact-review.yml`, `feedback-handler.yml`, `deploy-production.yml` and `CODEOWNERS`, and tell me: whether CODEOWNERS contains placeholder teams (it appears to use `@smartserve/*`), whether branch protection actually requires reviews, how the production environment's reviewers are set up, and whether the comment and command handlers restrict who may issue `/model` and `/agent` commands. If protections are missing, list what must be configured in GitHub for this portal to be safe.

## 6. Security requirements (treat as acceptance criteria)

- Uploaded content is **untrusted data**. Never execute macros, scripts or embedded objects. Strip hidden text, comments and metadata where feasible, and flag likely prompt-injection phrases (for example "ignore previous instructions") for the user without silently altering meaning.
- Enforce a file-type allowlist, per-file and total size caps, page and slide caps, ZIP and decompression-bomb limits, and extraction timeouts. Run extraction in a bounded worker.
- Provide a pluggable **malware-scan hook** (no-op by default, documented).
- CSRF protection, strict CORS, security headers, rate limiting per user, request-size limits.
- GitHub tokens (service and user) are **server-side only**. They never reach the browser, logs, error messages or the frontend bundle.
- Do not log document content or tokens. Redact secrets in logs.
- Show a visible notice: do not upload secrets, credentials or regulated personal data unless approved for this repository.
- Dependency pinning and a CI step for dependency and secret scanning.

## 7. Quality requirements

- Tests: unit tests for every extractor (include sample files and malformed, encrypted, empty and oversized cases), the issue-body builder (including truncation and overflow), idempotency, authorisation, the permission pre-check, and the identity rules in section 5. API integration tests with the GitHub API **mocked**. A Playwright end-to-end test for paste, upload, preview, submit, answer a question, and review and approve (mocked GitHub).
- Typed code, linting, formatting, and a CI workflow for the portal that runs tests and scans.
- Accessible UI (keyboard operable, labelled, sufficient contrast), clear error messages, and loading, empty and failure states for every screen.
- Structured logging, a correlation ID per request, and a `/healthz` endpoint.

## 8. How to work

1. **Discovery first.** Read the files listed in sections 1 and 5, then write a short design note covering: how context is collected from issues and comments (including bot and author filtering), the overflow strategy, the data model, the API surface, the two-token model, the identity-mapping approach, and the folder layout. List every assumption you could not verify and every missing GitHub protection. **Wait for my approval before writing code.**
2. If something blocks you (target repository, Entra tenant, GitHub App details, whether Entra users map to GitHub accounts), ask me at most **three** focused questions. Otherwise use the defaults above and say so.
3. Build in small increments, in this order: backend skeleton and extractors, issue builder and service GitHub client, status tracking, frontend intake, Entra sign-in, GitHub connect and user-token client, review and approval, production approval, hardening, CI, docs. Run tests after each increment.
4. **Never trigger a real AISDLC run, approve a real PR or approve a real deployment** against my production repository. Use a test repository, or the mocked client, until I confirm.
5. Never commit secrets. Provide `.env.example` with every variable documented.

## 9. Deliverables

- Working app in `apps/intake-portal/` with `README.md` (setup, GitHub App creation steps and permissions, Entra app registration, environment variables, deployment to Azure App Service, how the flow maps to AISDLC, and the GitHub protections required).
- A `docs/` note covering architecture, data flow diagram (Mermaid), the two-token and identity model, threat model summary, and the overflow decision.
- Test suite, CI workflow, Dockerfile.
- A final report: what was built, what was verified (with test output), what was not verified, and known limitations.

## 10. Acceptance criteria

- Paste text plus upload a PDF, DOCX and PPTX, then Submit. A GitHub issue appears with all sections filled, extracted text included, and the `sdlc:start` label added **after** the content. (Verified against a test repo or the mocked client.)
- Submitting twice quickly creates **one** issue.
- A 200-page document is handled by the overflow strategy without losing content or breaking the 65,536-character limit.
- An encrypted PDF, a corrupt DOCX and an oversized file each give a clear, non-crashing error.
- A user cannot see or act on another user's request.
- No GitHub token appears in any browser-visible response, log or bundle.
- When AISDLC adds `sdlc:awaiting-info`, the status page shows the questions, and the user's answer is posted **as that user** and resumes the run.
- Approving a stage PR shows the artifact, diff and QC scorecard, requires confirmation, and the review appears on GitHub under the **user's own GitHub login**, not a service account.
- A user who is not a code owner, or who is the PR author, or who lacks write access, does not get an Approve button, and a forced API call is rejected with GitHub's reason.
- No code path uses the service token to comment, review, approve or run `/agent` or `/model` commands (covered by a test).
- Production approval is available only to required reviewers of the `production` environment, needs typed confirmation, and is never performed by a service identity.
- Every comment, review and approval has an audit-log entry with the user, target, time and result.
