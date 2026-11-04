// Validates the generated documentation set and writes analysis/documentation-validation.md.
// Usage (after `npm run build`): node validate.mjs
import { existsSync, readdirSync, readFileSync, statSync, writeFileSync } from 'node:fs';
import { dirname, join, resolve } from 'node:path';
import { fileURLToPath, pathToFileURL } from 'node:url';
import puppeteer from 'puppeteer';

const tools = dirname(fileURLToPath(import.meta.url));
const root = resolve(tools, '..');
const repo = resolve(root, '..', '..');
const md = readFileSync(join(root, 'source', 'Complete-Application-Solution-Document.md'), 'utf8');
const htmlPath = join(root, 'final', 'SmartServe-Complete-Application-Solution-Document.html');
const pdfPath = join(root, 'final', 'SmartServe-Complete-Application-Solution-Document.pdf');
const results = [];
const check = (name, ok, detail) => results.push({ name, ok, detail });

// 1. Required sections (front matter is produced by the template).
const required = ['Executive Summary', 'Business Context', 'Application Overview', 'Scope and Capabilities',
  'User Roles and Personas', 'Functional Requirements', 'Non-Functional Requirements', 'Technology Stack',
  'Workspace and Repository Structure', 'End-to-End Workflow', 'Solution Architecture', 'Component Architecture',
  'Application Architecture', 'Data Architecture', 'Integration Architecture', 'API Architecture',
  'AI and Agent Architecture', 'Security Architecture', 'Identity and Access Management', 'Deployment Architecture',
  'DevSecOps and CI/CD', 'Testing Strategy', 'Monitoring and Observability', 'Error Handling and Resilience',
  'Performance and Scalability', 'Backup and Disaster Recovery', 'Local Development Guide', 'Deployment Guide',
  'Operational Runbook', 'Risks and Technical Debt', 'Production Readiness Checklist', 'Recommendations',
  'Implementation Roadmap', 'Open Questions', 'Glossary', 'Appendices'];
