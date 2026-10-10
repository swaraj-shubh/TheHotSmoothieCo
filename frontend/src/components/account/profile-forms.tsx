"use client"

import { useActionState } from "react"

import { updateProfile } from "@/app/actions/account"
import { changePassword } from "@/app/actions/auth"
import { Field, FormMessage, SubmitButton } from "@/components/forms"
import { Checkbox } from "@/components/ui/checkbox"
import { Label } from "@/components/ui/label"
import type { UserOut } from "@/lib/api/types"

export function ProfileForm({ user }: { user: UserOut }) {
  const [state, action] = useActionState(updateProfile, null)
  return (
    <form action={action} className="max-w-md space-y-4">
      <FormMessage state={state} />
      <Field label="Full name" name="full_name" defaultValue={user.full_name} required state={state} />
      <Field label="Phone" name="phone" type="tel" defaultValue={user.phone ?? ""} state={state} />
      <div className="flex items-center gap-2">
        <Checkbox
          id="marketing_emails"
          name="marketing_emails"
          defaultChecked={(user.preferences as { marketing_emails?: boolean }).marketing_emails !== false}
        />
        <Label htmlFor="marketing_emails" className="font-normal">
          Email me about new drops and offers
        </Label>
      </div>
      <SubmitButton>Save changes</SubmitButton>
    </form>
  )
}

export function ChangePasswordForm() {
  const [state, action] = useActionState(changePassword, null)
  return (
    <form action={action} className="max-w-md space-y-4">
      <FormMessage state={state} />
      <Field label="Current password" name="current_password" type="password" autoComplete="current-password" required state={state} />
      <Field
        label="New password"
        name="new_password"
        type="password"
        autoComplete="new-password"
        required
        minLength={8}
        state={state}
      />
      <SubmitButton variant="outline">Change password</SubmitButton>
    </form>
  )
}
