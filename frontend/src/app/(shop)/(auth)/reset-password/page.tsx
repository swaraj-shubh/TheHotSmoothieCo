import type { Metadata } from "next"
import { Suspense } from "react"

import { ResetForm } from "./form"

export const metadata: Metadata = { title: "Choose a new password", robots: { index: false } }

async function Reset({ searchParams }: PageProps<"/reset-password">) {
  const { token } = await searchParams
  if (typeof token !== "string") return <p className="text-sm text-destructive">This reset link is incomplete.</p>
  return <ResetForm token={token} />
}

export default function ResetPasswordPage(props: PageProps<"/reset-password">) {
  return (
    <>
      <h1 className="mb-6 font-display text-5xl leading-none tracking-tight">New password</h1>
      <Suspense>
        <Reset {...props} />
      </Suspense>
    </>
  )
}
