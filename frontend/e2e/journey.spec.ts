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
  await page.getByRole("button", { name: "[ Sign in ]" }).click()
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

test("wishlist: the heart saves and removes", async ({ page }) => {
  await signIn(page, email, password)
  await page.goto("/shop")
  await page.locator(".card__wish").first().click()
  await expect(page.getByText(/your wall will be ready/i)).toBeVisible()
  await page.goto("/wishlist")
  await expect(page.locator(".card")).toHaveCount(1)
  await page.locator(".card__wish").first().click()
  await expect(page.getByText(/removed from your wishlist/i)).toBeVisible()
  await expect(page.locator(".card")).toHaveCount(0)
})

test("guests are sent to sign in by the heart", async ({ page }) => {
  await page.goto("/shop")
  await page.locator(".card__wish").first().click()
  await expect(page).toHaveURL(/\/login/)
})

test("checkout with a simulated payment", async ({ page }) => {
  await signIn(page, email, password)
  await page.goto("/shop")
  await page.getByRole("button", { name: "Add to cart" }).first().click()
  await expect(page.locator("[data-cart-count]")).toHaveText("1")
  await page.goto("/cart")
  await page.getByRole("link", { name: "[ Checkout ]" }).click()
  await expect(page).toHaveURL(/\/checkout/)

  // The site's validation messages.
  await page.getByRole("button", { name: "Place order" }).click()
  await expect(page.getByText("We need a name for the parcel.")).toBeVisible()

  await page.getByLabel("Full name").fill("Asha Tester")
  await page.getByLabel("Mobile").fill("9876543210")
  await page.getByLabel("Address", { exact: true }).fill("12 MG Road")
  await page.getByLabel("City").fill("Bengaluru")
  await page.getByLabel("State").fill("Karnataka")
  await page.getByLabel("Pin code").fill("560001")
  await page.getByRole("button", { name: "Place order" }).click()

  await page.getByRole("button", { name: /simulate successful payment/i }).click()
  await expect(page).toHaveURL(/\/order-confirmed\/[0-9a-f-]{36}/)
  await expect(page.getByRole("heading", { name: /walls are about to get interesting/i })).toBeVisible()
  await expect(page.getByText("Delivering to")).toBeVisible()
  orderUrl = page.url().replace("/order-confirmed/", "/account/orders/")
  await expect(page.locator("[data-cart-count]")).toHaveText("0")
})

test("the saved address is offered next time", async ({ page }) => {
  await signIn(page, email, password)
  await page.goto("/shop")
  await page.getByRole("button", { name: "Add to cart" }).first().click()
  await expect(page.locator("[data-cart-count]")).not.toHaveText("0")
  await page.goto("/checkout")
  await expect(page.getByText("12 MG Road")).toBeVisible()
  await page.goto("/cart")
  await page.getByRole("button", { name: "Remove" }).first().click()
  await expect(page.getByText(/empty as your wall/i)).toBeVisible()
})

test("cancel the paid order and get refunded", async ({ page }) => {
  test.skip(!orderUrl, "needs the checkout test")
  await signIn(page, email, password)
  await page.goto(orderUrl)
  await page.getByRole("button", { name: "[ Cancel order ]" }).click()
  await page.getByRole("button", { name: "[ Yes, cancel ]" }).click()
  await expect(page.locator(".chip").getByText(/^(Cancelled|Refunded|Refund pending)$/)).toBeVisible()
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
  await expect(page.getByText(email).filter({ visible: true }).first()).toBeVisible()
  await expect(page.getByText("Timeline").filter({ visible: true }).first()).toBeVisible()
  for (const path of ["/admin/dashboard", "/admin/products", "/admin/inventory", "/admin/customers", "/admin/settings"]) {
    await page.goto(path)
    await expect(page.locator("h1").filter({ visible: true }).first()).toBeVisible()
  }
})
