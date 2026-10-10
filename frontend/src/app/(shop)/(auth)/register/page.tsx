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
      <h1 className="mb-2 font-display text-5xl leading-none tracking-tight">Join the club</h1>
      <p className="mb-6 text-sm text-muted-foreground">Track orders, save favourites and check out faster.</p>
      <Suspense>
        <Register {...props} />
      </Suspense>
    </>
  )
}
