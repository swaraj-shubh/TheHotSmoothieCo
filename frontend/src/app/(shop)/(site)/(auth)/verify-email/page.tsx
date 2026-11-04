import type { Metadata } from "next"
import Link from "next/link"
import { Suspense } from "react"

import { VerifyEmail } from "./verify"

export const metadata: Metadata = { title: "Verify your email", robots: { index: false } }

async function Verify({ searchParams }: PageProps<"/verify-email">) {
  const { token } = await searchParams
  if (typeof token !== "string") return <p className="notice notice--err">This verification link is incomplete.</p>
  return <VerifyEmail token={token} />
}

export default function VerifyEmailPage(props: PageProps<"/verify-email">) {
  return (
    <>
      <h1 className="t-display">Email verification.</h1>
      <Suspense fallback={<p className="t-sub">Verifying…</p>}>
        <Verify {...props} />
      </Suspense>
      <Link className="btn btn--outline" href="/shop" style={{ width: "fit-content" }}>
        [ Continue shopping ]
      </Link>
    </>
  )
}
