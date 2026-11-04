import { Suspense } from "react"

import { BannerManager, RoleEditor } from "@/components/admin/editors"
import { AdminPage, CursorPager, TableSkeleton } from "@/components/admin/ui"
import { Badge } from "@/components/ui/badge"
import { can } from "@/lib/admin-access"
import { api, unwrap } from "@/lib/api/client"
import { formatDateTime, rupees } from "@/lib/format"
import { requireStaff } from "@/lib/session"

type StoreSettings = {
  environment: string
  pricing: {
    prices_include_tax: boolean
    tax_rate_bps: number
    shipping_flat_paise: number
    free_shipping_threshold_paise: number
    return_window_days: number
    inventory_hold_seconds: number
  }
  integrations: Record<string, string | null>
}

function Section({ title, description, children }: { title: string; description?: string; children: React.ReactNode }) {
  return (
    <section className="space-y-3 rounded-xl border bg-card p-5 text-sm">
      <div>
        <h2 className="font-semibold">{title}</h2>
        {description && <p className="text-muted-foreground">{description}</p>}
      </div>
      {children}
    </section>
  )
}

async function Store() {
  const s = unwrap(await (await api()).GET("/api/v1/admin/settings")) as StoreSettings
  const p = s.pricing
  const rows: [string, string][] = [
    ["GST", `${p.tax_rate_bps / 100}% ${p.prices_include_tax ? "(included in prices)" : "(added at checkout)"}`],
    ["Shipping", `${rupees(p.shipping_flat_paise)} flat, free over ${rupees(p.free_shipping_threshold_paise)}`],
    ["Returns", `${p.return_window_days} days after delivery`],
    ["Checkout stock hold", `${Math.round(p.inventory_hold_seconds / 60)} minutes`],
  ]
  return (
    <>
      <Section title="Store policy" description="Set through server environment variables (see docs/ENVIRONMENT.md).">
        <dl className="grid gap-x-6 gap-y-1 sm:grid-cols-[180px_1fr]">
          {rows.map(([k, v]) => (
            <div key={k} className="contents">
              <dt className="text-muted-foreground">{k}</dt>
              <dd>{v}</dd>
            </div>
          ))}
        </dl>
      </Section>
      <Section title="Integrations" description={`Environment: ${s.environment}. Secrets are never shown here.`}>
        <ul className="grid gap-2 sm:grid-cols-2">
          {Object.entries(s.integrations).map(([k, v]) => (
            <li key={k} className="flex items-center justify-between rounded-lg border px-3 py-2">
              <span className="capitalize">{k.replace("_", " ")}</span>
              {v ? <Badge variant={v === "dev" || v === "console" ? "secondary" : "default"}>{v}</Badge> : <Badge variant="destructive">Not configured</Badge>}
            </li>
          ))}
        </ul>
      </Section>
    </>
  )
}

async function Banners() {
  const banners = unwrap(await (await api()).GET("/api/v1/admin/banners"))
  return (
    <Section title="Banners" description="Home page and shop banners. Scheduled ones go live on their own.">
      <BannerManager banners={banners} />
    </Section>
  )
}

async function Staff({ selfId }: { selfId: string }) {
  const staff = unwrap(await (await api()).GET("/api/v1/admin/users"))
  return (
    <Section title="Staff & roles" description="Give someone a role after they've registered a normal account. Changes apply on their next request.">
      <ul className="divide-y">
        {staff.map((m) => (
          <li key={m.id} className="space-y-2 py-3">
            <p>
              <span className="font-medium">{m.full_name}</span> <span className="text-muted-foreground">{m.email}</span>
              {!m.is_active && (
                <Badge variant="destructive" className="ml-2">
                  Deactivated
                </Badge>
              )}
            </p>
            <RoleEditor member={m} isSelf={m.id === selfId} />
          </li>
        ))}
      </ul>
    </Section>
  )
}

async function Audit({ cursor }: { cursor?: string }) {
  const page = unwrap(await (await api()).GET("/api/v1/admin/audit-logs", { params: { query: { cursor, limit: 25 } } }))
  return (
    <Section title="Audit log" description="Every staff change, newest first.">
      <ul className="divide-y font-mono text-xs">
        {page.items.map((a) => (
          <li key={a.id} className="flex flex-wrap gap-x-3 py-1.5">
            <span className="text-muted-foreground">{formatDateTime(a.created_at)}</span>
            <span>{a.actor_email ?? "system"}</span>
            <span className={a.status_code >= 400 ? "text-destructive" : ""}>{a.action}</span>
            <span className="text-muted-foreground">{a.path}</span>
          </li>
        ))}
      </ul>
      <CursorPager basePath="/admin/settings" params={{ cursor }} nextCursor={page.next_cursor} />
    </Section>
  )
}

async function Settings({ searchParams }: PageProps<"/admin/settings">) {
  const user = await requireStaff()
  const sp = await searchParams
  return (
    <div className="space-y-6">
      <Store />
      {can(user.roles, "marketing") && <Banners />}
      {can(user.roles, "roles") && <Staff selfId={user.id} />}
      {can(user.roles, "audit") && <Audit cursor={typeof sp.cursor === "string" ? sp.cursor : undefined} />}
    </div>
  )
}

export default function SettingsPage(props: PageProps<"/admin/settings">) {
  return (
    <AdminPage title="Settings">
      <Suspense fallback={<TableSkeleton rows={10} />}>
        <Settings {...props} />
      </Suspense>
    </AdminPage>
  )
}
