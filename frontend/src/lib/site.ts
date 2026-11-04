export const SITE = {
  name: "The Hot Smoothie Co.",
  description: "Limited-edition posters on 300 GSM glossy sheets for walls with opinions. Good taste is overrated.",
  // Public URL of the storefront (canonical links, sitemap, Open Graph).
  url: process.env.NEXT_PUBLIC_SITE_URL ?? "http://localhost:3000",
  supportEmail: "hello@thehotsmoothieco.com",
  dropDate: "2026-11-05T18:00:00+05:30",
  // Shown in copy and the free-delivery meter; the API's SHIPPING_FLAT_PAISE and
  // FREE_SHIPPING_THRESHOLD_PAISE decide what is actually charged, so keep them in step.
  freeShippingAbovePaise: 99900,
  shippingFeePaise: 7900,
}
