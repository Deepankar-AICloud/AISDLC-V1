import { expect, test } from "@playwright/test";

test.skip(
  process.env.E2E_AUTH_MODE !== "password",
  "Run with E2E_AUTH_MODE=password against the isolated test server.",
);

test("shared login retains the design, submits an issue and keeps reviewer privileges separate", async ({ page }) => {
  await page.goto("/");
  await expect(page.getByRole("heading", { name: "AISDLC Portal", exact: true })).toBeVisible();
  await expect(page.locator(".login-stripe span")).toHaveCount(4);
  await expect(page.locator(".login-page")).toHaveCSS("background-image", /linear-gradient/);
  await expect(page.locator(".stripe-red")).toHaveCSS("background-color", "rgb(242, 80, 34)");
  await expect(page.locator(".stripe-green")).toHaveCSS("background-color", "rgb(127, 186, 0)");
  await expect(page.locator(".stripe-blue")).toHaveCSS("background-color", "rgb(0, 164, 239)");
  await expect(page.locator(".stripe-yellow")).toHaveCSS("background-color", "rgb(255, 185, 0)");
  await expect(page.getByRole("button", { name: "Sign in as alice" })).toHaveCount(0);
  await expect(page.getByRole("link", { name: "Sign in with GitHub" })).toBeVisible();
  await page.getByLabel("Username", { exact: true }).fill("admin");
  await page.getByLabel("Password", { exact: true }).fill("wrong");
  await page.getByRole("button", { name: "Sign in", exact: true }).click();
  await expect(page.getByRole("alert")).toContainText("Incorrect username or password");
  await page.getByLabel("Password", { exact: true }).fill("e2e-only-password");
  await page.getByRole("button", { name: "Sign in", exact: true }).click();
  await expect(page.getByRole("heading", { name: "New requirement" })).toBeVisible();
  await expect(page.locator("header")).not.toContainText("Admin (shared)");
  await expect(page.getByRole("button", { name: "Sign out", exact: true })).toBeVisible();
  await expect(page.getByText(/Shared requester account:/)).toHaveCount(0);
  await expect(page.getByRole("link", { name: "Production", exact: true })).toHaveCount(0);
  await page.getByLabel("Problem", { exact: true }).fill("Managers cannot see access request status.");
  await page.getByLabel("Objective / Goal").fill("Improve visibility.");
  await page.getByLabel("Stakeholders / Users").fill("Employees, managers and the security team.");
  await page.getByRole("button", { name: "Preview", exact: true }).click();
  await page.getByRole("button", { name: "Submit to AISDLC" }).click();
  await expect(page).toHaveURL(/\/requests\/req_/);
  await expect(page.getByRole("link", { name: /GitHub issue #/ })).toBeVisible();
  await page.getByRole("link", { name: "Review", exact: true }).click();
  await expect(page.getByText("Reviewing needs the Reviewer role in the portal.")).toBeVisible();
  await expect(page.getByRole("button", { name: "Approve…" })).toHaveCount(0);
  await page.getByRole("link", { name: "Account", exact: true }).click();
  await expect(page.getByRole("link", { name: "Connect GitHub" })).toHaveCount(0);
  await page.getByRole("button", { name: "Sign out", exact: true }).click();
  await expect(page.getByLabel("Username", { exact: true })).toBeVisible();

  await page.getByRole("link", { name: "Sign in with GitHub" }).click();
  await page.getByLabel("GitHub account", { exact: true }).selectOption("bob-gh");
  await page.getByRole("button", { name: "Authorize" }).click();
  await expect(page.getByRole("link", { name: "Production", exact: true })).toBeVisible();
});

test("password form remains usable on a narrow screen", async ({ page }) => {
  await page.setViewportSize({ width: 390, height: 844 });
  await page.goto("/");
  await expect(page.getByLabel("Username", { exact: true })).toBeVisible();
  await expect(page.getByLabel("Password", { exact: true })).toHaveAttribute("type", "password");
  const size = await page.evaluate(() => ({
    content: document.documentElement.scrollWidth,
    viewport: window.innerWidth,
  }));
  expect(size.content).toBeLessThanOrEqual(size.viewport);
});
