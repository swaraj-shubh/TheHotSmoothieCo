import { expect, test } from "@playwright/test"

test("browse: home → shop → product", async ({ page }) => {
  await page.goto("/")
  await expect(page).toHaveTitle(/Hot Smoothie/i)
  await page.goto("/shop")
  const first = page.locator("a[href^='/product/']").first()
  await expect(first).toBeVisible()
  await first.click()
  await expect(page.locator(".pdp__buy").getByRole("button", { name: "Add to cart" })).toBeVisible()
  // Product pages carry structured data for search engines.
  await expect(page.locator("script[type='application/ld+json']").first()).toBeAttached()
})

test("search finds products and handles no results", async ({ page }) => {
  await page.goto("/search?q=soul")
  await expect(page.locator("a[href^='/product/']").first()).toBeVisible()
  await page.goto("/search?q=zzzznothing")
  await expect(page.getByText("No results. The croc looked everywhere.")).toBeVisible()
})

test("guest cart: add from a card and a product page, change quantity, remove", async ({ page }) => {
  await page.goto("/shop")
  await page.getByRole("button", { name: "Add to cart" }).first().click()
  await expect(page.getByText(/is in your cart/i)).toBeVisible()
  await expect(page.locator("[data-cart-count]")).toHaveText("1")
  await page.locator("a.card__media").first().click()
  await expect(() => page.getByRole("radio", { name: "A3" }).check({ force: true, timeout: 1000 })).toPass()
  await page.locator(".pdp__buy").getByRole("button", { name: "Add to cart" }).click()
  await expect(page.getByText(/\(A3\) added/i)).toBeVisible()
  await expect(page.locator("[data-cart-count]")).toHaveText("2")
  await page.goto("/cart")
  await expect(page.getByRole("heading", { name: /your cart/i })).toBeVisible()
  await page.getByRole("button", { name: "More" }).first().click()
  await expect(page.locator(".stepper output").first()).toHaveText("2")
  await page.getByRole("button", { name: "Remove" }).first().click()
  await expect(page.locator(".line")).toHaveCount(1)
  await page.getByRole("button", { name: "Remove" }).first().click()
  await expect(page.getByText(/empty as your wall/i)).toBeVisible()
})

test("promo code: a bad code explains itself", async ({ page }) => {
  await page.goto("/shop")
  await page.getByRole("button", { name: "Add to cart" }).first().click()
  await expect(page.locator("[data-cart-count]")).toHaveText("1")
  await page.goto("/cart")
  await page.getByLabel("Promo code").fill("NOPE")
  await page.getByRole("button", { name: "Apply" }).click()
  await expect(page.locator("form.field .err")).not.toBeEmpty()
})

test("static pages and the 404 render", async ({ page }) => {
  for (const [path, text] of [["/about", /good stories/i], ["/faq", /questions, answered/i], ["/contact", /on your mind/i], ["/gift-cards", /argue about it/i], ["/shipping-returns", /shipping & returns/i]] as const) {
    await page.goto(path)
    await expect(page.locator("h1")).toContainText(text)
  }
  const missing = await page.goto("/no-such-page")
  expect(missing?.status()).toBe(404)
  await expect(page.getByText(/worse taste than you/i)).toBeVisible()
})

test("the product image opens a zoomable preview", async ({ page }) => {
  await page.goto("/shop")
  await page.locator("a.card__media").first().click()
  await page.locator(".pdp__main img").click()
  const preview = page.getByRole("dialog", { name: "Image preview" })
  await expect(preview).toBeVisible()
  await preview.getByRole("button", { name: "Zoom in" }).click()
  await expect(preview.locator("img")).toHaveAttribute("style", /scale\(1\.5\)/)
  await preview.getByRole("button", { name: "Close" }).click()
  await expect(preview).toBeHidden()
})

test("account pages require sign-in", async ({ page }) => {
  await page.goto("/account/orders")
  await expect(page).toHaveURL(/\/login/)
})

