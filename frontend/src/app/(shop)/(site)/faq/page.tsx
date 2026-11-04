import type { Metadata } from "next"
import Link from "next/link"

import { Crumbs, FaqList } from "@/components/sf/bits"

export const metadata: Metadata = { title: "FAQ", description: "Questions, answered. Including the silly ones." }

export default function FaqPage() {
  return (
    <>
      <Crumbs items={[["Home", "/"], ["FAQ"]]} />
      <section className="wrap" id="faq-grid" style={{ display: "grid", gridTemplateColumns: "minmax(0,480px) 1fr", gap: 80, paddingTop: 48, paddingBottom: 96 }}>
        <div style={{ display: "grid", gap: 16, alignContent: "start" }}>
          <h1 className="t-display">Questions, answered.</h1>
          <p className="t-sub">
            Still stuck? Write to us from the{" "}
            <Link href="/contact" className="brand" style={{ textDecoration: "underline" }}>
              Contact page
            </Link>
            .
          </p>
        </div>
        <div>
          <FaqList />
        </div>
      </section>
    </>
  )
}
