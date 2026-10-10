"use client"

import { useActionState, useState } from "react"
import { toast } from "sonner"

import { adjustStock } from "@/app/actions/admin"
import { Field, FormMessage, SubmitButton } from "@/components/forms"
import { Button } from "@/components/ui/button"
import { Dialog, DialogContent, DialogDescription, DialogHeader, DialogTitle, DialogTrigger } from "@/components/ui/dialog"
import { RadioGroup, RadioGroupItem } from "@/components/ui/radio-group"
import type { StockRow } from "@/lib/api/types"

export function StockAdjust({ row }: { row: StockRow }) {
  const [open, setOpen] = useState(false)
  const [mode, setMode] = useState<"delta" | "set">("delta")
  const [state, action] = useActionState(async (prev: Awaited<ReturnType<typeof adjustStock>> | null, form: FormData) => {
    const r = await adjustStock(prev, form)
    if (r.ok) {
      toast.success(r.message)
      setOpen(false)
    }
    return r
  }, null)

  return (
    <Dialog open={open} onOpenChange={setOpen}>
      <DialogTrigger asChild>
        <Button size="sm" variant="outline">
          Adjust
        </Button>
      </DialogTrigger>
      <DialogContent>
        <DialogHeader>
          <DialogTitle>Adjust {row.sku}</DialogTitle>
          <DialogDescription>
            On hand {row.on_hand}, {row.reserved} held by unpaid checkouts. Stock can’t go below what’s held.
          </DialogDescription>
        </DialogHeader>
        <form action={action} className="space-y-4">
          <FormMessage state={state && !state.ok ? state : null} />
          <input type="hidden" name="variant_id" value={row.variant_id} />
          <input type="hidden" name="mode" value={mode} />
          <RadioGroup value={mode} onValueChange={(v) => setMode(v as "delta" | "set")} className="flex gap-6 text-sm">
            <label className="flex items-center gap-2">
              <RadioGroupItem value="delta" /> Add / remove
            </label>
            <label className="flex items-center gap-2">
              <RadioGroupItem value="set" /> Set exact count
            </label>
          </RadioGroup>
          <Field
            label={mode === "delta" ? "Change (e.g. 20 or -2)" : "New on-hand count"}
            name="amount"
            type="number"
            required
            min={mode === "set" ? 0 : undefined}
            state={state}
          />
          <Field label="Reason" name="reason" required minLength={3} placeholder="Restock from printer, damaged, stock count…" state={state} />
          <Field label="Low-stock alert at (optional)" name="low_stock_threshold" type="number" min={0} placeholder={String(row.low_stock_threshold)} state={state} />
          <SubmitButton>Save</SubmitButton>
        </form>
      </DialogContent>
    </Dialog>
  )
}
