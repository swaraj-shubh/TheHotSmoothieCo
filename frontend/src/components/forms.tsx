"use client"

import type { ComponentProps, ReactNode } from "react"
import { useFormStatus } from "react-dom"

import { Button } from "@/components/ui/button"
import { Input } from "@/components/ui/input"
import { Label } from "@/components/ui/label"

export type FormState = { ok: boolean; error?: string; message?: string; fields?: Record<string, string> } | null

export function Field({
  label,
  name,
  state,
  hint,
  ...props
}: { label: string; name: string; state?: FormState; hint?: ReactNode } & ComponentProps<typeof Input>) {
  const error = state && !state.ok ? state.fields?.[name] : undefined
  const id = props.id ?? name
  return (
    <div className="space-y-1.5">
      <Label htmlFor={id}>{label}</Label>
      <Input
        id={id}
        name={name}
        aria-invalid={!!error || undefined}
        aria-describedby={error ? `${id}-error` : undefined}
        {...props}
      />
      {error ? (
        <p id={`${id}-error`} className="text-sm text-destructive">
          {error}
        </p>
      ) : (
        hint && <p className="text-xs text-muted-foreground">{hint}</p>
      )}
    </div>
  )
}

export function FormMessage({ state }: { state: FormState }) {
  if (!state) return null
  if (state.ok)
    return state.message ? (
      <p role="status" className="rounded-lg bg-emerald-50 px-3 py-2 text-sm text-emerald-800">
        {state.message}
      </p>
    ) : null
  return (
    <p role="alert" className="rounded-lg bg-destructive/10 px-3 py-2 text-sm text-destructive">
      {state.error}
    </p>
  )
}

export function SubmitButton({ children, pendingText, ...props }: ComponentProps<typeof Button> & { pendingText?: string }) {
  const { pending } = useFormStatus()
  return (
    <Button type="submit" disabled={pending || props.disabled} {...props}>
      {pending ? (pendingText ?? "Please wait…") : children}
    </Button>
  )
}
