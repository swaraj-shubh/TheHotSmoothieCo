import Link from "next/link"
import type { ReactNode } from "react"

import { Button } from "@/components/ui/button"
import { cn } from "@/lib/utils"

export function AdminPage({
  title,
  description,
  actions,
  children,
}: {
  title: string
  description?: string
  actions?: ReactNode
  children: ReactNode
}) {
  return (
    <div className="space-y-6">
      <div className="flex flex-wrap items-end justify-between gap-4">
        <div>
          <h1 className="font-display text-4xl leading-none tracking-tight">{title}</h1>
          {description && <p className="text-sm text-muted-foreground">{description}</p>}
        </div>
        {actions && <div className="flex flex-wrap gap-2">{actions}</div>}
      </div>
      {children}
    </div>
  )
}

export function Empty({ title, children }: { title: string; children?: ReactNode }) {
  return (
    <div className="rounded-xl border border-dashed px-6 py-14 text-center">
      <p className="font-medium">{title}</p>
      {children && <div className="mt-2 text-sm text-muted-foreground">{children}</div>}
    </div>
  )
}

export function TableSkeleton({ rows = 6 }: { rows?: number }) {
  return (
    <div className="space-y-2" aria-busy>
      {Array.from({ length: rows }, (_, i) => (
        <div key={i} className="h-11 animate-pulse rounded-lg bg-muted" />
      ))}
    </div>
  )
}

/** Keyset pagination: "next" carries the cursor; "first" drops it. Other params are preserved. */
export function CursorPager({
  basePath,
  params,
  nextCursor,
}: {
  basePath: string
  params: Record<string, string | string[] | undefined>
  nextCursor?: string | null
}) {
  const qs = (cursor?: string) => {
    const p = new URLSearchParams()
    for (const [k, v] of Object.entries(params)) if (k !== "cursor") for (const x of [v ?? []].flat()) p.append(k, x)
    if (cursor) p.set("cursor", cursor)
    const s = p.toString()
    return s ? `${basePath}?${s}` : basePath
  }
  if (!params.cursor && !nextCursor) return null
  return (
    <div className="flex justify-end gap-2">
      {params.cursor && (
        <Button asChild variant="outline" size="sm">
          <Link href={qs()}>← First page</Link>
        </Button>
      )}
      {nextCursor && (
        <Button asChild variant="outline" size="sm">
          <Link href={qs(nextCursor)}>Next →</Link>
        </Button>
      )}
    </div>
  )
}

export function StatCard({
  label,
  value,
  hint,
  href,
  tone = "default",
}: {
  label: string
  value: ReactNode
  hint?: ReactNode
  href?: string
  tone?: "default" | "warn" | "danger"
}) {
  const body = (
    <div
      className={cn(
        "h-full rounded-xl border bg-card p-4 transition",
        href && "hover:border-foreground/30 hover:shadow-sm",
        tone === "warn" && "border-amber-300 bg-amber-50",
        tone === "danger" && "border-red-300 bg-red-50",
      )}
    >
      <p className="text-xs font-medium tracking-wide text-muted-foreground uppercase">{label}</p>
      <p className="mt-1 text-2xl font-semibold tabular-nums">{value}</p>
      {hint && <p className="mt-1 text-xs text-muted-foreground">{hint}</p>}
    </div>
  )
  return href ? <Link href={href}>{body}</Link> : body
}

/** Tabs implemented as links (server-rendered, shareable URLs). */
export function LinkTabs({ tabs, active }: { tabs: { href: string; label: string; key: string }[]; active: string }) {
  return (
    <nav className="flex flex-wrap gap-1 border-b" aria-label="Filter">
      {tabs.map((t) => (
        <Link
          key={t.key}
          href={t.href}
          aria-current={t.key === active ? "page" : undefined}
          className={cn(
            "-mb-px border-b-2 px-3 py-2 text-sm",
            t.key === active ? "border-foreground font-medium text-foreground" : "border-transparent text-muted-foreground hover:text-foreground",
          )}
        >
          {t.label}
        </Link>
      ))}
    </nav>
  )
}

/** Dependency-free bar chart (SVG), e.g. revenue per day. */
export function BarChart({
  data,
  format,
  height = 180,
}: {
  data: { label: string; value: number }[]
  format: (v: number) => string
  height?: number
}) {
  const max = Math.max(1, ...data.map((d) => d.value))
  const w = 100 / Math.max(data.length, 1)
  return (
    <figure className="space-y-2">
      <svg viewBox={`0 0 100 ${height}`} preserveAspectRatio="none" className="h-44 w-full" role="img" aria-label="Chart">
        {data.map((d, i) => {
          const h = (d.value / max) * (height - 4)
          return (
            <rect key={i} x={i * w + w * 0.15} y={height - h} width={w * 0.7} height={h} rx="0.6" className="fill-foreground">
              <title>{`${d.label}: ${format(d.value)}`}</title>
            </rect>
          )
        })}
      </svg>
      <figcaption className="flex justify-between text-xs text-muted-foreground">
        <span>{data[0]?.label}</span>
        <span>peak {format(max)}</span>
        <span>{data.at(-1)?.label}</span>
      </figcaption>
    </figure>
  )
}
