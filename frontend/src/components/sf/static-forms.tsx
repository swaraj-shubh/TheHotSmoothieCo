"use client"

import { useState } from "react"

import { money } from "@/lib/format"
import { SITE } from "@/lib/site"

import { toast } from "./toast"

/** ponytail: the API has no contact endpoint, so this hands the message to the visitor's mail app
 *  rather than dropping it. Post it to the backend once there is one. */
export function ContactForm() {
  const [sent, setSent] = useState(false)
  if (sent) {
    return (
      <div style={{ display: "grid", gap: 20 }}>
        <div className="empty" style={{ padding: "24px 0" }}>
          <img src="/assets/croc-wordmark.png" alt="" style={{ width: 140 }} />
          <p className="t-head">Message received.</p>
          <p>A human (or at least a very organised croc) will reply soon.</p>
        </div>
      </div>
    )
  }
  return (
    <form
      style={{ display: "grid", gap: 20 }}
      noValidate
      onSubmit={(e) => {
        e.preventDefault()
        const f = e.currentTarget
        if (!f.checkValidity()) return f.reportValidity()
        const d = new FormData(f)
        const body = `${d.get("message")}\n\n${d.get("name")} (${d.get("email")})`
        window.location.href = `mailto:${SITE.supportEmail}?subject=${encodeURIComponent(String(d.get("topic")))}&body=${encodeURIComponent(body)}`
        setSent(true)
      }}
    >
      <div className="grid-2">
        <div className="field">
          <label htmlFor="n">Name</label>
          <input className="input" id="n" name="name" required autoComplete="name" />
        </div>
        <div className="field">
          <label htmlFor="e">Email</label>
          <input className="input" id="e" name="email" type="email" required autoComplete="email" />
        </div>
      </div>
      <div className="field">
        <label htmlFor="t">What is it about?</label>
        <select className="input" id="t" name="topic">
          <option>An order</option>
          <option>A return</option>
          <option>A poster I want</option>
          <option>Something else</option>
        </select>
      </div>
      <div className="field">
        <label htmlFor="m">Message</label>
        <textarea className="input" id="m" name="message" required />
      </div>
      <button className="btn" type="submit" style={{ width: "fit-content" }}>
        [ Send it ]
      </button>
    </form>
  )
}

const AMOUNTS = [500, 1000, 2000, 5000]

/** ponytail: the backend has no gift-card product yet, so this page is the design with a holding
 *  message instead of a cart line. */
export function GiftCards() {
  const [amt, setAmt] = useState(1000)
  return (
    <section className="wrap" id="gift-grid" style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: 72, alignItems: "center", paddingTop: 48, paddingBottom: 96 }}>
      <div style={{ display: "grid", gap: 28, justifyItems: "start" }}>
        <span className="t-label brand">GIFT CARDS</span>
        <h1 className="t-display">For the friend who would argue about it.</h1>
        <p className="t-sub">Digital gift cards, delivered by email. They pick the obsession.</p>
        <div className="gift-card-preview" aria-hidden="true">
          <span className="t-label">THE HOT SMOOTHIE CO. · GIFT CARD</span>
          <span className="t-display" style={{ color: "var(--linen)" }}>
            {money(amt * 100)}
          </span>
          <img src="/assets/croc-wordmark.png" alt="" />
        </div>
      </div>
      <form
        style={{ display: "grid", gap: 24 }}
        noValidate
        onSubmit={(e) => {
          e.preventDefault()
          const em = e.currentTarget.elements.namedItem("to") as HTMLInputElement
          if (!em.checkValidity()) return em.reportValidity()
          toast("Gift cards land soon. The croc is still printing them.")
        }}
      >
        <div className="field">
          <span className="t-label">Amount</span>
          <div className="pill-group" role="radiogroup" aria-label="Amount">
            {AMOUNTS.map((a) => (
              <label key={a} className="pill">
                <input type="radio" name="amt" value={a} checked={amt === a} onChange={() => setAmt(a)} />
                <span>{money(a * 100)}</span>
              </label>
            ))}
          </div>
        </div>
        <div className="field">
          <label htmlFor="to">Their email</label>
          <input className="input" id="to" name="to" type="email" required placeholder="friend@example.com" />
        </div>
        <div className="field">
          <label htmlFor="msg">A note (optional)</label>
          <textarea className="input" id="msg" name="msg" maxLength={200} placeholder="Something unhinged and loving." />
        </div>
        <button className="ticket-btn" type="submit" style={{ width: "fit-content" }}>
          Add gift card to cart
        </button>
        <p className="t-cap muted">Delivered by email within minutes of payment. No shipping, no waiting.</p>
      </form>
    </section>
  )
}
