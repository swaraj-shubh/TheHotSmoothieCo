"use client"

import { useActionState, useEffect, useState, useTransition } from "react"
import { toast } from "sonner"

import { createCoupon, deleteBanner, resetTemplate, saveBanner, saveTemplate, setRoles } from "@/app/actions/admin"
import { ActionButton } from "@/components/admin/action-button"
import { Field, FormMessage, SubmitButton } from "@/components/forms"
import { Badge } from "@/components/ui/badge"
import { Button } from "@/components/ui/button"
import { Checkbox } from "@/components/ui/checkbox"
import { Dialog, DialogContent, DialogHeader, DialogTitle, DialogTrigger } from "@/components/ui/dialog"
import { Label } from "@/components/ui/label"
import { Textarea } from "@/components/ui/textarea"
import type { BannerOut, Role, StaffOut, TemplateOut } from "@/lib/api/types"
import { ROLES } from "@/lib/api/types"
import { titleCase } from "@/lib/format"

const select = "h-8 w-full rounded-lg border bg-background px-2 text-sm"

/** `<input type="datetime-local">` wants local "YYYY-MM-DDTHH:mm". */
const localInput = (iso?: string | null) => {
  if (!iso) return ""
  const d = new Date(iso)
  return new Date(d.getTime() - d.getTimezoneOffset() * 60_000).toISOString().slice(0, 16)
}

function useDone(state: { ok: boolean; message?: string } | null, done: () => void) {
  useEffect(() => {
    if (state?.ok) {
      toast.success(state.message)
      done()
    }
  }, [state, done])
}

// ---------- Coupons ----------

export function CouponCreate() {
  const [open, setOpen] = useState(false)
  const [type, setType] = useState<"PERCENT" | "FIXED">("PERCENT")
  const [state, action] = useActionState(createCoupon, null)
  useDone(state, () => setOpen(false))
  return (
    <Dialog open={open} onOpenChange={setOpen}>
      <DialogTrigger asChild>
        <Button>New coupon</Button>
      </DialogTrigger>
      <DialogContent className="max-h-[90vh] overflow-y-auto">
        <DialogHeader>
          <DialogTitle>New coupon</DialogTitle>
        </DialogHeader>
        <form action={action} className="space-y-3">
          <FormMessage state={state && !state.ok ? state : null} />
          <Field label="Code" name="code" required placeholder="MONSOON20" className="uppercase" state={state} />
          <Field label="Description (internal)" name="description" state={state} />
          <div className="grid grid-cols-2 gap-3">
            <div className="space-y-1.5">
              <Label htmlFor="discount_type">Type</Label>
              <select id="discount_type" name="discount_type" value={type} onChange={(e) => setType(e.target.value as "PERCENT" | "FIXED")} className={select}>
                <option value="PERCENT">Percent off</option>
                <option value="FIXED">Fixed ₹ off</option>
              </select>
            </div>
            <Field
              label={type === "PERCENT" ? "Percent (1–100)" : "Amount (₹)"}
              name="value"
              required
              inputMode="decimal"
              {...(type === "PERCENT" ? { type: "number", min: 1, max: 100 } : {})}
              state={state}
            />
            {type === "PERCENT" && <Field label="Max discount (₹, optional)" name="max_discount" inputMode="decimal" state={state} />}
            <Field label="Minimum cart (₹)" name="min_subtotal" inputMode="decimal" placeholder="0" state={state} />
            <Field label="Total uses (blank = unlimited)" name="usage_limit" type="number" min={1} state={state} />
            <Field label="Uses per customer" name="per_user_limit" type="number" min={1} state={state} />
            <Field label="Starts" name="starts_at" type="datetime-local" state={state} />
            <Field label="Ends" name="ends_at" type="datetime-local" state={state} />
          </div>
          <label className="flex items-center gap-2 text-sm">
            <Checkbox name="first_order_only" /> First order only
          </label>
          <SubmitButton>Create coupon</SubmitButton>
        </form>
      </DialogContent>
    </Dialog>
  )
}

// ---------- Banners ----------

function BannerForm({ banner, done }: { banner?: BannerOut; done: () => void }) {
  const [state, action] = useActionState(saveBanner, null)
  useDone(state, done)
  return (
    <form action={action} className="space-y-3">
      <FormMessage state={state && !state.ok ? state : null} />
      {banner && <input type="hidden" name="id" value={banner.id} />}
      <Field label="Title" name="title" required defaultValue={banner?.title} state={state} />
      <Field label="Subtitle" name="subtitle" defaultValue={banner?.subtitle ?? ""} state={state} />
      <Field label="Image URL (https)" name="image_url" type="url" required defaultValue={banner?.image_url} state={state} />
      <Field label="Link (e.g. /collection/new)" name="link_url" defaultValue={banner?.link_url ?? ""} state={state} />
      <div className="grid grid-cols-2 gap-3">
        <div className="space-y-1.5">
          <Label htmlFor="placement">Placement</Label>
          <select id="placement" name="placement" defaultValue={banner?.placement ?? "HOME_HERO"} className={select}>
            <option value="HOME_HERO">Home hero</option>
            <option value="HOME_STRIP">Home strip</option>
            <option value="SHOP_TOP">Top of shop</option>
          </select>
        </div>
        <Field label="Sort order" name="sort_order" type="number" defaultValue={banner?.sort_order ?? 0} state={state} />
        <Field label="Starts" name="starts_at" type="datetime-local" defaultValue={localInput(banner?.starts_at)} state={state} />
        <Field label="Ends" name="ends_at" type="datetime-local" defaultValue={localInput(banner?.ends_at)} state={state} />
      </div>
      <label className="flex items-center gap-2 text-sm">
        <Checkbox name="is_active" defaultChecked={banner?.is_active ?? true} /> Live
      </label>
      <SubmitButton>Save banner</SubmitButton>
    </form>
  )
}

