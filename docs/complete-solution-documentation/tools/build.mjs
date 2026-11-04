// Builds a document folder: Mermaid -> SVG/PNG, Markdown -> HTML (Pandoc), HTML -> PDF (Chrome).
// Usage (from docs/complete-solution-documentation/tools):  npm run build  |  node build.mjs <documentFolder>
import { execFileSync } from 'node:child_process';
import { existsSync, mkdirSync, readdirSync, readFileSync, statSync, writeFileSync } from 'node:fs';
import { dirname, join, resolve } from 'node:path';
import { fileURLToPath, pathToFileURL } from 'node:url';
import puppeteer from 'puppeteer';

const tools = dirname(fileURLToPath(import.meta.url));
const solutionRoot = resolve(tools, '..');
const root = process.argv[2] ? resolve(process.argv[2]) : solutionRoot;
const mermaidDir = join(root, 'diagrams', 'mermaid');
const renderedDir = join(root, 'diagrams', 'rendered');
const metadata = join(root, 'source', 'document-metadata.yaml');
const meta = (key, fallback) => readFileSync(metadata, 'utf8').match(new RegExp(`^${key}:\\s*"?(.+?)"?\\s*$`, 'm'))?.[1] ?? fallback;
const outputName = meta('output-name', 'SmartServe-Complete-Application-Solution-Document');
const pdfHeader = meta('pdf-header', 'SmartServe — Complete Application Solution Document');
const sourceMd = join(root, 'source', `${meta('source-name', 'Complete-Application-Solution-Document')}.md`);
const finalDir = join(root, 'final');
const htmlOut = join(finalDir, `${outputName}.html`);
const pdfOut = join(finalDir, `${outputName}.pdf`);
const isWin = process.platform === 'win32';
const mmdc = join(tools, 'node_modules', '@mermaid-js', 'mermaid-cli', 'src', 'cli.js');
const chrome = process.env.CHROME_PATH
  ?? ['C:\\Program Files\\Google\\Chrome\\Application\\chrome.exe',
      'C:\\Program Files (x86)\\Microsoft\\Edge\\Application\\msedge.exe',
      '/usr/bin/google-chrome', '/usr/bin/chromium'].find(existsSync);

mkdirSync(renderedDir, { recursive: true });
mkdirSync(finalDir, { recursive: true });

// 1. Render diagrams (skip when the output is newer than the source).
const sources = readdirSync(mermaidDir).filter((f) => f.endsWith('.mmd')).sort();
for (const file of sources) {
  const src = join(mermaidDir, file);
  for (const ext of ['svg', 'png']) {
    const out = join(renderedDir, file.replace(/\.mmd$/, `.${ext}`));
    if (existsSync(out) && statSync(out).mtimeMs > statSync(src).mtimeMs) continue;
    const args = ['-i', src, '-o', out, '-p', join(tools, 'puppeteer-config.json'),
      '-c', join(tools, 'mermaid-config.json'), '-b', 'white', '-w', '1400'];
    if (ext === 'png') args.push('-s', '2');
    execFileSync(process.execPath, [mmdc, ...args], { stdio: 'inherit' });
  }
}
console.log(`Rendered ${sources.length} diagrams (SVG + PNG).`);

// 2a. Assemble the master Markdown from ordered chapter files.
const chaptersDir = join(root, 'source', 'chapters');
const chapters = readdirSync(chaptersDir).filter((f) => f.endsWith('.md')).sort();
writeFileSync(sourceMd, chapters.map((f) => readFileSync(join(chaptersDir, f), 'utf8').trim()).join('\n\n') + '\n', 'utf8');
console.log(`Master Markdown assembled from ${chapters.length} chapters: ${sourceMd}`);

// 2b. Guides (solution document only) are extracted from the master Markdown so they never diverge from the PDF.
const master = readFileSync(sourceMd, 'utf8');
const section = (id) => {
  const m = master.match(new RegExp(`^# [^\\n]*\\{#${id}\\}[\\s\\S]*?(?=^# |(?![\\s\\S]))`, 'm'));
  if (!m) throw new Error(`Section {#${id}} not found for guide extraction`);
  return m[0].replace(/\]\(diagrams\//g, '](../diagrams/').replace(/^:::.*\n?/gm, '').trim();
};
const guides = {
  'local-development-guide.md': ['local-development-guide'],
  'deployment-guide.md': ['deployment-guide'],
  'operations-runbook.md': ['operational-runbook'],
  'troubleshooting-guide.md': ['error-handling-resilience', 'operational-runbook'],
  'production-readiness-checklist.md': ['production-readiness'],
};
if (root === solutionRoot) mkdirSync(join(root, 'guides'), { recursive: true });
for (const [file, ids] of root === solutionRoot ? Object.entries(guides) : []) {
  const banner = '> Extracted from `source/Complete-Application-Solution-Document.md` by `tools/build.mjs`. Edit the chapter files, not this file.\n\n';
  writeFileSync(join(root, 'guides', file), banner + ids.map(section).join('\n\n') + '\n', 'utf8');
}
console.log(`Guides written: ${root === solutionRoot ? Object.keys(guides).length : 0}`);

// 2c. Markdown -> standalone, self-contained HTML.
execFileSync('pandoc', [
  sourceMd, '--metadata-file', metadata,
  '--from', 'markdown+pipe_tables+grid_tables+implicit_figures+fenced_divs+bracketed_spans',
  '--to', 'html5', '--standalone', '--template', join(tools, 'template.html'),
  '--toc', '--toc-depth=2', '--number-sections', '--section-divs',
  '--css', join(tools, 'style.css'), '--embed-resources',
  '--resource-path', [join(root, 'source'), root, solutionRoot].join(isWin ? ';' : ':'),
  '--output', htmlOut,
], { stdio: 'inherit' });
console.log(`HTML written: ${htmlOut}`);

// 3. HTML -> PDF with header/footer, page numbers and bookmarks.
const browser = await puppeteer.launch({ executablePath: chrome, headless: true, args: ['--no-sandbox'] });
const page = await browser.newPage();
await page.goto(pathToFileURL(htmlOut).href, { waitUntil: 'networkidle0' });
const small = 'font-family:Segoe UI,Arial,sans-serif;font-size:7.5pt;color:#505050;width:100%;padding:0 16mm;';
await page.pdf({
  path: pdfOut,
  format: 'A4',
  printBackground: true,
  preferCSSPageSize: true,
  displayHeaderFooter: true,
  headerTemplate: `<div style="${small}display:flex;justify-content:space-between;"><span>${pdfHeader}</span><span>Confidential — internal &amp; customer use</span></div>`,
  footerTemplate: `<div style="${small}display:flex;justify-content:space-between;"><span>Generated from repository AISDLC-V1</span><span>Page <span class="pageNumber"></span> of <span class="totalPages"></span></span></div>`,
  outline: true,
  tagged: true,
});
await browser.close();
console.log(`PDF written: ${pdfOut} (${statSync(pdfOut).size} bytes)`);
