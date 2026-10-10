import "server-only"

import { cookies } from "next/headers"
import { connection } from "next/server"
import { notFound, redirect } from "next/navigation"
import { cache } from "react"

import { api, COOKIE } from "./api/client"
import { can, type Section } from "./admin-access"
import type { Role, UserOut } from "./api/types"

const secure = process.env.NODE_ENV === "production"
const base = { httpOnly: true, secure, sameSite: "lax" as const, path: "/" }
export const REFRESH_MAX_AGE = 30 * 24 * 3600

/** Server Actions / Route Handlers only (cookies can't be set while rendering). */
export async function setAuthCookies(tokens: { access_token: string; refresh_token?: string | null; expires_in: number }) {
  const jar = await cookies()
  jar.set(COOKIE.access, tokens.access_token, { ...base, maxAge: tokens.expires_in })
  if (tokens.refresh_token) jar.set(COOKIE.refresh, tokens.refresh_token, { ...base, maxAge: REFRESH_MAX_AGE })
}

export async function clearAuthCookies() {
  const jar = await cookies()
  jar.delete(COOKIE.access)
  jar.delete(COOKIE.refresh)
}

export async function setCartCookie(token: string) {
  ;(await cookies()).set(COOKIE.cart, token, { ...base, maxAge: REFRESH_MAX_AGE })
}

export async function clearCartCookie() {
  ;(await cookies()).delete(COOKIE.cart)
}

/** The signed-in user, or null. Memoised per request; the backend re-validates the session
 *  on every call, so a logged-out or deactivated account is never served from here. */
export const getCurrentUser = cache(async (): Promise<UserOut | null> => {
  await connection()
  const jar = await cookies()
  if (!jar.get(COOKIE.access)) return null
  const { data, response } = await (await api()).GET("/api/v1/users/me")
  return response.ok && data ? data : null
})

export async function requireUser(next = "/account"): Promise<UserOut> {
  const user = await getCurrentUser()
  if (!user) redirect(`/login?next=${encodeURIComponent(next)}`)
  return user
}

export function hasRole(user: UserOut | null, ...roles: Role[]): boolean {
  if (!user) return false
  return user.roles.includes("SUPER_ADMIN") || roles.some((r) => user.roles.includes(r))
}

export const isStaff = (user: UserOut | null) => !!user && user.roles.length > 0

/** UI gate only (non-staff get a 404, hiding the admin area). The API enforces every
 *  permission again on each request. */
export async function requireStaff(section: Section = "dashboard"): Promise<UserOut> {
  const user = await requireUser("/admin/dashboard")
  if (!isStaff(user) || !can(user.roles, section)) notFound()
  return user
}
