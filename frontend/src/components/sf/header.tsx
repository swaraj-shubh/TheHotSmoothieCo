"use client"

import Link from "next/link"
import { usePathname } from "next/navigation"
import { createContext, Suspense, useContext, useEffect, useRef, useState, type ReactNode } from "react"

const Path = createContext("")

export const isCurrent = (path: string, href: string, match: string[] = []) =>
  [href, ...match].some((m) => path === m || path.startsWith(`${m}/`))

export function NavLink({ href, match, className, children }: { href: string; match?: string[]; className?: string; children: ReactNode }) {
  const current = isCurrent(useContext(Path), href, match)
  return (
    <Link href={href} className={className} aria-current={current ? "page" : undefined}>
      {children}
    </Link>
  )
}

function Shell({ overlay, children }: { overlay: boolean; children: ReactNode }) {
  const [open, setOpen] = useState(false)
  return (
    <header className={`header${overlay ? " header--overlay" : ""}${open ? " open" : ""}`} id="hdr">
      <Link className="logo" href="/" aria-label="The Hot Smoothie Co. home">
        <span>The Hot Smoothie Co.</span>
      </Link>
      <button className="nav-toggle" aria-expanded={open} aria-controls="nav" onClick={() => setOpen(!open)}>
        Menu
      </button>
      <nav id="nav" aria-label="Main" onClick={() => setOpen(false)}>
        <NavLink href="/shop" match={["/collection", "/product"]}>
          Collections
        </NavLink>
        <NavLink href="/about">About</NavLink>
        <NavLink href="/wishlist">Wishlist</NavLink>
        {children}
      </nav>
    </header>
  )
}

function Routed({ children }: { children: ReactNode }) {
  const path = usePathname()
  return (
    <Path.Provider value={path}>
      <Shell overlay={path === "/"}>{children}</Shell>
    </Path.Provider>
  )
}

/** On routes with URL params the path only exists at request time, so the shell ships without the
 *  current-page underline and it streams in. Only "/" (prerendered with its path) overlays the hero. */
export function SiteHeader({ children }: { children: ReactNode }) {
  return (
    <Suspense fallback={<Shell overlay={false}>{children}</Shell>}>
      <Routed>{children}</Routed>
    </Suspense>
  )
}

/** The number in "Cart (n)". Bumps when it changes. */
export function CartCount({ count }: { count: number }) {
  const ref = useRef<HTMLSpanElement>(null)
  const last = useRef(count)
  useEffect(() => {
    const el = ref.current
    if (!el || last.current === count) return
    last.current = count
    el.classList.remove("bump")
    void el.offsetWidth
    el.classList.add("bump")
  }, [count])
  return (
    <span ref={ref} data-cart-count>
      {count}
    </span>
  )
}
