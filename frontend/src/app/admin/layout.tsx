import type { Metadata } from "next"
import Image from "next/image"
import Link from "next/link"
import { Suspense } from "react"

import { AdminSidebar } from "@/components/admin/sidebar"
import { requireStaff } from "@/lib/session"

export const metadata: Metadata = {
  title: { default: "Admin", template: "%s · Admin" },
  robots: { index: false, follow: false },
}

async function Sidebar() {
  const user = await requireStaff()
  return <AdminSidebar roles={user.roles} name={user.full_name} />
}

export default function AdminLayout({ children }: LayoutProps<"/admin">) {
  return (
    <div className="flex min-h-screen flex-col bg-muted/40">
      <header className="flex h-14 items-center gap-3 border-b bg-background px-4">
        <Link href="/admin/dashboard" className="flex items-baseline gap-3">
          <Image src="/logo.png" alt="" width={24} height={24} className="self-center rounded-[5px]" />
          <span className="font-display text-xl leading-none">The Hot Smoothie Co.</span>
          <span className="eyebrow">Admin</span>
        </Link>
        <Link href="/" className="ml-auto text-sm text-muted-foreground hover:text-foreground">
          View store →
        </Link>
      </header>
      <div className="mx-auto grid w-full max-w-[1400px] flex-1 gap-6 p-4 md:grid-cols-[200px_1fr] md:p-6">
        <aside className="md:sticky md:top-6 md:h-fit">
          <Suspense fallback={<div className="h-80 animate-pulse rounded-xl bg-muted" />}>
            <Sidebar />
          </Suspense>
        </aside>
        <main className="min-w-0">{children}</main>
      </div>
    </div>
  )
}
