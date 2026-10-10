"use client"

import { useActionState, useEffect } from "react"

import { saveAddress } from "@/app/actions/account"
import { Field, FormMessage, SubmitButton } from "@/components/forms"
import { Checkbox } from "@/components/ui/checkbox"
import { Label } from "@/components/ui/label"
import type { AddressOut } from "@/lib/api/types"

// Pre-filled options for the state field (free text is still accepted by the API).
const STATES = [
  "Andhra Pradesh", "Arunachal Pradesh", "Assam", "Bihar", "Chhattisgarh", "Delhi", "Goa", "Gujarat", "Haryana",
  "Himachal Pradesh", "Jammu and Kashmir", "Jharkhand", "Karnataka", "Kerala", "Ladakh", "Madhya Pradesh", "Maharashtra",
  "Manipur", "Meghalaya", "Mizoram", "Nagaland", "Odisha", "Puducherry", "Punjab", "Rajasthan", "Sikkim", "Tamil Nadu",
  "Telangana", "Tripura", "Uttar Pradesh", "Uttarakhand", "West Bengal", "Andaman and Nicobar Islands", "Chandigarh",
  "Dadra and Nagar Haveli and Daman and Diu", "Lakshadweep",
]

export function AddressForm({
  address,
  onSaved,
  submitLabel = "Save address",
}: {
  address?: AddressOut
  onSaved?: (a: AddressOut) => void
  submitLabel?: string
}) {
  const [state, action] = useActionState(saveAddress, null)
  useEffect(() => {
    if (state?.ok && state.data) onSaved?.(state.data)
  }, [state, onSaved])

  return (
    <form action={action} className="grid gap-4 sm:grid-cols-2">
      <div className="sm:col-span-2">
        <FormMessage state={state && !state.ok ? state : null} />
      </div>
      {address && <input type="hidden" name="id" value={address.id} />}
      <Field label="Full name" name="full_name" autoComplete="name" required defaultValue={address?.full_name} state={state} />
      <Field
        label="Phone"
        name="phone"
        type="tel"
        autoComplete="tel"
        required
        defaultValue={address?.phone}
        placeholder="+91 98765 43210"
        state={state}
      />
      <div className="sm:col-span-2">
        <Field label="Address line 1" name="line1" autoComplete="address-line1" required defaultValue={address?.line1} state={state} />
      </div>
      <div className="sm:col-span-2">
        <Field label="Address line 2 (optional)" name="line2" autoComplete="address-line2" defaultValue={address?.line2 ?? ""} state={state} />
      </div>
      <Field label="Landmark (optional)" name="landmark" defaultValue={address?.landmark ?? ""} state={state} />
      <Field label="City" name="city" autoComplete="address-level2" required defaultValue={address?.city} state={state} />
      <Field
        label="State"
        name="state"
        autoComplete="address-level1"
        required
        list="in-states"
        defaultValue={address?.state}
        state={state}
      />
      <datalist id="in-states">
        {STATES.map((s) => (
          <option key={s} value={s} />
        ))}
      </datalist>
      <Field
        label="PIN code"
        name="postal_code"
        inputMode="numeric"
        autoComplete="postal-code"
        pattern="[1-9][0-9]{5}"
        title="6-digit PIN code"
        required
        defaultValue={address?.postal_code}
        state={state}
      />
      <div className="flex items-center gap-2 sm:col-span-2">
        <Checkbox id="is_default_shipping" name="is_default_shipping" defaultChecked={address?.is_default_shipping} />
        <Label htmlFor="is_default_shipping" className="font-normal">
          Use as my default delivery address
        </Label>
      </div>
      <div className="sm:col-span-2">
        <SubmitButton>{submitLabel}</SubmitButton>
      </div>
    </form>
  )
}
