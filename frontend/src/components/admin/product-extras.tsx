"use client"

import Image from "next/image"
import { useActionState, useRef, useState, useTransition } from "react"
import { toast } from "sonner"

import { addVariant, deleteMedia, importProducts, updateMedia, updateVariant, uploadMedia } from "@/app/actions/admin"
import { ActionButton } from "@/components/admin/action-button"
import { FormMessage, SubmitButton } from "@/components/forms"
import { Badge } from "@/components/ui/badge"
import { Button } from "@/components/ui/button"
import { Checkbox } from "@/components/ui/checkbox"
import { Input } from "@/components/ui/input"
import type { AdminProductOut, AttributeOut } from "@/lib/api/types"
import { rupees, toPaise } from "@/lib/format"

export function VariantsEditor({ product, attributes }: { product: AdminProductOut; attributes: AttributeOut[] }) {
  const [pending, start] = useTransition()
  const codes = product.options.map((o) => o.code)

  return (
    <section className="space-y-4 rounded-xl border bg-card p-5">
      <h2 className="font-semibold">Variants & stock</h2>
      <div className="overflow-x-auto">
        <table className="w-full text-sm">
          <thead className="text-left text-muted-foreground">
            <tr>
              <th className="py-2 pr-3 font-medium">Variant</th>
              <th className="pr-3 font-medium">SKU</th>
              <th className="pr-3 font-medium">Price</th>
              <th className="pr-3 font-medium">Stock</th>
              <th className="pr-3 font-medium">Status</th>
              <th />
            </tr>
          </thead>
          <tbody>
            {product.variants.map((v) => (
              <tr key={v.id} className="border-t">
                <td className="py-2 pr-3">{v.title}</td>
                <td className="pr-3 font-mono text-xs">{v.sku}</td>
                <td className="pr-3">
                  <form
                    action={(f) =>
                      start(async () => {
                        const price = toPaise(f.get("price"))
                        if (price == null) return void toast.error("Enter a valid price")
                        const r = await updateVariant(product.id, v.id, {
                          price_paise: price,
                          compare_at_price_paise: toPaise(f.get("compare")),
                        })
                        if (r.ok) toast.success(r.message)
                        else toast.error(r.error)
                      })
                    }
                    className="flex gap-1"
                  >
                    <Input name="price" defaultValue={v.price_paise / 100} aria-label="Price" className="h-8 w-24" inputMode="decimal" />
                    <Input
                      name="compare"
                      defaultValue={v.compare_at_price_paise ? v.compare_at_price_paise / 100 : ""}
                      placeholder="MRP"
                      aria-label="Compare-at price"
                      className="h-8 w-24"
                      inputMode="decimal"
                    />
                    <Button size="sm" variant="outline" disabled={pending}>
                      Save
                    </Button>
                  </form>
                </td>
                <td className="pr-3 tabular-nums">
                  {v.on_hand} <span className="text-muted-foreground">({v.reserved} held)</span>
                </td>
                <td className="pr-3">{v.is_active ? <Badge>Active</Badge> : <Badge variant="secondary">Inactive</Badge>}</td>
                <td>
                  <ActionButton
                    size="sm"
                    variant="ghost"
                    run={() => updateVariant(product.id, v.id, { is_active: !v.is_active })}
                    confirm={v.is_active ? { title: `Deactivate ${v.title}?`, description: "It stops being sold; past orders are unaffected.", action: "Deactivate" } : undefined}
                  >
                    {v.is_active ? "Deactivate" : "Activate"}
                  </ActionButton>
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
      <details className="rounded-lg border p-4">
        <summary className="cursor-pointer text-sm font-medium">Add a variant</summary>
        <form
          className="mt-4 flex flex-wrap items-end gap-3"
          action={(f) =>
            start(async () => {
              const attrs: Record<string, string> = {}
              for (const c of codes) attrs[c] = String(f.get(`attr_${c}`) ?? "")
              const price = toPaise(f.get("price"))
              if (price == null) return void toast.error("Enter a valid price")
              const r = await addVariant(product.id, {
                sku: String(f.get("sku") ?? ""),
                price_paise: price,
                compare_at_price_paise: null,
                attributes: attrs,
                initial_stock: Number(f.get("stock") || 0),
                low_stock_threshold: 5,
                position: product.variants.length,
              })
              if (r.ok) toast.success(r.message)
              else toast.error(r.error)
            })
          }
        >
          {codes.map((code) => {
            const attr = attributes.find((a) => a.code === code)
            return (
              <label key={code} className="space-y-1 text-sm">
                <span className="block">{attr?.name ?? code}</span>
                <Input name={`attr_${code}`} list={`vals-${code}`} required className="h-8 w-32" />
                <datalist id={`vals-${code}`}>{attr?.values.map((v) => <option key={v.id} value={v.value} />)}</datalist>
              </label>
            )
          })}
          <label className="space-y-1 text-sm">
            <span className="block">SKU</span>
            <Input name="sku" required className="h-8 w-40 font-mono" />
          </label>
          <label className="space-y-1 text-sm">
            <span className="block">Price ₹</span>
            <Input name="price" required className="h-8 w-24" inputMode="decimal" />
          </label>
          <label className="space-y-1 text-sm">
            <span className="block">Stock</span>
            <Input name="stock" defaultValue="0" className="h-8 w-20" inputMode="numeric" />
          </label>
          <Button size="sm" disabled={pending}>
            Add
          </Button>
        </form>
      </details>
    </section>
  )
}

export function MediaManager({ product }: { product: AdminProductOut }) {
  const [pending, start] = useTransition()
  const fileRef = useRef<HTMLInputElement>(null)
  return (
    <section className="space-y-4 rounded-xl border bg-card p-5">
      <div className="flex items-center justify-between">
        <h2 className="font-semibold">Images</h2>
        <form
          action={(f) =>
            start(async () => {
              const r = await uploadMedia(product.id, f)
              if (r.ok) toast.success(r.message)
              else toast.error(r.error)
              if (fileRef.current) fileRef.current.value = ""
            })
          }
          className="flex items-center gap-2"
        >
          <Input ref={fileRef} type="file" name="file" accept="image/jpeg,image/png,image/webp" required className="h-8 w-56" />
          <Input name="alt_text" placeholder="Alt text" className="h-8 w-40" maxLength={300} />
          <Button size="sm" disabled={pending}>
            {pending ? "Uploading…" : "Upload"}
          </Button>
        </form>
      </div>
      {product.media.length === 0 ? (
        <p className="text-sm text-muted-foreground">No images yet. JPEG, PNG or WebP up to 15 MB.</p>
      ) : (
        <ul className="grid grid-cols-2 gap-4 sm:grid-cols-4">
          {product.media.map((m, i) => (
            <li key={m.id} className="space-y-2">
              <div className="relative aspect-[3/4] overflow-hidden rounded-lg bg-muted">
                <Image src={m.thumbnail_url} alt={m.alt_text ?? ""} fill sizes="200px" className="object-cover" />
                {i === 0 && <Badge className="absolute top-2 left-2">Cover</Badge>}
              </div>
              <form
                action={(f) =>
                  start(async () => {
                    const r = await updateMedia(product.id, m.id, { alt_text: String(f.get("alt") ?? "") || null })
                    if (r.ok) toast.success(r.message)
                    else toast.error(r.error)
                  })
                }
                className="flex gap-1"
              >
                <Input name="alt" defaultValue={m.alt_text ?? ""} aria-label="Alt text" className="h-7 text-xs" />
                <Button size="xs" variant="outline">
                  Save
                </Button>
              </form>
              <div className="flex gap-1">
                {i > 0 && (
                  <ActionButton size="xs" variant="ghost" run={() => updateMedia(product.id, m.id, { sort_order: -1 })}>
                    Make cover
                  </ActionButton>
                )}
                <ActionButton
                  size="xs"
                  variant="ghost"
                  run={() => deleteMedia(product.id, m.id)}
                  confirm={{ title: "Delete this image?", description: "It's removed from the store and the media storage.", action: "Delete" }}
                >
                  Delete
                </ActionButton>
              </div>
            </li>
          ))}
        </ul>
      )}
    </section>
  )
}

export function CsvImport() {
  const [state, action] = useActionState(importProducts, null)
  const [dryRun, setDryRun] = useState(true)
  const report = state?.ok ? (state.data as Record<string, number | boolean>) : null
  const rowErrors =
    state && !state.ok && state.code === "INVALID_CSV"
      ? ((state.details as { errors?: { row: number; error: string; product_slug?: string }[] } | undefined)?.errors ?? [])
      : []
  return (
    <details className="rounded-xl border bg-card p-4">
      <summary className="cursor-pointer text-sm font-medium">Bulk import from CSV</summary>
      <form action={action} className="mt-4 space-y-3 text-sm">
        <p className="text-muted-foreground">
          One row per variant. Start from <a href="/admin/products/export" download className="text-brand underline">an export</a> to get the right
          columns. Imports are all-or-nothing.
        </p>
        <Input type="file" name="file" accept=".csv,text/csv" required className="max-w-sm" />
        <label className="flex items-center gap-2">
          <Checkbox name="dry_run" checked={dryRun} onCheckedChange={(c) => setDryRun(!!c)} />
          Dry run (validate only, change nothing)
        </label>
        <SubmitButton size="sm">{dryRun ? "Validate file" : "Import now"}</SubmitButton>
        <FormMessage state={state && !state.ok ? state : null} />
        {rowErrors.length > 0 && (
          <ul className="max-h-64 overflow-y-auto rounded-lg bg-destructive/5 p-3 text-xs text-destructive">
            {rowErrors.slice(0, 100).map((e, i) => (
              <li key={i}>
                Row {e.row}
                {e.product_slug ? ` (${e.product_slug})` : ""}: {e.error}
              </li>
            ))}
          </ul>
        )}
        {report && (
          <p className="rounded-lg bg-secondary p-3 text-secondary-foreground">
            {report.dry_run ? "Dry run OK: " : "Imported: "}
            {report.products_created} new products, {report.products_updated} updated, {report.variants_created} new variants,{" "}
            {report.variants_updated} variants updated, {report.stock_adjusted} stock changes ({report.rows} rows).
          </p>
        )}
      </form>
    </details>
  )
}

export function PriceRange({ min, max }: { min?: number | null; max?: number | null }) {
  if (min == null) return <span className="text-muted-foreground">—</span>
  return <span>{min === max ? rupees(min) : `${rupees(min)} – ${rupees(max)}`}</span>
}
