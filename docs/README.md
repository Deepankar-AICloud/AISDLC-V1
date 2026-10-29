# SmartServe SDLC Artifacts

Generated Agentic SDLC artifacts live here, one subfolder per stage. Each
artifact carries stable traceability IDs so requirements can be followed from
intake to production.

| Folder | Stage | ID prefix |
|---|---|---|
| `brd/` | Business Requirements | `BRD-REQ-NNN` |
| `prd/` | Product/Functional Requirements | `PRD-FR-NNN` |
| `epic/` | Epics / Features / Stories | `EPIC-/FEATURE-/US-NNN` |
| `architecture/` | HLD / LLD | `ARCH-COMP-NNN` |
| `nfr/` | Non-Functional Requirements | `NFR-NNN` |
| `tasks/` | Development tasks | `TASK-NNN` |
| `security/` | Security findings & reports | `SEC-NNN` |

Traceability chain:
`REQ → BRD-REQ → PRD-FR → EPIC → FEATURE → US → ARCH-COMP → TASK → CODE → UT → FT → SEC → RELEASE`

Artifacts are produced by the orchestrator (`scripts/sdlc/run.py`), evaluated by
QC (`scripts/sdlc/quality`), and reviewed by humans via stage PRs before the
workflow advances.
