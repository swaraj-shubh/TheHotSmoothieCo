import type { Metadata } from "next"
import { Suspense } from "react"

import { AddressBook } from "@/components/sf/account"
import { api, unwrap } from "@/lib/api/client"
import { requireUser } from "@/lib/session"

export const metadata: Metadata = { title: "Addresses", robots: { index: false } }

async function Addresses() {
  await requireUser("/account/addresses")
  const addresses = unwrap(await (await api()).GET("/api/v1/users/me/addresses"))
  return <AddressBook addresses={addresses} />
}

export default function AddressesPage() {
  return (
    <div style={{ display: "grid", gap: 40 }}>
      <h1 className="t-display">Addresses.</h1>
      <Suspense fallback={null}>
        <Addresses />
      </Suspense>
    </div>
  )
}
