"use client"

import { useEffect } from "react"

export default function ShopError({ error, reset }: { error: Error & { digest?: string }; reset: () => void }) {
  useEffect(() => console.error(error), [error])
  return (
    <section className="err-page">
      <img src="/assets/croc-wordmark.png" alt="" />
      <h1 className="t-display">Something spilled.</h1>
      <p className="t-sub">This page did not load. Try again in a moment.</p>
      {error.digest && <p className="t-cap muted">Reference: {error.digest}</p>}
      <button className="btn" onClick={reset}>
        [ Try again ]
      </button>
    </section>
  )
}
