"use client"

import { useActionState } from "react"

import { forgotPassword } from "@/app/actions/auth"
import { Field, FormMessage, SubmitButton } from "@/components/forms"

export default function ForgotPasswordPage() {
  const [state, action] = useActionState(forgotPassword, null)
  return (
    <>
      <h1 className="mb-2 font-display text-5xl leading-none tracking-tight">Forgot your password?</h1>
      <p className="mb-6 text-sm text-muted-foreground">We’ll email you a link to choose a new one.</p>
      <form action={action} className="space-y-4">
        <FormMessage state={state} />
        <Field label="Email" name="email" type="email" autoComplete="email" required state={state} />
        <SubmitButton className="h-10 w-full">Send reset link</SubmitButton>
      </form>
    </>
  )
}
