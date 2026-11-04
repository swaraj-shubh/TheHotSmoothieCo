import type { Metadata } from "next"
import { Suspense } from "react"

import { ChangePasswordForm, ProfileForm } from "@/components/sf/account"
import { requireUser } from "@/lib/session"

export const metadata: Metadata = { title: "Your account", robots: { index: false } }

async function Profile({ searchParams }: PageProps<"/account">) {
  const [user, sp] = await Promise.all([requireUser("/account"), searchParams])
  return (
    <div style={{ display: "grid", gap: 72 }}>
      <div style={{ display: "grid", gap: 28 }}>
        {sp.welcome && <p className="notice">Welcome aboard, {user.full_name.split(" ")[0]}! Check your inbox to verify your email.</p>}
        <h1 className="t-display">Hi, {user.full_name.split(" ")[0]}.</h1>
        <p className="t-cap muted">
          {user.email} · {user.email_verified ? "verified" : "not verified yet"}
        </p>
        <ProfileForm user={user} />
      </div>
      <div style={{ display: "grid", gap: 28 }}>
        <h2 className="t-head">Change password</h2>
        <ChangePasswordForm />
      </div>
    </div>
  )
}

export default function AccountPage(props: PageProps<"/account">) {
  return (
    <Suspense fallback={null}>
      <Profile {...props} />
    </Suspense>
  )
}
