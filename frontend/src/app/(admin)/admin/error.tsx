"use client"

import { Button } from "@/components/ui/button"

export default function AdminError({ error, reset }: { error: Error & { digest?: string }; reset: () => void }) {
  return (
    <div className="rounded-xl border bg-background p-10 text-center">
      <p className="text-lg font-semibold">This page couldn’t load</p>
      <p className="mt-1 text-sm text-muted-foreground">
        {error.message && !error.message.includes("digest") ? error.message : "Something went wrong talking to the API."}
      </p>
      {error.digest && <p className="mt-1 text-xs text-muted-foreground">Reference {error.digest}</p>}
      <Button className="mt-4" onClick={reset}>
        Retry
      </Button>
    </div>
  )
}
