"use server"

import { cookies } from "next/headers"
import { redirect } from "next/navigation"

import { action, type ActionResult } from "@/lib/action-result"
import { api, API_URL, COOKIE, unwrap } from "@/lib/api/client"
import { clearAuthCookies, clearCartCookie, setAuthCookies } from "@/lib/session"

/** Only same-site relative paths: never redirect to another origin after login. */
function safeNext(value: FormDataEntryValue | null, fallback = "/account"): string {
  const next = String(value ?? "")
  return next.startsWith("/") && !next.startsWith("//") && !next.startsWith("/\\") ? next : fallback
}

/** Fold the guest cart (if any) into the account that just signed in. */
async function mergeGuestCart(accessToken: string) {
  const jar = await cookies()
  const cartToken = jar.get(COOKIE.cart)?.value
  if (!cartToken) return
  await fetch(`${API_URL}/api/v1/cart/merge`, {
    method: "POST",
    headers: {
      Authorization: `Bearer ${accessToken}`,
      "X-Cart-Token": cartToken,
      ...(process.env.BFF_SECRET ? { "X-BFF-Secret": process.env.BFF_SECRET } : {}),
    },
    cache: "no-store",
  }).catch(() => undefined) // a failed merge must not block sign-in; the guest cart stays put
  await clearCartCookie()
}

export async function login(_: ActionResult | null, form: FormData): Promise<ActionResult> {
  const result = await action(async () => {
    const tokens = unwrap(
      await (await api()).POST("/api/v1/auth/login", {
        body: { email: String(form.get("email") ?? ""), password: String(form.get("password") ?? "") },
      }),
    )
    await setAuthCookies(tokens)
    await mergeGuestCart(tokens.access_token)
  })
  if (result.ok) redirect(safeNext(form.get("next")))
  return result
}

export async function register(_: ActionResult | null, form: FormData): Promise<ActionResult> {
  const result = await action(async () => {
    const tokens = unwrap(
      await (await api()).POST("/api/v1/auth/register", {
        body: {
          full_name: String(form.get("full_name") ?? ""),
          email: String(form.get("email") ?? ""),
          password: String(form.get("password") ?? ""),
          phone: String(form.get("phone") ?? "") || null,
        },
      }),
    )
    await setAuthCookies(tokens)
    await mergeGuestCart(tokens.access_token)
  })
  if (result.ok) redirect(safeNext(form.get("next"), "/account?welcome=1"))
  return result
}

export async function logout(): Promise<void> {
  await (await api()).POST("/api/v1/auth/logout").catch(() => undefined)
  await clearAuthCookies()
  redirect("/")
}

export async function forgotPassword(_: ActionResult | null, form: FormData): Promise<ActionResult> {
  return action(
    async () =>
      void unwrap(
        await (await api()).POST("/api/v1/auth/forgot-password", { body: { email: String(form.get("email") ?? "") } }),
      ),
    "If an account exists for that email, we've sent a reset link.",
  )
}

export async function resetPassword(_: ActionResult | null, form: FormData): Promise<ActionResult> {
  const result = await action(async () => {
    unwrap(
      await (await api()).POST("/api/v1/auth/reset-password", {
        body: { token: String(form.get("token") ?? ""), new_password: String(form.get("password") ?? "") },
      }),
    )
    await clearAuthCookies() // every session was revoked by the reset
  })
  if (result.ok) redirect("/login?reset=1")
  return result
}

export async function verifyEmail(token: string): Promise<ActionResult> {
  return action(async () => {
    unwrap(await (await api()).POST("/api/v1/auth/verify-email", { body: { token } }))
  })
}

export async function changePassword(_: ActionResult | null, form: FormData): Promise<ActionResult> {
  return action(async () => {
    unwrap(
      await (await api()).POST("/api/v1/auth/change-password", {
        body: {
          current_password: String(form.get("current_password") ?? ""),
          new_password: String(form.get("new_password") ?? ""),
        },
      }),
    )
  }, "Password changed. Other devices have been signed out.")
}
