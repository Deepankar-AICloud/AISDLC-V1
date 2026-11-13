import { expect, test, type Browser, type Page } from "@playwright/test";
import path from "node:path";
import { fileURLToPath } from "node:url";

const __dirname = path.dirname(fileURLToPath(import.meta.url));

// Runs against the fake GitHub (development mode). Never touches a real repository.
const samples = path.resolve(__dirname, ".samples");
const CLEAR =
  "Business problem: managers cannot see the status of access requests. Objective: reduce turnaround. " +
  "Stakeholders: employees, managers and the security team.";

test.describe.configure({ mode: "serial" });

async function signIn(browser: Browser, username: string): Promise<Page> {
  const ctx = await browser.newContext();
  const page = await ctx.newPage();
  await page.goto("/");
  await page.getByRole("button", { name: `Sign in as ${username}` }).click();
  await expect(page.getByRole("button", { name: "Sign out" })).toBeVisible();
  return page;
}

async function connectGitHub(page: Page, login: string) {
  await page.goto("/account");
  await page.getByRole("link", { name: /Connect GitHub/ }).click();
  await page.getByLabel("GitHub account", { exact: true }).selectOption(login);
  await page.getByRole("button", { name: "Authorize" }).click();
  await expect(page.getByText("GitHub connected.")).toBeVisible();
  await expect(page.getByText(`Connected as ${login}`)).toBeVisible();
}

async function fakeState(page: Page) {
  const r = await page.request.post("/dev/fake-github/state");
  return r.json();
}

let requestUrl = "";

