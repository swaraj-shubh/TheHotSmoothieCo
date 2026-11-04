import type { Metadata } from "next"

import { Crumbs } from "@/components/sf/bits"
import { ContactForm } from "@/components/sf/static-forms"
import { SITE } from "@/lib/site"

export const metadata: Metadata = { title: "Contact", description: "Write to The Hot Smoothie Co." }

export default function ContactPage() {
  return (
    <>
      <Crumbs items={[["Home", "/"], ["Contact"]]} />
      <section className="wrap" id="contact-grid" style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: 72, paddingTop: 48, paddingBottom: 96 }}>
        <div style={{ display: "grid", gap: 24, alignContent: "start", justifyItems: "start" }}>
          <span className="t-label brand">TALK TO US</span>
          <h1 className="t-display">Tell us what is on your mind. Or your wall.</h1>
          <p className="t-sub">Order trouble, drop gossip, or a poster idea nobody asked for. We read everything.</p>
          <div className="t-cap" style={{ display: "grid", gap: 6 }}>
            <span className="muted">EMAIL</span>
            <a className="brand" style={{ textDecoration: "underline" }} href={`mailto:${SITE.supportEmail}`}>
              {SITE.supportEmail}
            </a>
            <span className="muted" style={{ marginTop: 12 }}>
              REPLY TIME
            </span>
            <span>Within 1-2 working days</span>
          </div>
        </div>
        <ContactForm />
      </section>
    </>
  )
}
