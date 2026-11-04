# SmartServe — Complete Solution Documentation

Customer-ready technical documentation for the **SmartServe** IT Service & Access Request Portal and the **Agentic SDLC** platform in this repository. It was generated from the source at commit `605e414`.

## Deliverables

| File | Description |
|---|---|
| `final/SmartServe-Complete-Application-Solution-Document.pdf` | Final document: 36 chapters, 30 figures, 50+ tables, bookmarks, page numbers |
| `final/SmartServe-Complete-Application-Solution-Document.html` | Self-contained HTML edition (images embedded) |
| `source/Complete-Application-Solution-Document.md` | Master Markdown, assembled from `source/chapters/*.md` |
| `source/document-metadata.yaml` | Cover, document control and revision history |
| `source/references.md` | Workspace and external references |
| `diagrams/mermaid/*.mmd` | 30 Mermaid diagram sources |
| `diagrams/rendered/*.svg`, `*.png` | Rendered diagrams (SVG + 2× PNG) |
| `analysis/` | Workspace analysis, component inventory, source-code mapping, assumptions, open questions, inspection log, validation report |
| `guides/` | Local development, deployment, operations runbook, troubleshooting, production readiness. These are extracted from the master document at build time |
| `tools/` | Build, validation and visual-QA scripts, HTML template, print CSS, Mermaid configuration |

## Regenerate

Prerequisites: Node.js 20+, Pandoc 3.x, and Google Chrome or Microsoft Edge (set `CHROME_PATH` to override detection).

```bash
cd docs/complete-solution-documentation/tools
PUPPETEER_SKIP_DOWNLOAD=true npm install   # once; uses the installed browser (PowerShell: $env:PUPPETEER_SKIP_DOWNLOAD="true"; npm install)
npm run build                              # diagrams → master Markdown → guides → HTML → PDF
npm run validate                           # writes analysis/documentation-validation.md
npm run qa -- <output-folder>              # optional print-mode screenshots for visual review
```

The toolchain is local to this folder and is not an application dependency. `node_modules/` is git-ignored.

## Editing

- **Content:** edit `source/chapters/*.md`. Chapters are concatenated in file-name order; level-1 headings become numbered chapters.
- **Diagrams:** edit `diagrams/mermaid/*.mmd`. The build re-renders only diagrams whose source has changed.
- **Status labels:** use `[IMPLEMENTED]{.badge .ok}`, `[PARTIAL]{.badge .partial}`, `[PLANNED]{.badge .planned}`, `[RECOMMENDED]{.badge .rec}`, `[NOT CONFIRMED]{.badge .nc}`.
- **Wide tables:** wrap them in `::: {.landscape}` … `:::` to print on landscape pages.
- **Secrets:** never paste real secrets, IDs or connection strings. Use placeholders such as `<TENANT_ID>`. `npm run validate` scans for leaks.
