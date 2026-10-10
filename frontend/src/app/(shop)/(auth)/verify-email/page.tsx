import type { Metadata } from "next"
import Link from "next/link"
import { Suspense } from "react"

import { Button } from "@/components/ui/button"

import { VerifyEmail } from "./verify"

export const metadata: Metadata = { title: "Verify your email", robots: { index: false } }

async function Verify({ searchParams }: PageProps<"/verify-email">) {
  const { token } = await searchParams
  if (typeof token !== "string") return <p className="text-sm text-destructive">This verification link is incomplete.</p>
  return <VerifyEmail token={token} />
}

export default function VerifyEmailPage(props: PageProps<"/verify-email">) {
  return (
    <div className="space-y-6 text-center">
      <h1 className="font-display text-5xl leading-none tracking-tight">Email verification</h1>
      <Suspense fallback={<p className="text-muted-foreground">Verifying…</p>}>
        <Verify {...props} />
      </Suspense>
      <Button asChild variant="outline">
        <Link href="/shop">Continue shopping</Link>
      </Button>
    </div>
  )
}
