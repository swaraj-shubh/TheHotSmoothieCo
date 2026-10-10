"use client"

import Link from "next/link"
import { usePathname } from "next/navigation"

import { NAV, can } from "@/lib/admin-access"
import { cn } from "@/lib/utils"

export function AdminSidebar({ roles, name }: { roles: string[]; name: string }) {
  const pathname = usePathname()
  return (
    <nav aria-label="Admin" className="flex flex-col gap-0.5 text-sm">
      {NAV.filter((n) => can(roles, n.section)).map((n) => {
        const active = pathname === n.href || pathname.startsWith(`${n.href}/`)
        return (
          <Link
            key={n.href}
            href={n.href}
            aria-current={active ? "page" : undefined}
            className={cn(
              "rounded-lg px-3 py-2",
              active ? "bg-foreground font-medium text-background" : "text-muted-foreground hover:bg-muted hover:text-foreground",
            )}
          >
            {n.label}
          </Link>
        )
      })}
      <p className="mt-6 truncate px-3 text-xs text-muted-foreground" title={name}>
        Signed in as {name}
      </p>
    </nav>
  )
}