test("paste, upload PDF/DOCX/PPTX, preview and submit creates the issue, then labels it", async ({ browser }) => {
  const page = await signIn(browser, "alice");
  await page.goto("/new");
  await expect(page.getByText(/Do not upload secrets/)).toBeVisible();
  await page.getByLabel("Requirement text").fill(CLEAR);
  await page
    .getByLabel("Upload documents")
    .setInputFiles([
      path.join(samples, "requirements.pdf"),
      path.join(samples, "brief.docx"),
      path.join(samples, "scope.pptx"),
    ]);
  await expect(page.getByRole("list", { name: "Selected files" }).getByRole("listitem")).toHaveCount(3);
  await page.getByRole("button", { name: "Preview" }).click();

  await expect(page.getByRole("heading", { name: "Preview" })).toBeFocused();
  await expect(page.getByText(/PDF · 3 pages/)).toBeVisible();
  await expect(page.getByText(/PPTX · 2 slides/)).toBeVisible();
  await expect(page.getByText("Looks complete for the readiness check.")).toBeVisible();
  await page.getByText("Issue body preview").click();
  await expect(page.locator("pre.body-preview")).toContainText("## Source documents");
  await expect(page.locator("pre.body-preview")).toContainText("UNTRUSTED SOURCE MATERIAL");

  const submit = page.getByRole("button", { name: "Submit to AISDLC" });
  await submit.dblclick(); // a double-click must still create one issue
  await expect(page).toHaveURL(/\/requests\/req_/);
  await expect(page.getByRole("link", { name: /GitHub issue #\d+/ })).toBeVisible();
  await expect(page.getByText("Stage in review")).toBeVisible();
  await expect(page.getByRole("cell", { name: "BRD" })).toBeVisible();
  requestUrl = new URL(page.url()).pathname;

  const state = await fakeState(page);
  const issues = Object.values(state.issues) as { author: string; labels: string[] }[];
  expect(issues).toHaveLength(1);
  expect(issues[0]?.author).toBe("aisdlc-portal[bot]");
  const startAdd = state.label_log.find((e: string[]) => e[1] === "add" && e[2] === "sdlc:start");
  expect(startAdd[3]).toBe("aisdlc-portal[bot]");
  await page.context().close();
});

test("AISDLC asks a question and the requester answers as themself", async ({ browser }) => {
  const page = await signIn(browser, "alice");
  await page.goto("/new");
  await page.getByLabel("Requirement text").fill("Lorem ipsum dolor sit amet, consectetur adipiscing elit.");
  await page.getByRole("button", { name: "Preview" }).click();
  await expect(page.getByText(/AISDLC will probably ask about/)).toBeVisible();
  await page.getByRole("button", { name: "Submit to AISDLC" }).click();
  await expect(page.getByRole("heading", { name: "AISDLC needs more information" })).toBeVisible();
  await expect(page.getByText(/Please provide: business problem/)).toBeVisible();
  const detailUrl = page.url();

  await expect(page.getByRole("link", { name: "Connect GitHub" }).first()).toBeVisible();
  await connectGitHub(page, "alice-gh");
  await page.goto(detailUrl);
  await page.getByLabel("Your answer").fill(CLEAR);
  await page.getByRole("button", { name: "Post answer" }).click();
  await expect(page.getByText("Posted to GitHub as alice-gh. AISDLC will resume.")).toBeVisible();
  await expect(page.getByText("Stage in review")).toBeVisible();

  const state = await fakeState(page);
  const all = Object.values(state.comments).flat() as { author: string; body: string }[];
  const answer = all.find((c) => c.body.startsWith("Business problem: managers"));
  expect(answer?.author).toBe("alice-gh");
  await page.context().close();
});

test("a code-owner reviewer reviews the artifact and approves under their own login", async ({ browser }) => {
  const page = await signIn(browser, "bob");
  await connectGitHub(page, "bob-gh");
  await page.goto("/requests");
  const assigned = page.getByRole("region", { name: "Assigned to me for review" });
  await expect(assigned.getByRole("link").first()).toBeVisible();
  await page.goto(requestUrl);
  await page.getByRole("link", { name: "Review" }).click();

  await expect(page.getByRole("heading", { name: /BRD review/ })).toBeVisible();
  await expect(page.locator(".mermaid-box svg")).toBeVisible();
  await page.getByRole("tab", { name: /Diff/ }).click();
  await expect(page.locator(".diff").first()).toContainText("+# BRD");
  await page.getByRole("tab", { name: "QC scorecard" }).click();
  await expect(page.getByRole("tabpanel")).toContainText("QC: PASS 0.86");
  await expect(page.getByRole("list", { name: "Approval checks" })).toContainText("code owner");

  await page.getByRole("button", { name: "Approve…" }).click();
  const dialog = page.getByRole("dialog");
  await expect(dialog).toContainText("merges this pull request and starts the next stage");
  const confirm = dialog.getByRole("button", { name: "Approve on GitHub" });
  await expect(confirm).toBeDisabled();
  await dialog.getByLabel(/I have reviewed/).check();
  await confirm.click();
  await expect(page.getByText(/Approved on GitHub as bob-gh/)).toBeVisible();

  const state = await fakeState(page);
  const reviews = Object.values(state.reviews).flat() as { author: string; state: string }[];
  expect(reviews).toEqual([{ author: "bob-gh", state: "APPROVED" }]);
  await page.goto(requestUrl);
  await expect(page.getByRole("cell", { name: "PRD" })).toBeVisible();
  await page.context().close();
});

test("an unassigned reviewer cannot see or act on the request", async ({ browser }) => {
  const page = await signIn(browser, "carol");
  await connectGitHub(page, "carol-gh");
  await page.goto("/requests");
  // carol is not assigned, so the request is invisible to her
  await page.goto(requestUrl);
  await expect(page.getByText("Request not found, or you do not have access to it.")).toBeVisible();
  await page.context().close();
});

test("a new user without a work account signs in with GitHub", async ({ browser }) => {
  const ctx = await browser.newContext();
  const page = await ctx.newPage();
  await page.goto("/");
  await expect(page.getByText("New here? Use your GitHub account")).toBeVisible();
  await page.getByRole("link", { name: "Sign in with GitHub" }).click();
  await page.getByLabel(/create a new GitHub account/).fill("newbie-gh");
  await page.getByRole("button", { name: "Authorize" }).click();
  await expect(page.getByRole("button", { name: "Sign out" })).toBeVisible();
  await expect(page.getByText(/newbie-gh · Requester · GitHub: newbie-gh/)).toBeVisible();
  await expect(page.getByRole("heading", { name: "New requirement" })).toBeVisible();
  await page.goto("/account");
  await expect(page.getByText(/this connection is your identity/)).toBeVisible();
  await ctx.close();
});

test("a GitHub user without repository access is refused with an explanation", async ({ browser }) => {
  const ctx = await browser.newContext();
  const page = await ctx.newPage();
  await page.goto("/");
  await page.getByRole("link", { name: "Sign in with GitHub" }).click();
  await page.getByLabel("GitHub account", { exact: true }).selectOption("mallory-gh");
  await page.getByRole("button", { name: "Authorize" }).click();
  await expect(page.getByText(/doesn't have access to the AISDLC repository yet/)).toBeVisible();
  await ctx.close();
});
