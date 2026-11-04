import type { Metadata } from "next"
import { Suspense } from "react"

import { RegisterForm } from "./form"

export const metadata: Metadata = { title: "Create an account", robots: { index: false } }

async function Register({ searchParams }: PageProps<"/register">) {
  const sp = await searchParams
  return <RegisterForm next={typeof sp.next === "string" ? sp.next : "/account?welcome=1"} />
}

export default function RegisterPage(props: PageProps<"/register">) {
  return (
    <>
      <div style={{ display: "grid", gap: 16 }}>
        <span className="t-label brand">NEW HERE</span>
        <h1 className="t-display">Join the club.</h1>
        <p className="t-sub">Track orders, save favourites and check out faster.</p>
      </div>
      <Suspense>
        <Register {...props} />
      </Suspense>
    </>
  )
}