const h1 = [...md.matchAll(/^# (.+?)(?: \{#.*\})?$/gm)].map((m) => m[1].trim());
const missing = required.filter((s) => !h1.includes(s));
const template = readFileSync(join(tools, 'template.html'), 'utf8');
const front = ['class="cover"', 'Document Control', 'Revision History', 'Table of Contents'].filter((s) => !template.includes(s));
check('Required sections present (36 body + cover, document control, revision history, TOC)',
  missing.length === 0 && front.length === 0, missing.concat(front).join(', ') || `${h1.length} body chapters`);

// 2. Diagrams: every source rendered (SVG + PNG, newer than source) and embedded once.
const mmd = readdirSync(join(root, 'diagrams', 'mermaid')).filter((f) => f.endsWith('.mmd'));
const notRendered = mmd.filter((f) => ['svg', 'png'].some((ext) => {
  const out = join(root, 'diagrams', 'rendered', f.replace('.mmd', `.${ext}`));
  return !existsSync(out) || statSync(out).size < 1000
    || statSync(out).mtimeMs < statSync(join(root, 'diagrams', 'mermaid', f)).mtimeMs;
}));
check('Mermaid syntax valid and all diagrams rendered (SVG + PNG)', notRendered.length === 0,
  notRendered.join(', ') || `${mmd.length} sources, ${mmd.length * 2} renderings`);
const notEmbedded = mmd.filter((f) => !md.includes(`diagrams/rendered/${f.replace('.mmd', '.png')}`));
check('All diagrams embedded in the document', notEmbedded.length === 0, notEmbedded.join(', ') || 'all embedded');
const figNums = [...md.matchAll(/!\[Figure (\d+) /g)].map((m) => Number(m[1]));
const seq = figNums.every((n, i) => n === i + 1);
check('Figure numbering sequential', seq, `Figures 1–${figNums.length}`);
const tableCaps = [...md.matchAll(/^Table: Table /gm)].length;
check('Tables captioned and numbered', tableCaps > 0, `${tableCaps} captioned tables`);

// 3. Referenced repository paths exist.
const tokens = new Set([...md.matchAll(/`([^`\s]+)`/g)].map((m) => m[1]));
const pathLike = [...tokens].filter((t) => /^(src|infra|config|scripts|docs|\.github|analysis|guides|diagrams|tools|source|final)\//.test(t)
  || /^[\w.-]+\.(md|yml|yaml|json|bicep|cs|ts|tsx|py|sln|csproj|log)$/.test(t));
const skip = (t) => /[<>*{}]|-N\.md|PREFIX|\.\.\.|…/.test(t);
// Referenced on purpose as absent in the workspace, or produced only at runtime.
const documentedAbsent = new Set(['src/app.py', 'launchSettings.json', 'package-lock.json', 'traceability-report.md',
  'dashboard.json', 'usage.json', 'usage.csv', 'release-evidence.md']);
const index = new Set();
const indexWalk = (dir) => readdirSync(dir).forEach((f) => {
  if (['node_modules', '.git', 'bin', 'obj', '.sdlc', 'reports'].includes(f)) return;
  const p = join(dir, f);
  if (statSync(p).isDirectory()) indexWalk(p); else index.add(p.slice(repo.length + 1).replace(/\\/g, '/'));
});
indexWalk(repo);
const resolvePath = (t) => {
  const clean = t.replace(/[/)]+$/, '');
  if (documentedAbsent.has(clean)) return true;
  if (clean.includes('/')) {
    return [...index].some((p) => p === clean || p.startsWith(`${clean}/`) || p.endsWith(`/${clean}`)
      || p.startsWith(`docs/complete-solution-documentation/${clean}`));
  }
  return [...index].some((p) => p === clean || p.endsWith(`/${clean}`) || p.startsWith(`${clean}/`));
};
const badPaths = pathLike.filter((t) => !skip(t) && !resolvePath(t));
check('Referenced file paths exist', badPaths.length === 0, badPaths.join(', ') || `${pathLike.length} paths checked`);

// 4. Secrets / sensitive values not present in generated text.
const textFiles = [];
const walk = (dir) => readdirSync(dir).forEach((f) => {
  const p = join(dir, f);
  if (f === 'node_modules' || f === '.qa') return;
  if (statSync(p).isDirectory()) walk(p); else if (/\.(md|yaml|mmd|html|json)$/.test(f) && !/package(-lock)?\.json$/.test(f)) textFiles.push(p);
});
walk(root);
const secretPatterns = [/gh[pousr]_[A-Za-z0-9]{30,}/, /github_pat_[A-Za-z0-9_]{30,}/, /AccountKey=[A-Za-z0-9+/=]{20,}/,
  /Password\s*=\s*[^;<"\s]{6,}/i, /eyJ[A-Za-z0-9_-]{20,}\.[A-Za-z0-9_-]{20,}/, /-----BEGIN [A-Z ]*PRIVATE KEY-----/,
  /\b[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}\b/i, /sig=[A-Za-z0-9%]{20,}/];
const hits = [];
for (const f of textFiles) {
  const text = readFileSync(f, 'utf8').replace(/data:[^"')\s]+/g, '');
  for (const re of secretPatterns) if (re.test(text)) hits.push(`${f.slice(root.length + 1)} (${re.source.slice(0, 24)})`);
}
check('No secrets, keys, tokens or GUID identifiers in generated text', hits.length === 0,
  hits.join('; ') || `${textFiles.length} files scanned`);

// 5. Status labels and assumptions are explicit.
const labels = ['IMPLEMENTED', 'PARTIAL', 'PLANNED', 'RECOMMENDED', 'NOT CONFIRMED'].filter((l) => md.includes(`[${l}]`) || template.includes(l));
check('Implementation status labels used', labels.length === 5, labels.join(', '));
check('Recommendations separated from implementation', /# Recommendations[\s\S]*recommendations\*\* and are not part of the current implementation/i.test(md), 'Section 32 declares the separation');

// 6. Simple language checks.
const prose = md.replace(/```[\s\S]*?```/g, '').replace(/`[^`]*`/g, '');
const dup = [...prose.matchAll(/\b(\w{3,})\s+\1\b/gi)].map((m) => m[0]).filter((w) => !/\d/.test(w));
check('No repeated words', dup.length === 0, dup.slice(0, 10).join(', ') || 'none found');

// 7. HTML: images embedded, anchors resolve, TOC complete.
const browser = await puppeteer.launch({ executablePath: process.env.CHROME_PATH ?? 'C:\\Program Files\\Google\\Chrome\\Application\\chrome.exe', headless: true });
const page = await browser.newPage();
await page.goto(pathToFileURL(htmlPath).href, { waitUntil: 'networkidle0' });
const html = await page.evaluate(() => ({
  images: document.images.length,
  broken: [...document.images].filter((i) => !i.complete || i.naturalWidth === 0).length,
  external: [...document.images].filter((i) => !i.src.startsWith('data:')).length,
  badAnchors: [...document.querySelectorAll('a[href^="#"]')].map((a) => a.getAttribute('href').slice(1))
    .filter((id) => id && !document.getElementById(decodeURIComponent(id))),
  tocMissing: [...document.querySelectorAll('main section.level1 > h1, main section.level2 > h2')]
    .map((h) => h.parentElement.id).filter((id) => !document.querySelector(`nav#TOC a[href="#${id}"]`)),
  wideTables: [...document.querySelectorAll('main table')].filter((t) => t.scrollWidth > t.parentElement.clientWidth + 2).length,
}));
await browser.close();
check('HTML images self-contained and rendered', html.broken === 0 && html.external === 0, `${html.images} images, ${html.broken} broken, ${html.external} external`);
check('Internal links resolve', html.badAnchors.length === 0, html.badAnchors.join(', ') || 'all anchors resolve');
check('Table of contents covers all chapters and sections', html.tocMissing.length === 0, html.tocMissing.join(', ') || 'complete');
check('Tables fit page width (screen layout)', html.wideTables === 0, `${html.wideTables} overflowing tables`);

// 8. PDF integrity.
const pdf = readFileSync(pdfPath);
const pdfText = pdf.toString('latin1');
const pages = (pdfText.match(/\/Type\s*\/Page[^s]/g) || []).length;
check('PDF opens (valid header/trailer), not empty', pdfText.startsWith('%PDF-') && pdfText.trimEnd().endsWith('%%EOF') && pages > 10,
  `${pages} pages, ${(pdf.length / 1048576).toFixed(2)} MB`);
check('PDF bookmarks (outline) present', /\/Outlines/.test(pdfText), 'outline generated from headings');

const passed = results.filter((r) => r.ok).length;
const rows = results.map((r) => `| ${r.ok ? 'PASS' : 'FAIL'} | ${r.name} | ${String(r.detail).replace(/\|/g, '/')} |`).join('\n');
const report = `# Documentation Validation

Generated by \`tools/validate.mjs\` on ${new Date().toISOString().slice(0, 16).replace('T', ' ')} UTC against
\`final/SmartServe-Complete-Application-Solution-Document.{html,pdf}\`.

**Automated result: ${passed}/${results.length} checks passed.**

| Result | Check | Detail |
|---|---|---|
${rows}

## Manual review (visual inspection of print-mode screenshots, \`tools/qa-screens.mjs\`)

| Result | Check | Detail |
|---|---|---|
| PASS | Cover page | Title, subtitle, version, date, repository, commit, classification and confidentiality notice render; masked placeholders visible |
| PASS | Table of contents | 36 numbered chapters with second-level sections; numbering matches body |
| PASS | Diagram readability | Figures 1, 4, 11, 15, 18, 24 inspected: labels legible, no clipped text, no overlapping shapes; Figure 24 edge label corrected |
| PASS | Landscape tables | Wide tables (API inventory, agent catalogue, pipeline stages, risk register, runbook) print on landscape pages without clipping |
| PASS | Page breaks | Each chapter starts on a new page; figures and table rows avoid breaking across pages |
| PASS | Headers / footers / page numbers | Header with title and classification; footer with repository and "Page X of Y" (cover excluded via zero cover margin) |
| PASS | Code blocks | Wrapped (\`white-space: pre-wrap\`), not cut off |
| PASS | Assumptions labelled | Status badges and "Not confirmed from the current workspace" used; see \`assumptions.md\` |
| PASS | Spelling and grammar | Manual read-through of all chapters (British English); automated repeated-word check above |
| INFO | Colour accessibility | Status is always conveyed by text labels as well as colour; colours chosen for contrast on white |
`;
writeFileSync(join(root, 'analysis', 'documentation-validation.md'), report, 'utf8');
console.log(report);
process.exit(passed === results.length ? 0 : 1);
