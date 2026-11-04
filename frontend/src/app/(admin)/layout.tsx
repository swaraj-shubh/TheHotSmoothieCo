import type { Metadata, Viewport } from "next"
import { Geist, Instrument_Serif } from "next/font/google"

import { Toaster } from "@/components/ui/sonner"
import { TooltipProvider } from "@/components/ui/tooltip"
import { SITE } from "@/lib/site"

import "./globals.css"

const sans = Geist({ variable: "--font-sans", subsets: ["latin"] })
// Editorial serif for headings and the wordmark.
const display = Instrument_Serif({ variable: "--font-serif", subsets: ["latin"], weight: "400", style: ["normal", "italic"] })

export const metadata: Metadata = {
  metadataBase: new URL(SITE.url),
  title: { default: `Admin · ${SITE.name}`, template: `%s · ${SITE.name}` },
  robots: { index: false },
}

export const viewport: Viewport = { themeColor: "#faf8f4" }

/** Root layout of the admin. Separate from the storefront's so Tailwind never reaches the shop. */
export default function AdminRootLayout({ children }: { children: React.ReactNode }) {
  return (
    <html lang="en-IN" className={`${sans.variable} ${display.variable} h-full antialiased`}>
      <body className="flex min-h-full flex-col">
        <TooltipProvider>{children}</TooltipProvider>
        <Toaster position="top-center" richColors />
      </body>
    </html>
  )
}
