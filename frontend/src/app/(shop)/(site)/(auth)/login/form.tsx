"use client"

import Link from "next/link"
import { useActionState } from "react"

import { login } from "@/app/actions/auth"
import { Field, FormMessage, SubmitButton } from "@/components/sf/forms"

export function LoginForm({ next, notice }: { next: string; notice?: string }) {
  const [state, action] = useActionState(login, null)
  return (
    <form action={action} className="auth-form">
      {notice && !state && <p className="notice">{notice}</p>}
      <FormMessage state={state} />
      <input type="hidden" name="next" value={next} />
      <Field label="Email" name="email" type="email" autoComplete="email" required state={state} />
      <Field label="Password" name="password" type="password" autoComplete="current-password" required state={state} />
      <Link href="/forgot-password" className="link-quiet" style={{ width: "fit-content" }}>
        Forgot password?
      </Link>
      <SubmitButton className="btn btn--block" pendingText="[ Signing in ]">
        [ Sign in ]
      </SubmitButton>
      <p className="t-cap muted">
        New here?{" "}
        <Link href={`/register?next=${encodeURIComponent(next)}`} style={{ textDecoration: "underline" }}>
          Create an account
        </Link>
      </p>
    </form>
  )
}
