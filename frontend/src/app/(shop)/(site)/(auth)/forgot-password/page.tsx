"use client"

import { useActionState } from "react"

import { forgotPassword } from "@/app/actions/auth"
import { Field, FormMessage, SubmitButton } from "@/components/sf/forms"

export default function ForgotPasswordPage() {
  const [state, action] = useActionState(forgotPassword, null)
  return (
    <>
      <div style={{ display: "grid", gap: 16 }}>
        <h1 className="t-display">Forgot your password?</h1>
        <p className="t-sub">We&apos;ll email you a link to choose a new one.</p>
      </div>
      <form action={action} className="auth-form">
        <FormMessage state={state} />
        <Field label="Email" name="email" type="email" autoComplete="email" required state={state} />
        <SubmitButton className="btn btn--block">[ Send reset link ]</SubmitButton>
      </form>
    </>
  )
}
