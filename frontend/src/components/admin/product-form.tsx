"use client"

import { useMemo, useState, useTransition } from "react"
import { toast } from "sonner"

import { createProduct, updateProduct } from "@/app/actions/admin"
import { Button } from "@/components/ui/button"
import { Checkbox } from "@/components/ui/checkbox"
import { Input } from "@/components/ui/input"
import { Label } from "@/components/ui/label"
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select"
import { Textarea } from "@/components/ui/textarea"
import type { AdminCategoryOut, AdminCollectionOut, AdminProductOut, AttributeOut } from "@/lib/api/types"
import { toPaise } from "@/lib/format"

type VariantRow = { key: string; attributes: Record<string, string>; sku: string; price: string; compare: string; weight: string; stock: string }

function slugCode(s: string) {
  return s.replace(/[^A-Za-z0-9]+/g, "").slice(0, 3).toUpperCase()
}

/** Cartesian product of chosen option values, e.g. sizes × frames. */
function combos(chosen: [string, string[]][]): Record<string, string>[] {
  return chosen.reduce<Record<string, string>[]>(
    (acc, [code, values]) => acc.flatMap((c) => values.map((v) => ({ ...c, [code]: v }))),
    [{}],
  )
}

export function ProductForm({
  product,
  categories,
  collections,
  attributes,
}: {
  product?: AdminProductOut
  categories: AdminCategoryOut[]
  collections: AdminCollectionOut[]
  attributes: AttributeOut[]
}) {
  const [pending, start] = useTransition()
  const [title, setTitle] = useState(product?.title ?? "")
  const [status, setStatus] = useState(product?.status ?? "DRAFT")
  const [categoryId, setCategoryId] = useState(product?.category?.id ?? "")
  const [collectionIds, setCollectionIds] = useState<string[]>(product?.collections.map((c) => c.id) ?? [])
  const [chosen, setChosen] = useState<Record<string, string[]>>({})
  const [rows, setRows] = useState<VariantRow[]>([])
  const [base, setBase] = useState({ price: "", stock: "10", weight: "250" })

  const prefix = useMemo(() => title.split(/\s+/).map((w) => w[0] ?? "").join("").toUpperCase().slice(0, 4) || "SKU", [title])

  function generate() {
    const picked = Object.entries(chosen).filter(([, v]) => v.length) as [string, string[]][]
    setRows(
      combos(picked).map((attrs) => ({
        key: JSON.stringify(attrs),
        attributes: attrs,
        sku: [prefix, ...Object.values(attrs).map(slugCode)].join("-"),
        price: base.price,
        compare: "",
        weight: base.weight,
        stock: base.stock,
      })),
    )
  }

  function submit(form: FormData) {
    const fields = {
      title,
      slug: String(form.get("slug") || "").trim() || null,
      short_description: String(form.get("short_description") || "") || null,
      description: String(form.get("description") || "") || null,
      seo_title: String(form.get("seo_title") || "") || null,
      seo_description: String(form.get("seo_description") || "") || null,
      category_id: categoryId || null,
      collection_ids: collectionIds,
      tags: String(form.get("tags") || "").split(",").map((t) => t.trim()).filter(Boolean),
      status: status as "DRAFT" | "ACTIVE" | "ARCHIVED",
    }
    start(async () => {
      if (product) {
        const r = await updateProduct(product.id, fields)
        if (r.ok) toast.success(r.message)
        else toast.error(r.error)
        return
      }
      if (!rows.length) return void toast.error("Generate at least one variant")
      const variants = rows.map((r) => ({
        sku: r.sku,
        price_paise: toPaise(r.price) ?? -1,
        compare_at_price_paise: toPaise(r.compare),
        weight_grams: r.weight ? Number(r.weight) : null,
        attributes: r.attributes,
        initial_stock: Number(r.stock || 0),
        low_stock_threshold: 5,
        position: 0,
      }))
      if (variants.some((v) => v.price_paise < 0)) return void toast.error("Every variant needs a valid price")
      const r = await createProduct({ ...fields, variants })
      if (!r.ok) toast.error(r.error)
    })
  }

  return (
    <form action={submit} className="space-y-8">
      <section className="grid gap-4 rounded-xl border bg-card p-5 md:grid-cols-2">
        <div className="space-y-1.5 md:col-span-2">
          <Label htmlFor="title">Title</Label>
          <Input id="title" value={title} onChange={(e) => setTitle(e.target.value)} required maxLength={200} />
        </div>
        <div className="space-y-1.5">
          <Label htmlFor="slug">URL slug</Label>
          <Input id="slug" name="slug" defaultValue={product?.slug} placeholder="auto from title" pattern="[a-z0-9]+(-[a-z0-9]+)*" />
        </div>
        <div className="space-y-1.5">
          <Label>Status</Label>
          <Select value={status} onValueChange={setStatus}>
            <SelectTrigger className="w-full">
              <SelectValue />
            </SelectTrigger>
            <SelectContent>
              <SelectItem value="DRAFT">Draft (hidden)</SelectItem>
              <SelectItem value="ACTIVE">Active (on sale)</SelectItem>
              <SelectItem value="ARCHIVED">Archived</SelectItem>
            </SelectContent>
          </Select>
        </div>
        <div className="space-y-1.5">
          <Label>Category</Label>
          <Select value={categoryId || "none"} onValueChange={(v) => setCategoryId(v === "none" ? "" : v)}>
            <SelectTrigger className="w-full">
              <SelectValue />
            </SelectTrigger>
            <SelectContent>
              <SelectItem value="none">No category</SelectItem>
              {categories.map((c) => (
                <SelectItem key={c.id} value={c.id}>
                  {c.parent_id ? "— " : ""}
                  {c.name}
                </SelectItem>
              ))}
            </SelectContent>
          </Select>
        </div>
        <div className="space-y-1.5">
          <Label htmlFor="tags">Tags (comma separated)</Label>
          <Input id="tags" name="tags" defaultValue={product?.tags.map((t) => t.name).join(", ")} />
        </div>
        <fieldset className="space-y-2 md:col-span-2">
          <legend className="text-sm font-medium">Collections</legend>
          <div className="flex flex-wrap gap-4">
            {collections.map((c) => (
              <label key={c.id} className="flex items-center gap-2 text-sm">
                <Checkbox
                  checked={collectionIds.includes(c.id)}
                  onCheckedChange={(on) => setCollectionIds((ids) => (on ? [...ids, c.id] : ids.filter((i) => i !== c.id)))}
                />
                {c.name}
              </label>
            ))}
          </div>
        </fieldset>
        <div className="space-y-1.5 md:col-span-2">
          <Label htmlFor="short_description">Short description</Label>
          <Input id="short_description" name="short_description" defaultValue={product?.short_description ?? ""} maxLength={500} />
        </div>
        <div className="space-y-1.5 md:col-span-2">
          <Label htmlFor="description">Description</Label>
          <Textarea id="description" name="description" rows={5} defaultValue={product?.description ?? ""} />
        </div>
        <div className="space-y-1.5">
          <Label htmlFor="seo_title">SEO title</Label>
          <Input id="seo_title" name="seo_title" maxLength={160} defaultValue={product?.seo_title ?? ""} />
        </div>
        <div className="space-y-1.5">
          <Label htmlFor="seo_description">SEO description</Label>
          <Input id="seo_description" name="seo_description" maxLength={320} defaultValue={product?.seo_description ?? ""} />
        </div>
      </section>

      {!product && (
        <section className="space-y-4 rounded-xl border bg-card p-5">
          <h2 className="font-semibold">Variants</h2>
          <p className="text-sm text-muted-foreground">Pick the options this print comes in, then generate every combination.</p>
          <div className="grid gap-4 md:grid-cols-3">
            {attributes.map((a) => (
              <fieldset key={a.code} className="space-y-1.5">
                <legend className="text-sm font-medium">{a.name}</legend>
                {a.values.map((v) => (
                  <label key={v.id} className="flex items-center gap-2 text-sm">
                    <Checkbox
                      checked={chosen[a.code]?.includes(v.value) ?? false}
                      onCheckedChange={(on) =>
                        setChosen((c) => ({
                          ...c,
                          [a.code]: on ? [...(c[a.code] ?? []), v.value] : (c[a.code] ?? []).filter((x) => x !== v.value),
                        }))
                      }
                    />
                    {v.value}
                  </label>
                ))}
              </fieldset>
            ))}
          </div>
          <div className="flex flex-wrap items-end gap-3">
            <div className="space-y-1">
              <Label htmlFor="base-price">Default price (₹)</Label>
              <Input id="base-price" value={base.price} onChange={(e) => setBase({ ...base, price: e.target.value })} className="w-32" inputMode="decimal" />
            </div>
            <div className="space-y-1">
              <Label htmlFor="base-stock">Stock each</Label>
              <Input id="base-stock" value={base.stock} onChange={(e) => setBase({ ...base, stock: e.target.value })} className="w-24" inputMode="numeric" />
            </div>
            <Button type="button" variant="outline" onClick={generate}>
              Generate variants
            </Button>
          </div>
          {rows.length > 0 && (
            <div className="overflow-x-auto">
              <table className="w-full text-sm">
                <thead className="text-left text-muted-foreground">
                  <tr>
                    <th className="py-2 pr-3 font-medium">Options</th>
                    <th className="pr-3 font-medium">SKU</th>
                    <th className="pr-3 font-medium">Price ₹</th>
                    <th className="pr-3 font-medium">Compare at ₹</th>
                    <th className="pr-3 font-medium">Weight g</th>
                    <th className="pr-3 font-medium">Stock</th>
                    <th />
                  </tr>
                </thead>
                <tbody>
                  {rows.map((r, i) => {
                    const set = (k: keyof VariantRow, v: string) => setRows((rs) => rs.map((x, j) => (j === i ? { ...x, [k]: v } : x)))
                    return (
                      <tr key={r.key} className="border-t">
                        <td className="py-2 pr-3">{Object.values(r.attributes).join(" / ") || "Default"}</td>
                        <td className="pr-3"><Input aria-label="SKU" value={r.sku} onChange={(e) => set("sku", e.target.value)} className="h-8 w-40 font-mono" /></td>
                        <td className="pr-3"><Input aria-label="Price" value={r.price} onChange={(e) => set("price", e.target.value)} className="h-8 w-24" inputMode="decimal" /></td>
                        <td className="pr-3"><Input aria-label="Compare-at price" value={r.compare} onChange={(e) => set("compare", e.target.value)} className="h-8 w-24" inputMode="decimal" /></td>
                        <td className="pr-3"><Input aria-label="Weight" value={r.weight} onChange={(e) => set("weight", e.target.value)} className="h-8 w-20" inputMode="numeric" /></td>
                        <td className="pr-3"><Input aria-label="Stock" value={r.stock} onChange={(e) => set("stock", e.target.value)} className="h-8 w-20" inputMode="numeric" /></td>
                        <td>
                          <Button type="button" variant="ghost" size="sm" onClick={() => setRows((rs) => rs.filter((_, j) => j !== i))}>
                            Remove
                          </Button>
                        </td>
                      </tr>
                    )
                  })}
                </tbody>
              </table>
            </div>
          )}
        </section>
      )}

      <div className="flex gap-3">
        <Button type="submit" disabled={pending}>
          {pending ? "Saving…" : product ? "Save product" : "Create product"}
        </Button>
      </div>
    </form>
  )
}
