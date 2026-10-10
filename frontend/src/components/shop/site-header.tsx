import Image from "next/image"
import Link from "next/link"
import { Suspense } from "react"
import { Heart, Menu, Search, ShoppingBag, User } from "lucide-react"

import { Button } from "@/components/ui/button"
import { Sheet, SheetContent, SheetHeader, SheetTitle, SheetTrigger } from "@/components/ui/sheet"
import { api } from "@/lib/api/client"
import { getCategories } from "@/lib/catalog"
import { getCurrentUser, isStaff } from "@/lib/session"

import { SearchBox } from "./search-box"

export function Logo({ className = "" }: { className?: string }) {
  return (
    <Link href="/" className={`flex items-center gap-2.5 ${className}`} aria-label="The Hot Smoothie Co. home">
      <Image src="/logo.png" alt="" width={28} height={28} className="hidden rounded-[5px] sm:block" priority />
      <span className="font-display text-[1.45rem] leading-none tracking-tight whitespace-nowrap sm:text-[1.6rem]">The Hot Smoothie Co.</span>
    </Link>
  )
}

const navLink = "text-[0.8rem] tracking-wide text-foreground/70 transition-colors hover:text-foreground"

async function CategoryNav() {
  const categories = await getCategories()
  return (
    <nav aria-label="Categories" className="hidden items-center gap-7 lg:flex">
      <Link href="/shop" className={navLink}>
        Shop all
      </Link>
      {categories.map((c) => (
        <Link key={c.id} href={`/category/${c.slug}`} className={navLink}>
          {c.name}
        </Link>
      ))}
    </nav>
  )
}

async function MobileNav() {
  const categories = await getCategories()
  return (
    <Sheet>
      <SheetTrigger asChild>
        <Button variant="ghost" size="icon" className="-ml-2 lg:hidden" aria-label="Open menu">
          <Menu />
        </Button>
      </SheetTrigger>
      <SheetContent side="left" className="w-80 bg-background">
        <SheetHeader>
          <SheetTitle className="eyebrow">Browse</SheetTitle>
        </SheetHeader>
        <nav className="flex flex-col px-4">
          <Link href="/shop" className="border-b py-3 font-display text-2xl">
            Shop all
          </Link>
          {categories.map((c) => (
            <div key={c.id} className="border-b py-3">
              <Link href={`/category/${c.slug}`} className="block font-display text-2xl">
                {c.name}
              </Link>
              {c.children?.map((child) => (
                <Link key={child.id} href={`/category/${child.slug}`} className="block py-1 text-sm text-muted-foreground">
                  {child.name}
                </Link>
              ))}
            </div>
          ))}
          <Link href="/search" className="py-3 text-sm text-muted-foreground">
            Search
          </Link>
        </nav>
      </SheetContent>
    </Sheet>
  )
}

/** Reads the session and cart: request-time, so it streams in behind Suspense. */
async function HeaderActions() {
  const user = await getCurrentUser()
  const { data: cart } = await (await api()).GET("/api/v1/cart")
  const count = cart?.item_count ?? 0
  return (
    <>
      {isStaff(user) && (
        <Link href="/admin/dashboard" className={`${navLink} mr-2 hidden sm:inline`}>
          Admin
        </Link>
      )}
      <Button asChild variant="ghost" size="icon" aria-label="Wishlist" className="hidden sm:inline-flex">
        <Link href="/wishlist">
          <Heart strokeWidth={1.5} />
        </Link>
      </Button>
      <Button asChild variant="ghost" size="icon" aria-label={user ? "Your account" : "Sign in"}>
        <Link href={user ? "/account" : "/login"}>
          <User strokeWidth={1.5} />
        </Link>
      </Button>
      <Button asChild variant="ghost" size="icon" aria-label={`Cart, ${count} items`} className="relative -mr-2">
        <Link href="/cart">
          <ShoppingBag strokeWidth={1.5} />
          {count > 0 && (
            <span className="absolute top-0.5 right-0.5 grid size-3.5 place-items-center rounded-full bg-brand text-[9px] font-medium text-white tabular-nums">
              {count > 9 ? "9+" : count}
            </span>
          )}
        </Link>
      </Button>
    </>
  )
}

export function SiteHeader() {
  return (
    <header className="sticky top-0 z-40 bg-background/85 backdrop-blur-md">
      <a href="#main" className="sr-only focus:not-sr-only focus:absolute focus:p-2">
        Skip to content
      </a>
      <p className="bg-foreground py-2 text-center text-[0.7rem] tracking-[0.14em] text-background uppercase">
        Free shipping across India on orders over ₹999
      </p>
      <div className="mx-auto grid h-16 max-w-7xl grid-cols-[1fr_auto_1fr] items-center gap-4 border-b px-4 sm:px-6 lg:px-8">
        <div className="flex items-center">
          <Suspense fallback={<div className="size-8 lg:hidden" />}>
            <MobileNav />
          </Suspense>
          <Suspense fallback={null}>
            <CategoryNav />
          </Suspense>
        </div>
        <Logo />
        <div className="flex items-center justify-end gap-0.5">
          <SearchBox />
          <Button asChild variant="ghost" size="icon" aria-label="Search" className="md:hidden">
            <Link href="/search">
              <Search strokeWidth={1.5} />
            </Link>
          </Button>
          <Suspense fallback={<div className="h-8 w-24" aria-hidden />}>
            <HeaderActions />
          </Suspense>
        </div>
      </div>
    </header>
  )
}

export function SiteFooter() {
  return (
    <footer className="mt-32 border-t">
      <div className="mx-auto grid max-w-7xl gap-12 px-4 py-16 sm:grid-cols-2 sm:px-6 lg:grid-cols-[2fr_1fr_1fr_1fr] lg:px-8">
        <div className="max-w-xs space-y-4">
          <p className="font-display text-3xl leading-none">The Hot Smoothie Co.</p>
          <p className="text-sm leading-relaxed text-muted-foreground">
            Posters, prints and stickers, designed in India and printed on 250 gsm archival paper.
          </p>
        </div>
        <FooterLinks
          title="Shop"
          links={[
            ["All prints", "/shop"],
            ["Search", "/search"],
            ["Wishlist", "/wishlist"],
          ]}
        />
        <FooterLinks
          title="Account"
          links={[
            ["Orders", "/account/orders"],
            ["Addresses", "/account/addresses"],
            ["Sign in", "/login"],
          ]}
        />
        <div className="space-y-3 text-sm text-muted-foreground">
          <p className="eyebrow text-foreground">Care</p>
          <p>Free shipping over ₹999</p>
          <p>7-day returns</p>
          <p>Secure payments by Razorpay</p>
        </div>
      </div>
      <div className="mx-auto flex max-w-7xl flex-wrap justify-between gap-2 border-t px-4 py-6 text-xs text-muted-foreground sm:px-6 lg:px-8">
        <p>© The Hot Smoothie Co.</p>
        <p>Made in India</p>
      </div>
    </footer>
  )
}

function FooterLinks({ title, links }: { title: string; links: [string, string][] }) {
  return (
    <div className="space-y-3 text-sm">
      <p className="eyebrow text-foreground">{title}</p>
      {links.map(([label, href]) => (
        <Link key={href} href={href} className="block text-muted-foreground transition-colors hover:text-foreground">
          {label}
        </Link>
      ))}
    </div>
  )
}
