import Link from "next/link"
import { Fragment } from "react"

import { FAQS } from "@/lib/content"

/** `crumbs` from the site: last entry is the current page. */
export function Crumbs({ items }: { items: [string, string?][] }) {
  return (
    <nav className="crumbs wrap t-cap" aria-label="Breadcrumb">
      {items.map(([label, href], i) => (
        <Fragment key={label}>
          {href ? <Link href={href}>{label}</Link> : <span aria-current="page">{label}</span>}
          {i < items.length - 1 && <span aria-hidden="true">/</span>}
        </Fragment>
      ))}
    </nav>
  )
}

export function FaqList() {
  return (
    <>
      {FAQS.map((f, i) => (
        <details key={f.q} className="acc" open={i === 0}>
          <summary>{f.q}</summary>
          <p className="acc__body">{f.a}</p>
        </details>
      ))}
    </>
  )
}

export function Steps() {
  return (
    <div className="steps">
      <div className="step">
        <span className="t-price muted">01</span>
        <h3 className="t-head">Picked</h3>
        <p style={{ opacity: 0.85 }}>Every design is chosen for a drop, not dumped into a catalogue.</p>
      </div>
      <div className="step">
        <span className="t-price muted">02</span>
        <h3 className="t-head">Printed</h3>
        <p style={{ opacity: 0.85 }}>300 GSM glossy sheets, so the colors stay as loud as the idea.</p>
      </div>
      <div className="step">
        <span className="t-price muted">03</span>
        <h3 className="t-head">Packed</h3>
        <p style={{ opacity: 0.85 }}>Tamper-proof packaging, at your door in 4-5 days.</p>
      </div>
    </div>
  )
}

export function Empty({ title, children }: { title: React.ReactNode; children?: React.ReactNode }) {
  return (
    <div className="empty" style={{ gridColumn: "1/-1" }}>
      <img src="/assets/croc-wordmark.png" alt="" />
      {title}
      {children}
    </div>
  )
}
