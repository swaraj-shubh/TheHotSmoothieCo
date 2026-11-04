"use client"

import Link from "next/link"
import { useActionState } from "react"

import { register } from "@/app/actions/auth"
import { Field, FormMessage, SubmitButton } from "@/components/sf/forms"

export function RegisterForm({ next }: { next: string }) {
  const [state, action] = useActionState(register, null)
  return (
    <form action={action} className="auth-form">
      <FormMessage state={state} />
      <input type="hidden" name="next" value={next} />
      <Field label="Full name" name="full_name" autoComplete="name" required maxLength={120} state={state} />
      <Field label="Email" name="email" type="email" autoComplete="email" required state={state} />
      <Field label="Phone (optional)" name="phone" type="tel" autoComplete="tel" placeholder="+91 98765 43210" state={state} />
      <Field label="Password" name="password" type="password" autoComplete="new-password" required minLength={8} maxLength={128} hint="At least 8 characters." state={state} />
      <SubmitButton className="btn btn--block" pendingText="[ Creating account ]">
        [ Create account ]
      </SubmitButton>
      <p className="t-cap muted">
        Already have an account?{" "}
        <Link href={`/login?next=${encodeURIComponent(next)}`} style={{ textDecoration: "underline" }}>
          Sign in
        </Link>
      </p>
    </form>
  )
}
