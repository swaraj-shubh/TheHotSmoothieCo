"use client"

import { useActionState, useEffect, useState } from "react"
import { toast } from "sonner"

import { createAttribute, deleteCategory, deleteCollection, saveCategory, saveCollection } from "@/app/actions/admin"
import { ActionButton } from "@/components/admin/action-button"
import { Field, FormMessage, SubmitButton } from "@/components/forms"
import { Badge } from "@/components/ui/badge"
import { Button } from "@/components/ui/button"
import { Checkbox } from "@/components/ui/checkbox"
import { Label } from "@/components/ui/label"
import { Dialog, DialogContent, DialogHeader, DialogTitle, DialogTrigger } from "@/components/ui/dialog"
import type { AdminCategoryOut, AdminCollectionOut, AttributeOut } from "@/lib/api/types"

type Item = AdminCategoryOut | AdminCollectionOut
type Kind = "category" | "collection"

function TaxonomyForm({ kind, item, parents, onDone }: { kind: Kind; item?: Item; parents?: AdminCategoryOut[]; onDone: () => void }) {
  const [state, action] = useActionState(kind === "category" ? saveCategory : saveCollection, null)
  useEffect(() => {
    if (state?.ok) {
      toast.success(state.message)
      onDone()
    }
  }, [state, onDone])
  return (
    <form action={action} className="space-y-3">
      <FormMessage state={state && !state.ok ? state : null} />
      {item && <input type="hidden" name="id" value={item.id} />}
      <Field label="Name" name="name" required defaultValue={item?.name} state={state} />
      <Field label="Slug" name="slug" defaultValue={item?.slug} placeholder="auto from name" state={state} />
      {kind === "category" && (
        <div className="space-y-1.5">
          <Label htmlFor="parent_id">Parent category</Label>
          <select
            id="parent_id"
            name="parent_id"
            defaultValue={(item as AdminCategoryOut | undefined)?.parent_id ?? ""}
            className="h-8 w-full rounded-lg border bg-background px-2 text-sm"
          >
            <option value="">None (top level)</option>
            {parents?.filter((p) => p.id !== item?.id).map((p) => (
              <option key={p.id} value={p.id}>
                {p.name}
              </option>
            ))}
          </select>
        </div>
      )}
      <Field label="Description" name="description" defaultValue={item?.description ?? ""} state={state} />
      <Field label="Image URL (https)" name="image_url" defaultValue={item?.image_url ?? ""} state={state} />
      <div className="grid grid-cols-2 gap-3">
        <Field label="Sort order" name="sort_order" type="number" defaultValue={item?.sort_order ?? 0} state={state} />
        <label className="flex items-end gap-2 pb-2 text-sm">
          <Checkbox name="is_active" defaultChecked={item?.is_active ?? true} /> Visible in store
        </label>
      </div>
      <Field label="SEO title" name="seo_title" defaultValue={item?.seo_title ?? ""} state={state} />
      <Field label="SEO description" name="seo_description" defaultValue={item?.seo_description ?? ""} state={state} />
      <SubmitButton>Save</SubmitButton>
    </form>
  )
}

function EditDialog({ kind, item, parents, trigger }: { kind: Kind; item?: Item; parents?: AdminCategoryOut[]; trigger: React.ReactNode }) {
  const [open, setOpen] = useState(false)
  return (
    <Dialog open={open} onOpenChange={setOpen}>
      <DialogTrigger asChild>{trigger}</DialogTrigger>
      <DialogContent className="max-h-[90vh] overflow-y-auto">
        <DialogHeader>
          <DialogTitle>{item ? `Edit ${item.name}` : `New ${kind}`}</DialogTitle>
        </DialogHeader>
        <TaxonomyForm kind={kind} item={item} parents={parents} onDone={() => setOpen(false)} />
      </DialogContent>
    </Dialog>
  )
}

export function TaxonomyManager({ kind, items }: { kind: Kind; items: Item[] }) {
  const parents = kind === "category" ? (items as AdminCategoryOut[]) : undefined
  const byId = new Map(items.map((i) => [i.id, i]))
  return (
    <div className="space-y-4">
      <EditDialog kind={kind} parents={parents} trigger={<Button>New {kind}</Button>} />
      {items.length === 0 ? (
        <p className="rounded-xl border border-dashed p-10 text-center text-sm text-muted-foreground">No {kind === "category" ? "categories" : "collections"} yet.</p>
      ) : (
        <ul className="divide-y rounded-xl border bg-card">
          {items.map((item) => {
            const parent = "parent_id" in item && item.parent_id ? byId.get(item.parent_id) : null
            return (
              <li key={item.id} className="flex flex-wrap items-center gap-3 p-4">
                <div className="flex-1">
                  <p className="font-medium">
                    {parent && <span className="text-muted-foreground">{parent.name} / </span>}
                    {item.name}
                    {!item.is_active && (
                      <Badge variant="secondary" className="ml-2">
                        Hidden
                      </Badge>
                    )}
                  </p>
                  <p className="text-xs text-muted-foreground">/{kind}/{item.slug}</p>
                </div>
                <EditDialog kind={kind} item={item} parents={parents} trigger={<Button variant="outline" size="sm">Edit</Button>} />
                <ActionButton
                  size="sm"
                  variant="ghost"
                  run={() => (kind === "category" ? deleteCategory(item.id) : deleteCollection(item.id))}
                  confirm={{
                    title: `Delete ${item.name}?`,
                    description:
                      kind === "category"
                        ? "Only empty categories (no products or sub-categories) can be deleted. Hide it instead to keep its products."
                        : "Products stay; they're just removed from this collection.",
                    action: "Delete",
                  }}
                >
                  Delete
                </ActionButton>
              </li>
            )
          })}
        </ul>
      )}
    </div>
  )
}

export function AttributesManager({ attributes }: { attributes: AttributeOut[] }) {
  const [state, action] = useActionState(createAttribute, null)
  return (
    <div className="space-y-4 rounded-xl border bg-card p-5">
      <h2 className="font-semibold">Product options</h2>
      <ul className="space-y-1 text-sm">
        {attributes.map((a) => (
          <li key={a.id}>
            <span className="font-medium">{a.name}</span> <span className="text-muted-foreground">({a.code})</span>:{" "}
            {a.values.map((v) => v.value).join(", ")}
          </li>
        ))}
      </ul>
      <form action={action} className="grid gap-3 sm:grid-cols-4">
        <Field label="Code" name="code" placeholder="paper" required state={state} />
        <Field label="Name" name="name" placeholder="Paper" required state={state} />
        <div className="sm:col-span-2">
          <Field label="Values (comma separated)" name="values" placeholder="Matte, Glossy" state={state} />
        </div>
        <div className="sm:col-span-4">
          <FormMessage state={state} />
          <SubmitButton size="sm" variant="outline" className="mt-2">
            Add option
          </SubmitButton>
        </div>
      </form>
    </div>
  )
}
