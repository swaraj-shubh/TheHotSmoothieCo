"use client"

import { useEffect, useState, useTransition } from "react"

import { verifyEmail } from "@/app/actions/auth"

/** Verification is a state change, so it's a POST (Server Action) triggered on load, never a GET:
 *  link scanners that pre-fetch email URLs can't consume the token. */
export function VerifyEmail({ token }: { token: string }) {
  const [result, setResult] = useState<{ ok: boolean; error?: string } | null>(null)
  const [, start] = useTransition()
  useEffect(() => start(async () => setResult(await verifyEmail(token))), [token])

  if (!result) return <p className="text-muted-foreground">Verifying…</p>
  return result.ok ? (
    <p className="text-emerald-700">Your email is verified. Thanks!</p>
  ) : (
    <p className="text-destructive">{result.error}</p>
  )
}
