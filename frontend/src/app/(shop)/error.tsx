"use client"

import { useEffect } from "react"

import { Button } from "@/components/ui/button"

export default function ShopError({ error, reset }: { error: Error & { digest?: string }; reset: () => void }) {
  useEffect(() => console.error(error), [error])
  return (
    <div className="mx-auto max-w-lg px-4 py-24 text-center">
      <p className="font-display text-4xl">Oops, a spill!</p>
      <p className="mt-3 text-muted-foreground">Something went wrong loading this page. Please try again.</p>
      {error.digest && <p className="mt-2 text-xs text-muted-foreground">Reference: {error.digest}</p>}
      <Button className="mt-6" onClick={reset}>
        Try again
      </Button>
    </div>
  )
}
