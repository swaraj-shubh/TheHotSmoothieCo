import Link from "next/link"
import { Suspense } from "react"

import { CartCount, NavLink, SiteHeader } from "@/components/sf/header"
import { WishProvider, WishSeed } from "@/components/sf/wish"
import { api } from "@/lib/api/client"
import { money } from "@/lib/format"
import { getCurrentUser, isStaff } from "@/lib/session"
import { SITE } from "@/lib/site"

/** Reads the session and cart: request-time, so it streams in behind Suspense. */
async function HeaderActions() {
  const user = await getCurrentUser()
  const { data: cart } = await (await api()).GET("/api/v1/cart")
  return (
    <>
      {isStaff(user) && <NavLink href="/admin">Admin</NavLink>}
      <NavLink href={user ? "/account" : "/login"}>{user ? "Account" : "Sign in"}</NavLink>
      <NavLink className="cart-link" href="/cart">
        Cart (<CartCount count={cart?.item_count ?? 0} />)
      </NavLink>
    </>
  )
}

async function SavedProducts() {
  if (!(await getCurrentUser())) return <WishSeed productIds={[]} />
  const { data } = await (await api()).GET("/api/v1/wishlist", { params: { query: { limit: 100 } } })
  return <WishSeed productIds={data?.items.map((i) => i.product.id) ?? []} />
}

function SiteFooter() {
  return (
    <footer className="footer">
      <div className="footer__cols">
        <div className="footer__col">
          <span className="t-label">Shop</span>
          <Link href="/shop">Collections</Link>
          <Link href="/shop?new=1">New drops</Link>
          <Link href="/gift-cards">Gift cards</Link>
          <Link href="/about">About</Link>
        </div>
        <div className="footer__col">
          <span className="t-label">Help</span>
          <Link href="/shipping-returns">Shipping &amp; returns</Link>
          <Link href="/faq">FAQ</Link>
          <Link href="/contact">Contact</Link>
        </div>
        <div className="footer__col">
          <span className="t-label">Follow</span>
          <a href="#" rel="noopener">
            Instagram
          </a>
          <a href="#" rel="noopener">
            YouTube
          </a>
        </div>
      </div>
      <p className="footer__mark">The Hot Smoothie Co.</p>
      <div className="footer__fine t-cap">
        <span>© 2026 The Hot Smoothie Co.</span>
        <span>300 GSM glossy. Zero good taste required.</span>
      </div>
    </footer>
  )
}

/** The site's chrome: top bar, header, footer. */
export default function SiteLayout({ children }: { children: React.ReactNode }) {
  return (
    <WishProvider>
      <div className="topbar">
        <span>300 GSM Glossy Print</span>
        <span>Free Delivery on orders above {money(SITE.freeShippingAbovePaise)}</span>
      </div>
      <SiteHeader>
        <Suspense
          fallback={
            <>
              <NavLink href="/login">Sign in</NavLink>
              <NavLink className="cart-link" href="/cart">
                Cart (<span data-cart-count>0</span>)
              </NavLink>
            </>
          }
        >
          <HeaderActions />
        </Suspense>
      </SiteHeader>
      <main id="main-content">{children}</main>
      <SiteFooter />
      <Suspense fallback={null}>
        <SavedProducts />
      </Suspense>
    </WishProvider>
  )
}