function BannerDialog({ banner, trigger }: { banner?: BannerOut; trigger: React.ReactNode }) {
  const [open, setOpen] = useState(false)
  return (
    <Dialog open={open} onOpenChange={setOpen}>
      <DialogTrigger asChild>{trigger}</DialogTrigger>
      <DialogContent className="max-h-[90vh] overflow-y-auto">
        <DialogHeader>
          <DialogTitle>{banner ? "Edit banner" : "New banner"}</DialogTitle>
        </DialogHeader>
        <BannerForm banner={banner} done={() => setOpen(false)} />
      </DialogContent>
    </Dialog>
  )
}

export function BannerManager({ banners }: { banners: BannerOut[] }) {
  return (
    <div className="space-y-3">
      <BannerDialog trigger={<Button size="sm">New banner</Button>} />
      {banners.length === 0 ? (
        <p className="text-sm text-muted-foreground">No banners. The home page falls back to its built-in hero.</p>
      ) : (
        <ul className="divide-y rounded-lg border">
          {banners.map((b) => (
            <li key={b.id} className="flex flex-wrap items-center gap-3 p-3 text-sm">
              <span className="flex-1">
                <span className="font-medium">{b.title}</span>{" "}
                <span className="text-muted-foreground">
                  · {titleCase(b.placement)} · #{b.sort_order}
                </span>
                {!b.is_active && (
                  <Badge variant="secondary" className="ml-2">
                    Off
                  </Badge>
                )}
              </span>
              <BannerDialog banner={b} trigger={<Button size="sm" variant="outline">Edit</Button>} />
              <ActionButton size="sm" variant="ghost" run={() => deleteBanner(b.id)} confirm={{ title: `Delete “${b.title}”?`, action: "Delete" }}>
                Delete
              </ActionButton>
            </li>
          ))}
        </ul>
      )}
    </div>
  )
}

// ---------- Notification templates ----------

export function TemplateEditor({ template }: { template: TemplateOut }) {
  const [state, action] = useActionState(saveTemplate, null)
  useEffect(() => {
    if (state?.ok) toast.success(state.message)
  }, [state])
  return (
    <details className="rounded-lg border p-4">
      <summary className="cursor-pointer text-sm">
        <span className="font-medium">{titleCase(template.code)}</span>
        {template.is_overridden && (
          <Badge variant="secondary" className="ml-2">
            Customised
          </Badge>
        )}
      </summary>
      <form action={action} className="mt-4 space-y-3">
        <FormMessage state={state && !state.ok ? state : null} />
        <input type="hidden" name="code" value={template.code} />
        <Field label="Subject" name="subject" required defaultValue={template.subject} state={state} />
        <div className="space-y-1.5">
          <Label htmlFor={`body-${template.code}`}>Body</Label>
          <Textarea id={`body-${template.code}`} name="body" required rows={10} defaultValue={template.body} className="font-mono text-xs" />
          <p className="text-xs text-muted-foreground">
            Placeholders: {template.placeholders.map((p) => `{{ ${p} }}`).join(", ") || "none"}
          </p>
        </div>
        <div className="flex gap-2">
          <SubmitButton size="sm">Save</SubmitButton>
          {template.is_overridden && (
            <ActionButton
              size="sm"
              variant="ghost"
              run={() => resetTemplate(template.code)}
              confirm={{ title: "Reset to the default text?", description: "Your edits to this template are discarded.", action: "Reset" }}
            >
              Reset to default
            </ActionButton>
          )}
        </div>
      </form>
    </details>
  )
}

// ---------- Staff roles (SUPER_ADMIN) ----------

export function RoleEditor({ member, isSelf }: { member: StaffOut; isSelf: boolean }) {
  const [roles, setLocal] = useState<Role[]>(member.roles as Role[])
  const [pending, start] = useTransition()
  const dirty = roles.slice().sort().join() !== member.roles.slice().sort().join()
  return (
    <div className="flex flex-wrap items-center gap-x-4 gap-y-2">
      {ROLES.map((r) => (
        <label key={r} className="flex items-center gap-1.5 text-xs">
          <Checkbox
            checked={roles.includes(r)}
            // Removing your own SUPER_ADMIN would lock you out of this screen.
            disabled={isSelf && r === "SUPER_ADMIN"}
            onCheckedChange={(c) => setLocal((cur) => (c ? [...cur, r] : cur.filter((x) => x !== r)))}
          />
          {titleCase(r)}
        </label>
      ))}
      <Button
        size="sm"
        variant="outline"
        disabled={!dirty || pending}
        onClick={() =>
          start(async () => {
            const res = await setRoles(member.id, roles)
            if (res.ok) toast.success(res.message)
            else toast.error(res.error)
          })
        }
      >
        Save roles
      </Button>
    </div>
  )
}
