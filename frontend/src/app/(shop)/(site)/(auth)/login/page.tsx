import type { Metadata } from "next"
import { Suspense } from "react"

import { LoginForm } from "./form"

export const metadata: Metadata = { title: "Sign in", robots: { index: false } }

async function Login({ searchParams }: PageProps<"/login">) {
  const sp = await searchParams
  const next = typeof sp.next === "string" ? sp.next : "/account"
  const notice = sp.reset ? "Password updated. Sign in with your new password." : undefined
  return <LoginForm next={next} notice={notice} />
}

export default function LoginPage(props: PageProps<"/login">) {
  return (
    <>
      <div style={{ display: "grid", gap: 16 }}>
        <span className="t-label brand">WELCOME BACK</span>
        <h1 className="t-display">Sign in.</h1>
        <p className="t-sub">Your walls missed you.</p>
      </div>
      <Suspense>
        <Login {...props} />
      </Suspense>
    </>
  )
}
