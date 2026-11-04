import type { Metadata } from "next"

import { Crumbs } from "@/components/sf/bits"
import { GiftCards } from "@/components/sf/static-forms"

export const metadata: Metadata = { title: "Gift cards", description: "Digital gift cards from The Hot Smoothie Co. They pick the obsession." }

export default function GiftCardsPage() {
  return (
    <>
      <Crumbs items={[["Home", "/"], ["Gift cards"]]} />
      <GiftCards />
    </>
  )
}
