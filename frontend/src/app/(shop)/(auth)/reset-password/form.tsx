"use client"

import { useActionState } from "react"

import { resetPassword } from "@/app/actions/auth"
import { Field, FormMessage, SubmitButton } from "@/components/forms"

export function ResetForm({ token }: { token: string }) {
  const [state, action] = useActionState(resetPassword, null)
  return (
    <form action={action} className="space-y-4">
      <FormMessage state={state} />
      <input type="hidden" name="token" value={token} />
      <Field
        label="New password"
        name="password"
        type="password"
        autoComplete="new-password"
        required
        minLength={8}
        maxLength={128}
        state={state}
      />
      <SubmitButton className="h-10 w-full">Set new password</SubmitButton>
    </form>
  )
}
