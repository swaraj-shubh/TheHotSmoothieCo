"use client"

import Link from "next/link"
import { useActionState } from "react"

import { login } from "@/app/actions/auth"
import { Field, FormMessage, SubmitButton } from "@/components/forms"

export function LoginForm({ next, notice }: { next: string; notice?: string }) {
  const [state, action] = useActionState(login, null)
  return (
    <form action={action} className="space-y-4">
      {notice && !state && <p className="rounded-lg bg-secondary px-3 py-2 text-sm text-secondary-foreground">{notice}</p>}
      <FormMessage state={state} />
      <input type="hidden" name="next" value={next} />
      <Field label="Email" name="email" type="email" autoComplete="email" required state={state} />
      <Field label="Password" name="password" type="password" autoComplete="current-password" required state={state} />
      <div className="flex justify-end text-sm">
        <Link href="/forgot-password" className="underline underline-offset-4">
          Forgot password?
        </Link>
      </div>
      <SubmitButton className="h-10 w-full" pendingText="Signing in…">
        Sign in
      </SubmitButton>
      <p className="text-center text-sm text-muted-foreground">
        New here?{" "}
        <Link href={`/register?next=${encodeURIComponent(next)}`} className="underline underline-offset-4">
          Create an account
        </Link>
      </p>
    </form>
  )
}
