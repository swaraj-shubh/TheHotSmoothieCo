import { Suspense } from "react"

import { retryNotification } from "@/app/actions/admin"
import { ActionButton } from "@/components/admin/action-button"
import { TemplateEditor } from "@/components/admin/editors"
import { AdminPage, CursorPager, Empty, LinkTabs, TableSkeleton } from "@/components/admin/ui"
import { Badge } from "@/components/ui/badge"
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from "@/components/ui/table"
import { can } from "@/lib/admin-access"
import { api, unwrap } from "@/lib/api/client"
import { formatDateTime, titleCase } from "@/lib/format"
import { getCurrentUser, requireStaff } from "@/lib/session"

const TABS = [
  ["all", "All"],
  ["FAILED", "Failed"],
  ["PENDING", "Queued"],
  ["SENT", "Sent"],
  ["SKIPPED", "Skipped"],
] as const

async function Log({ searchParams }: PageProps<"/admin/notifications">) {
  await requireStaff("notifications")
  const sp = await searchParams
  const status = TABS.find(([k]) => k !== "all" && k === sp.status)?.[0] as Exclude<(typeof TABS)[number][0], "all"> | undefined
  const page = unwrap(
    await (await api()).GET("/api/v1/admin/notifications", {
      params: { query: { status, cursor: typeof sp.cursor === "string" ? sp.cursor : undefined, limit: 50 } },
    }),
  )
  return (
    <div className="space-y-4">
      <LinkTabs
        active={status ?? "all"}
        tabs={TABS.map(([key, label]) => ({ key, label, href: key === "all" ? "/admin/notifications" : `/admin/notifications?status=${key}` }))}
      />
      {page.items.length === 0 ? (
        <Empty title="No messages here" />
      ) : (
        <div className="rounded-xl border bg-card">
          <Table>
            <TableHeader>
              <TableRow>
                <TableHead>Message</TableHead>
                <TableHead>To</TableHead>
                <TableHead>Created</TableHead>
                <TableHead>Status</TableHead>
                <TableHead />
              </TableRow>
            </TableHeader>
            <TableBody>
              {page.items.map((n) => (
                <TableRow key={n.id}>
                  <TableCell>
                    {titleCase(n.template)}
                    {n.subject && <p className="max-w-xs truncate text-xs text-muted-foreground">{n.subject}</p>}
                  </TableCell>
                  <TableCell className="text-sm">{n.recipient}</TableCell>
                  <TableCell className="text-sm text-muted-foreground">{formatDateTime(n.created_at)}</TableCell>
                  <TableCell>
                    <Badge variant={n.status === "FAILED" ? "destructive" : n.status === "SENT" ? "default" : "secondary"}>{titleCase(n.status)}</Badge>
                    {n.last_error && (
                      <p className="max-w-xs truncate text-xs text-destructive" title={n.last_error}>
                        {n.attempts} tries · {n.last_error}
                      </p>
                    )}
                  </TableCell>
                  <TableCell className="text-right">
                    {n.status === "FAILED" && (
                      <ActionButton size="sm" variant="outline" run={retryNotification.bind(null, n.id)}>
                        Retry
                      </ActionButton>
                    )}
                  </TableCell>
                </TableRow>
              ))}
            </TableBody>
          </Table>
        </div>
      )}
      <CursorPager basePath="/admin/notifications" params={sp} nextCursor={page.next_cursor} />
    </div>
  )
}

async function Templates() {
  const user = await getCurrentUser()
  if (!user || !can(user.roles, "marketing")) return null
  const templates = unwrap(await (await api()).GET("/api/v1/admin/notification-templates"))
  return (
    <section className="space-y-3">
      <h2 className="font-semibold">Email templates</h2>
      {templates.map((t) => (
        <TemplateEditor key={t.code} template={t} />
      ))}
    </section>
  )
}

export default function NotificationsPage(props: PageProps<"/admin/notifications">) {
  return (
    <AdminPage title="Notifications" description="Customer emails. Failed sends retry automatically with backoff; retry by hand once the cause is fixed.">
      <Suspense fallback={<TableSkeleton />}>
        <Log {...props} />
      </Suspense>
      <Suspense>
        <Templates />
      </Suspense>
    </AdminPage>
  )
}
