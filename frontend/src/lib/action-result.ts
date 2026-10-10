import "server-only"

import { unstable_rethrow } from "next/navigation"

import { ApiError } from "./api/client"

export type ActionResult<T = void> =
  | { ok: true; data?: T; message?: string }
  | { ok: false; error: string; code?: string; fields?: Record<string, string>; details?: unknown }

/** Run a Server Function body and turn API errors into a form-friendly result.
 *  Framework control flow (redirect, notFound) passes through untouched. */
export async function action<T>(fn: () => Promise<T>, message?: string): Promise<ActionResult<T>> {
  try {
    const data = await fn()
    return { ok: true, data, message }
  } catch (err) {
    unstable_rethrow(err) // redirect(), notFound()… are control flow, not failures
    if (err instanceof ApiError) {
      const fields: Record<string, string> = {}
      if (err.code === "VALIDATION_ERROR" && Array.isArray(err.details)) {
        for (const d of err.details as { field: string; message: string }[]) fields[d.field] = d.message
      }
      return { ok: false, error: err.message, code: err.code, fields, details: err.details }
    }
    console.error(err)
    return { ok: false, error: "Something went wrong. Please try again." }
  }
}
