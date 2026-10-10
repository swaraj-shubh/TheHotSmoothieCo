import { expect, test } from "@playwright/test"

test("browse: home → shop → product", async ({ page }) => {
  await page.goto("/")
  await expect(page).toHaveTitle(/Hot Smoothie/i)
  await page.goto("/shop")
  const first = page.locator("a[href^='/product/']").first()
  await expect(first).toBeVisible()
  await first.click()
  await expect(page.getByRole("button", { name: "Add to cart" })).toBeVisible()
  // Product pages carry structured data for search engines.
  await expect(page.locator("script[type='application/ld+json']").first()).toBeAttached()
})

test("search finds products and handles no results", async ({ page }) => {
  await page.goto("/search?q=line")
  await expect(page.locator("a[href^='/product/']").first()).toBeVisible()
  await page.goto("/search?q=zzzznothing")
  await expect(page.getByText(/no results|nothing matched|couldn.t find/i)).toBeVisible()
})

test("guest cart: add, change quantity, remove", async ({ page }) => {
  await page.goto("/shop")
  await page.locator("a[href^='/product/']").first().click()
  await page.getByRole("button", { name: "Add to cart" }).click()
  await expect(page.getByText(/added to (your )?cart/i)).toBeVisible()
  await page.goto("/cart")
  await expect(page.getByRole("heading", { name: /cart/i })).toBeVisible()
  await page.getByRole("button", { name: /increase/i }).first().click()
  await expect(page.getByRole("spinbutton").or(page.getByText(/^2$/)).first()).toBeVisible()
  await page.getByRole("button", { name: /remove/i }).first().click()
  await expect(page.getByText(/cart is empty/i)).toBeVisible()
})

test("account pages require sign-in", async ({ page }) => {
  await page.goto("/account/orders")
  await expect(page).toHaveURL(/\/login/)
})
