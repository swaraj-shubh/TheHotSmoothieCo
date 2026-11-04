import type { Metadata } from "next"
import Link from "next/link"

export const metadata: Metadata = { title: "Page not found", description: "This page does not exist." }

export default function NotFound() {
  return (
    <section className="err-page">
      <img src="/assets/croc-wordmark.png" alt="" />
      <span className="t-label brand">404</span>
      <h1 className="t-display">This page has worse taste than you.</h1>
      <p className="t-sub">It does not exist. The croc looked everywhere.</p>
      <Link className="btn" href="/">
        [ Back home ]
      </Link>
    </section>
  )
}
