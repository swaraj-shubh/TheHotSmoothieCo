import { expect, type Page, test } from "@playwright/test"

// One customer, end to end: register → buy → pay (simulated) → cancel → refund; then staff sees it.
test.describe.configure({ mode: "serial" })

const email = `e2e+${Date.now()}@example.com`
const password = "e2e-password-123"
let orderUrl = ""

async function signIn(page: Page, user: string, pass: string) {
  await page.goto("/login")
  await page.getByLabel("Email").fill(user)
  await page.getByLabel("Password").fill(pass)
  await page.getByRole("button", { name: "Sign in" }).click()
  await page.waitForURL((u) => !u.pathname.startsWith("/login"))
}

test("register", async ({ page }) => {
  await page.goto("/register")
  await page.getByLabel("Full name").fill("Asha Tester")
  await page.getByLabel("Email").fill(email)
  await page.getByLabel("Password").fill(password)
  await page.getByRole("button", { name: "Create account" }).click()
  await expect(page).toHaveURL(/\/account/)
})

test("checkout with a simulated payment", async ({ page }) => {
  await signIn(page, email, password)
  await page.goto("/shop")
  await page.locator("a[href^='/product/']").first().click()
  await page.getByRole("button", { name: "Buy now" }).click()
  await expect(page).toHaveURL(/\/checkout/)

  await page.getByLabel("Full name").fill("Asha Tester")
  await page.getByLabel("Phone").fill("9876543210")
  await page.getByLabel("Address line 1").fill("12 MG Road")
  await page.getByLabel("City").fill("Bengaluru")
  await page.getByLabel("State").fill("Karnataka")
  await page.getByLabel("PIN code").fill("560001")
  await page.getByRole("button", { name: "Save and use this address" }).click()

  await page.getByRole("button", { name: "Place order & pay" }).click()
  await page.getByRole("button", { name: /simulate successful payment/i }).click()
  await expect(page).toHaveURL(/\/account\/orders\/[0-9a-f-]{36}/)
  await expect(page.getByText(/order is confirmed/i)).toBeVisible()
  orderUrl = page.url().split("?")[0]
})

test("cancel the paid order and get refunded", async ({ page }) => {
  test.skip(!orderUrl, "needs the checkout test")
  await signIn(page, email, password)
  await page.goto(orderUrl)
  await page.getByRole("button", { name: "Cancel order" }).click()
  await page.getByRole("button", { name: "Yes, cancel" }).click()
  await expect(page.getByText(/^(Cancelled|Refunded|Refund pending)$/).first()).toBeVisible()
})

test("staff can find the order in the admin", async ({ page }) => {
  const admin = process.env.E2E_ADMIN_EMAIL
  const adminPass = process.env.E2E_ADMIN_PASSWORD
  test.skip(!admin || !adminPass, "set E2E_ADMIN_EMAIL / E2E_ADMIN_PASSWORD")
  await signIn(page, admin!, adminPass!)
  await page.goto(`/admin/orders?q=${encodeURIComponent(email)}`)
  const link = page.locator("a[href^='/admin/orders/']").first()
  await expect(link).toBeVisible()
  await link.click()
  await expect(page.getByText(email)).toBeVisible()
  await expect(page.getByText("Timeline")).toBeVisible()
  for (const path of ["/admin/dashboard", "/admin/products", "/admin/inventory", "/admin/customers", "/admin/settings"]) {
    await page.goto(path)
    await expect(page.locator("h1")).toBeVisible()
  }
})