test("home: wall colours, vinyl player, club form and scroll reveal", async ({ page }) => {
  await page.goto("/")
  await expect(page.locator("#hdr")).toHaveClass(/header--overlay/)
  await expect(page.locator(".collections .coll")).toHaveCount(3)
  await expect(page.locator("#bestsellers .card")).toHaveCount(3)

  await page.getByRole("radio", { name: "Linen" }).check({ force: true })
  await expect(page.locator(".wall-mock .chip")).toHaveText("WALL: LINEN")
  await expect(page.locator(".wall-mock")).toHaveAttribute("style", /--wall:\s*#f2eadb/)

  await page.getByRole("button", { name: "Next", exact: true }).click()
  await expect(page.locator(".player__now b")).toHaveText("Side Eye, Slow Burn")
  await page.getByRole("button", { name: "Pause" }).click()
  await expect(page.locator(".player")).toHaveClass(/paused/)

  await page.getByLabel("Email address").fill("club@example.com")
  await page.getByRole("button", { name: "Join the club" }).click()
  await expect(page.getByText(/takes 10% off your first order/)).toBeVisible()

  // Reveal: off-screen sections start hidden and appear on scroll, as on the site.
  await expect(page.locator(".footer__col").first()).toHaveClass(/reveal/)
  await page.locator(".footer").scrollIntoViewIfNeeded()
  await expect(page.locator(".footer__col").first()).toHaveClass(/\bin\b/)
  await expect(page.locator(".page-top")).toHaveClass(/show/)
})

test("shop: filter, sort, and the header after client-side navigation", async ({ page }) => {
  await page.goto("/")
  await page.getByRole("link", { name: "Collections" }).first().click()
  await expect(page).toHaveURL(/\/shop/)
  await expect(page.locator("#hdr")).not.toHaveClass(/header--overlay/)
  await expect(page.locator(".card:visible")).toHaveCount(5)
  // Cards that arrive on client navigation still get revealed.
  await page.locator(".card:visible").first().scrollIntoViewIfNeeded()
  await expect(page.locator(".card:visible").first()).toHaveClass(/\bin\b/)

  await page.evaluate(() => scrollTo(0, 0)) // the sticky header would cover the pills
  await expect(() => page.getByRole("radio", { name: "Nerd Fiction" }).check({ force: true, timeout: 1000 })).toPass()
  await expect(page.locator(".card:visible")).toHaveCount(2)
  await expect(page.getByText("2 posters")).toBeVisible()
  await page.getByRole("radio", { name: "All" }).check({ force: true })
  await page.locator("#sort").selectOption("az")
  await expect(page.locator(".card__title:visible").first()).toHaveText("Baddie Profile #1")
})

test("product: views, wall colour, sizes change price and dimensions", async ({ page }) => {
  await page.goto("/product/red-bull-1")
  await expect(page.locator(".pdp__thumbs button")).toHaveCount(3)
  await expect(page.locator(".pdp__buy .t-price")).toHaveText("Rs. 499")
  await expect(page.getByText("21 × 29.7 cm")).toBeVisible()
  await expect(() => page.getByRole("radio", { name: "A3" }).check({ force: true, timeout: 1000 })).toPass()
  await expect(page.locator(".pdp__buy .t-price")).toHaveText("Rs. 799")
  await expect(page.getByText("29.7 × 42 cm")).toBeVisible()
  await page.getByRole("button", { name: "More" }).click()
  await expect(page.locator(".pdp__buy .t-price")).toHaveText("Rs. 1,598")
  await page.getByRole("radio", { name: "Ink" }).check({ force: true })
  await expect(page.locator(".pdp__main")).toHaveClass(/is-framed/)
  await expect(page.getByText("Only 250 made.")).toBeVisible()
  await expect(page.getByText(/Hang it if/)).toBeVisible()
})

test("phone: the menu opens and closes", async ({ page }) => {
  await page.setViewportSize({ width: 390, height: 844 })
  await page.goto("/shop")
  await expect(page.locator("#nav")).toBeHidden()
  await page.getByRole("button", { name: "Menu" }).click()
  await expect(page.locator("#nav").getByRole("link", { name: "About" })).toBeVisible()
})

test("coming soon: waiting list accepts an email and rejects junk", async ({ page }) => {
  await page.goto("/coming-soon")
  // Enter, not a click: the card sways with the parallax, so it never counts as "stable".
  await page.getByLabel("Email address").fill("nope")
  await page.getByLabel("Email address").press("Enter")
  await expect(page.getByText(/does not look like an email/)).toBeVisible()
  await page.getByLabel("Email address").fill("wait@example.com")
  await page.getByLabel("Email address").press("Enter")
  await expect(page.getByText("Wall secured.")).toBeVisible()
})
