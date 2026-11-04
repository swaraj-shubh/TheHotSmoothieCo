import type { Metadata } from "next"
import Link from "next/link"

import { Steps } from "@/components/sf/bits"

export const metadata: Metadata = { title: "About", description: "Why The Hot Smoothie Co. exists: posters for people with questionable taste." }

export default function AboutPage() {
  return (
    <>
      <section className="wrap" style={{ paddingTop: 64, paddingBottom: 72, display: "grid", gap: 24, maxWidth: 1240 }}>
        <span className="t-label brand">ABOUT</span>
        <h1 className="t-hero" style={{ color: "var(--cherry)" }}>
          Not good taste. Good stories.
        </h1>
        <p className="t-head" style={{ maxWidth: 900 }}>
          The Hot Smoothie Co. makes posters for people whose personality is built around a fictional character, a questionable race strategy, or a family WhatsApp argument from 2023.
        </p>
      </section>
      <section className="wrap" style={{ paddingBottom: 96 }}>
        <div className="split">
          <img className="rounded" src="/assets/croc-duo.png" alt="Two crocs plotting something" loading="lazy" />
          <div className="split__copy">
            <span className="t-label brand">BEHIND DROP 001</span>
            <h2 className="t-display">Drops, not dumps.</h2>
            <p className="t-sub">Drop-wise releases give each collection its own identity. They build anticipation, make the store feel like a discovery, and give you a reason to come back.</p>
            <p>Every design is chosen for a drop, not dumped into a catalogue. Printed on 300 GSM glossy sheets so the colours stay as loud as the idea. Packed tamper-proof and at your door in 4-5 days.</p>
            <Link className="btn" href="/shop">
              [ Shop the drop ]
            </Link>
          </div>
        </div>
      </section>
      <section className="wrap dark section" style={{ paddingTop: 96, paddingBottom: 96 }}>
        <h2 className="t-display">How it is made.</h2>
        <Steps />
      </section>
      <section className="wrap section" style={{ display: "flex", gap: 56, alignItems: "center", flexWrap: "wrap", justifyContent: "center" }}>
        <img src="/assets/croc-wordmark.png" alt="" style={{ width: 240 }} />
        <div style={{ display: "grid", gap: 20, justifyItems: "start", maxWidth: 620 }}>
          <h2 className="t-display">Meet the croc.</h2>
          <p className="t-sub">He picks the weekly favourite, approves the prints, and has opinions about your wall. He is not single, and he is not telling.</p>
          <Link className="btn-link" href="/faq">
            Ask us anything <span aria-hidden="true">→</span>
          </Link>
        </div>
      </section>
    </>
  )
}
