"use client"

import { useState, useTransition } from "react"
import { toast } from "sonner"

import { deleteAddress } from "@/app/actions/account"
import { AddressForm } from "@/components/shop/address-form"
import { Badge } from "@/components/ui/badge"
import { Button } from "@/components/ui/button"
import type { AddressOut } from "@/lib/api/types"

export function AddressBook({ addresses }: { addresses: AddressOut[] }) {
  const [editing, setEditing] = useState<string | "new" | null>(addresses.length ? null : "new")
  const [pending, start] = useTransition()

  return (
    <div className="space-y-4">
      {addresses.map((a) =>
        editing === a.id ? (
          <div key={a.id} className=" border p-5">
            <AddressForm address={a} onSaved={() => setEditing(null)} />
          </div>
        ) : (
          <div key={a.id} className="flex flex-wrap items-start gap-4 border p-5 text-sm">
            <div className="flex-1">
              <p className="font-medium">
                {a.full_name} · {a.phone}
                {a.is_default_shipping && <Badge className="ml-2">Default</Badge>}
              </p>
              <p className="text-muted-foreground">
                {[a.line1, a.line2, a.landmark, `${a.city}, ${a.state} ${a.postal_code}`].filter(Boolean).join(", ")}
              </p>
            </div>
            <Button variant="outline" size="sm" onClick={() => setEditing(a.id)}>
              Edit
            </Button>
            <Button
              variant="ghost"
              size="sm"
              disabled={pending}
              onClick={() =>
                start(async () => {
                  const r = await deleteAddress(a.id)
                  if (!r.ok) toast.error(r.error)
                })
              }
            >
              Delete
            </Button>
          </div>
        ),
      )}
      {editing === "new" ? (
        <div className=" border p-5">
          <AddressForm onSaved={() => setEditing(null)} />
        </div>
      ) : (
        <Button variant="outline" onClick={() => setEditing("new")}>
          + Add address
        </Button>
      )}
    </div>
  )
}
