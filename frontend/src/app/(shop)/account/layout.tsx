import Link from "next/link"

import { logout } from "@/app/actions/auth"
import { Button } from "@/components/ui/button"

const LINKS = [
  ["/account", "Profile"],
  ["/account/orders", "Orders"],
  ["/account/addresses", "Addresses"],
  ["/wishlist", "Wishlist"],
] as const

export default function AccountLayout({ children }: LayoutProps<"/account">) {
  return (
    <div className="mx-auto grid max-w-6xl gap-12 px-4 py-12 sm:px-6 md:grid-cols-[180px_1fr] lg:px-8">
      <nav aria-label="Account" className="flex gap-6 overflow-x-auto border-b pb-3 md:flex-col md:gap-3 md:border-0 md:pb-0">
        {LINKS.map(([href, label]) => (
          <Link key={href} href={href} className="text-sm whitespace-nowrap text-muted-foreground transition-colors hover:text-foreground">
            {label}
          </Link>
        ))}
        <form action={logout}>
          <Button type="submit" variant="link" className="h-auto p-0 text-sm font-normal whitespace-nowrap text-muted-foreground hover:text-foreground hover:no-underline">
            Sign out
          </Button>
        </form>
      </nav>
      <div className="min-w-0">{children}</div>
    </div>
  )
}
