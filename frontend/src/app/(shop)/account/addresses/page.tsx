import type { Metadata } from "next"
import { Suspense } from "react"

import { AddressBook } from "@/components/account/address-book"
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
    <>
      <h1 className="mb-6 font-display text-5xl leading-none tracking-tight">Addresses</h1>
      <Suspense fallback={<div className="h-48 animate-pulse bg-muted" />}>
        <Addresses />
      </Suspense>
    </>
  )
}
