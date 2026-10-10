"use client"

import { useActionState, useState } from "react"
import { Star } from "lucide-react"

import { submitReview } from "@/app/actions/shop"
import { Button } from "@/components/ui/button"
import { Input } from "@/components/ui/input"
import { Label } from "@/components/ui/label"
import { Textarea } from "@/components/ui/textarea"

export function ReviewForm({ productId, slug }: { productId: string; slug: string }) {
  const [state, formAction, pending] = useActionState(submitReview, null)
  const [rating, setRating] = useState(5)

  if (state?.ok) return <p className=" bg-secondary p-4 text-sm text-secondary-foreground">{state.message}</p>

  return (
    <form action={formAction} className="space-y-4 border p-5">
      <h3 className="font-semibold">Write a review</h3>
      <input type="hidden" name="product_id" value={productId} />
      <input type="hidden" name="slug" value={slug} />
      <input type="hidden" name="rating" value={rating} />
      <fieldset>
        <legend className="mb-1 text-sm">Your rating</legend>
        <div className="flex gap-1">
          {[1, 2, 3, 4, 5].map((n) => (
            <button
              key={n}
              type="button"
              onClick={() => setRating(n)}
              aria-label={`${n} star${n > 1 ? "s" : ""}`}
              aria-pressed={rating === n}
            >
              <Star className={`size-6 ${n <= rating ? "fill-foreground text-foreground" : "text-muted-foreground"}`} />
            </button>
          ))}
        </div>
      </fieldset>
      <div className="space-y-1.5">
        <Label htmlFor="title">Title (optional)</Label>
        <Input id="title" name="title" maxLength={120} />
      </div>
      <div className="space-y-1.5">
        <Label htmlFor="body">Your review (optional)</Label>
        <Textarea id="body" name="body" maxLength={5000} rows={4} />
      </div>
      {state && !state.ok && <p className="text-sm text-destructive">{state.error}</p>}
      <Button type="submit" disabled={pending}>
        {pending ? "Submitting…" : "Submit review"}
      </Button>
    </form>
  )
}
