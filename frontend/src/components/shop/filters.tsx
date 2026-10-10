"use client"

import { usePathname, useRouter, useSearchParams } from "next/navigation"
import { useTransition } from "react"
import { SlidersHorizontal } from "lucide-react"

import { Button } from "@/components/ui/button"
import { Checkbox } from "@/components/ui/checkbox"
import { Label } from "@/components/ui/label"
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select"
import { Sheet, SheetContent, SheetHeader, SheetTitle, SheetTrigger } from "@/components/ui/sheet"
import type { AttributeOut } from "@/lib/api/types"

const PRICES = [
  ["under-500", "Under ₹500"],
  ["500-1000", "₹500 – ₹1,000"],
  ["1000-2000", "₹1,000 – ₹2,000"],
  ["2000-plus", "₹2,000+"],
] as const

function useFilterParams() {
  const router = useRouter()
  const pathname = usePathname()
  const params = useSearchParams()
  const [pending, start] = useTransition()

  function update(mutate: (p: URLSearchParams) => void) {
    const next = new URLSearchParams(params)
    mutate(next)
    next.delete("cursor") // any filter change restarts pagination
    start(() => router.push(`${pathname}?${next}`, { scroll: false }))
  }
  const toggle = (key: string, value: string) =>
    update((p) => {
      const values = p.getAll(key)
      p.delete(key)
      for (const v of values.includes(value) ? values.filter((x) => x !== value) : [...values, value]) p.append(key, v)
    })
  return { params, update, toggle, pending }
}

function FilterPanel({ attributes }: { attributes: AttributeOut[] }) {
  const { params, update, toggle } = useFilterParams()
  const active = [...params.keys()].some((k) => k !== "sort" && k !== "q" && k !== "cursor")

  return (
    <div className="space-y-7 text-sm">
      <label className="flex items-center gap-2">
        <Checkbox
          checked={params.get("in_stock") === "1"}
          onCheckedChange={(c) => update((p) => (c ? p.set("in_stock", "1") : p.delete("in_stock")))}
        />
        In stock only
      </label>
      <fieldset className="space-y-2">
        <legend className="eyebrow mb-3 text-foreground">Price</legend>
        {PRICES.map(([value, label]) => (
          <label key={value} className="flex items-center gap-2">
            <Checkbox
              checked={params.get("price") === value}
              onCheckedChange={(c) => update((p) => (c ? p.set("price", value) : p.delete("price")))}
            />
            {label}
          </label>
        ))}
      </fieldset>
      {attributes.map((attr) => (
        <fieldset key={attr.code} className="space-y-2">
          <legend className="eyebrow mb-3 text-foreground">{attr.name}</legend>
          {attr.values.map((v) => (
            <label key={v.slug} className="flex items-center gap-2">
              <Checkbox
                checked={params.getAll(attr.code).includes(v.slug)}
                onCheckedChange={() => toggle(attr.code, v.slug)}
              />
              {v.value}
            </label>
          ))}
        </fieldset>
      ))}
      {active && (
        <Button
          variant="link"
          className="px-0"
          onClick={() =>
            update((p) => {
              for (const k of [...p.keys()]) if (k !== "sort" && k !== "q") p.delete(k)
            })
          }
        >
          Clear filters
        </Button>
      )}
    </div>
  )
}

export function Filters({
  attributes,
  showRelevance,
  showSort,
}: {
  attributes: AttributeOut[]
  showRelevance: boolean
  showSort: boolean
}) {
  const { params, update, pending } = useFilterParams()
  const sort = params.get("sort") ?? (showRelevance ? "relevance" : "newest")

  return (
    <>
      <aside className="hidden lg:row-span-2 lg:row-start-1 lg:block" aria-label="Filters" data-pending={pending || undefined}>
        <FilterPanel attributes={attributes} />
      </aside>
      <div className="flex items-center justify-between gap-3 lg:col-start-2 lg:row-start-1 lg:justify-end">
        <Sheet>
          <SheetTrigger asChild>
            <Button variant="outline" className="lg:hidden">
              <SlidersHorizontal /> Filters
            </Button>
          </SheetTrigger>
          <SheetContent side="left" className="overflow-y-auto">
            <SheetHeader>
              <SheetTitle>Filters</SheetTitle>
            </SheetHeader>
            <div className="px-4 pb-8">
              <FilterPanel attributes={attributes} />
            </div>
          </SheetContent>
        </Sheet>
        {showSort && (
          <div className="flex items-center gap-2">
            <Label htmlFor="sort" className="text-muted-foreground">
              Sort
            </Label>
            <Select value={sort} onValueChange={(v) => update((p) => p.set("sort", v))}>
              <SelectTrigger id="sort" className="w-44">
                <SelectValue />
              </SelectTrigger>
              <SelectContent>
                {showRelevance && <SelectItem value="relevance">Best match</SelectItem>}
                <SelectItem value="newest">Newest</SelectItem>
                <SelectItem value="price_asc">Price: low to high</SelectItem>
                <SelectItem value="price_desc">Price: high to low</SelectItem>
              </SelectContent>
            </Select>
          </div>
        )}
      </div>
    </>
  )
}
