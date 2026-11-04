"use client"

import type { ComponentProps, ReactNode } from "react"
import { useFormStatus } from "react-dom"

export type FormState = { ok: boolean; error?: string; message?: string; fields?: Record<string, string> } | null

/** The site's .field: mono label, linen input, cherry error line. */
export function Field({ label, name, state, error, hint, noError, ...props }: { label: string; name: string; state?: FormState; error?: string; hint?: ReactNode; noError?: boolean } & ComponentProps<"input">) {
  const message = error ?? (state && !state.ok ? state.fields?.[name] : undefined)
  const id = props.id ?? name
  return (
    <div className="field">
      <label htmlFor={id}>{label}</label>
      <input className="input" id={id} name={name} aria-invalid={message ? true : undefined} {...props} />
      {/* An empty .err still takes a grid row, as on the site. */}
      {hint && !message ? (
        <span className="t-cap muted">{hint}</span>
      ) : noError ? null : (
        <span className="err" role="alert">
          {message}
        </span>
      )}
    </div>
  )
}

export function FormMessage({ state }: { state: FormState }) {
  if (!state) return null
  if (state.ok) return state.message ? <p className="notice" role="status">{state.message}</p> : null
  return (
    <p className="notice notice--err" role="alert">
      {state.error}
    </p>
  )
}

export function SubmitButton({ children, pendingText, className = "btn", ...props }: ComponentProps<"button"> & { pendingText?: string }) {
  const { pending } = useFormStatus()
  return (
    <button type="submit" className={className} disabled={pending || props.disabled} {...props}>
      {pending ? (pendingText ?? "[ Please wait ]") : children}
    </button>
  )
}
