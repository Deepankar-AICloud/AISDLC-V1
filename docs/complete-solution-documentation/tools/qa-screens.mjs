// Visual QA: screenshots of key document regions rendered with print media at A4 width.
// Usage: node qa-screens.mjs <outDir>
import { mkdirSync } from 'node:fs';
import { dirname, join, resolve } from 'node:path';
import { fileURLToPath, pathToFileURL } from 'node:url';
import puppeteer from 'puppeteer';

const tools = dirname(fileURLToPath(import.meta.url));
const html = process.env.HTML_PATH
  ? resolve(process.env.HTML_PATH)
  : resolve(tools, '..', 'final', 'SmartServe-Complete-Application-Solution-Document.html');
const out = resolve(process.argv[2] ?? join(tools, '..', '.qa'));
mkdirSync(out, { recursive: true });
const chrome = process.env.CHROME_PATH ?? 'C:\\Program Files\\Google\\Chrome\\Application\\chrome.exe';

const browser = await puppeteer.launch({ executablePath: chrome, headless: true });
const page = await browser.newPage();
await page.setViewport({ width: 794, height: 1123, deviceScaleFactor: 1.5 }); // A4 @96dpi
await page.emulateMediaType('print');
await page.goto(pathToFileURL(html).href, { waitUntil: 'networkidle0' });

const shots = {
  cover: 'section.cover',
  toc: 'nav.toc',
  fig04: 'figure:has(img[src*="04-business"]), figure:nth-of-type(1)',
};
for (const [name, sel] of Object.entries(shots)) {
  const el = await page.$(sel);
  if (el) await el.screenshot({ path: join(out, `${name}.png`) });
}
const figures = await page.$$('figure');
const pick = process.env.ALL_FIGURES ? figures.map((_, i) => i) : [0, 3, 10, 14, 17, 23];
for (const i of pick) {
  if (figures[i]) await figures[i].screenshot({ path: join(out, `figure-${String(i + 1).padStart(2, '0')}.png`) });
}
const wide = await page.$$('div.landscape table');
if (wide[0]) await wide[0].screenshot({ path: join(out, 'landscape-table-1.png') });
const stats = await page.evaluate(() => ({
  figures: document.querySelectorAll('figure').length,
  brokenImages: [...document.images].filter((i) => !i.complete || i.naturalWidth === 0).length,
  tables: document.querySelectorAll('table').length,
  h1: document.querySelectorAll('main h1').length,
  badLinks: [...document.querySelectorAll('a[href^="#"]')].map((a) => a.getAttribute('href').slice(1))
    .filter((id) => id && !document.getElementById(decodeURIComponent(id))),
}));
console.log(JSON.stringify(stats));
await browser.close();
