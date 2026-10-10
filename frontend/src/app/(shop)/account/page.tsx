import type { Metadata } from "next"
import { Suspense } from "react"

import { ChangePasswordForm, ProfileForm } from "@/components/account/profile-forms"
import { requireUser } from "@/lib/session"

export const metadata: Metadata = { title: "Your account", robots: { index: false } }

async function Profile({ searchParams }: PageProps<"/account">) {
  const [user, sp] = await Promise.all([requireUser("/account"), searchParams])
  return (
    <div className="space-y-10">
      {sp.welcome && (
        <p className=" bg-secondary p-4 text-secondary-foreground">
          Welcome aboard, {user.full_name.split(" ")[0]}! Check your inbox to verify your email.
        </p>
      )}
      <section className="space-y-4">
        <h1 className="font-display text-5xl leading-none tracking-tight">Profile</h1>
        <p className="text-sm text-muted-foreground">
          {user.email} {user.email_verified ? "· verified" : "· not verified yet"}
        </p>
        <ProfileForm user={user} />
      </section>
      <section className="space-y-4">
        <h2 className="font-display text-3xl">Change password</h2>
        <ChangePasswordForm />
      </section>
    </div>
  )
}

export default function AccountPage(props: PageProps<"/account">) {
  return (
    <Suspense fallback={<div className="h-64 animate-pulse bg-muted" />}>
      <Profile {...props} />
    </Suspense>
  )
}
