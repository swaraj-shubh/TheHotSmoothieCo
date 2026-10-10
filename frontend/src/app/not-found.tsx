import Link from "next/link"

import { Button } from "@/components/ui/button"

export default function NotFound() {
  return (
    <div className="mx-auto flex max-w-lg flex-1 flex-col items-center justify-center px-4 py-24 text-center">
      <p className="font-display text-6xl text-brand">404</p>
      <p className="mt-3 text-lg">This page wandered off to find a smoothie.</p>
      <Button asChild className="mt-6">
        <Link href="/shop">Back to the shop</Link>
      </Button>
    </div>
  )
}
