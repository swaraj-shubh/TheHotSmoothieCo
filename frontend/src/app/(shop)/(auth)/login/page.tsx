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
      <h1 className="mb-6 font-display text-5xl leading-none tracking-tight">Welcome back</h1>
      <Suspense>
        <Login {...props} />
      </Suspense>
    </>
  )
}
