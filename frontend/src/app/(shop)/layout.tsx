import type { Metadata } from "next"

import { Motion } from "@/components/sf/motion"
import { Toaster } from "@/components/sf/toast"
import { SITE } from "@/lib/site"

import "./storefront.css"

export const metadata: Metadata = {
  metadataBase: new URL(SITE.url),
  title: { default: `${SITE.name} · Posters for people with questionable taste`, template: `%s · ${SITE.name}` },
  description: SITE.description,
  applicationName: SITE.name,
  openGraph: { type: "website", siteName: SITE.name, locale: "en_IN" },
  twitter: { card: "summary_large_image" },
}

/** Root layout of the storefront: the site/ stylesheet and nothing else (no Tailwind). */
export default function ShopRootLayout({ children }: { children: React.ReactNode }) {
  return (
    <html lang="en">
      <head>
        {/* Same font request as site/: next/font's self-hosted builds set text slightly differently. */}
        <link rel="preconnect" href="https://fonts.googleapis.com" />
        <link rel="preconnect" href="https://fonts.gstatic.com" crossOrigin="" />
        <link href="https://fonts.googleapis.com/css2?family=Space+Grotesk:wght@400;500;700&family=Space+Mono:wght@400;700&display=swap" rel="stylesheet" />
      </head>
      <body>
        {children}
        <Toaster />
        <Motion />
      </body>
    </html>
  )
}
