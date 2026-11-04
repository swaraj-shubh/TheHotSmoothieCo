"use client"

import { createContext, useContext, useEffect, useRef, useState, useTransition, type ReactNode } from "react"

import { toggleWishlist } from "@/app/actions/shop"

import { toast } from "./toast"

type Wish = { ids: Set<string>; setIds: (ids: Set<string>) => void }
const Ctx = createContext<Wish>({ ids: new Set(), setIds: () => {} })

export function WishProvider({ children }: { children: ReactNode }) {
  const [ids, setIds] = useState(new Set<string>())
  return <Ctx.Provider value={{ ids, setIds }}>{children}</Ctx.Provider>
}

/** Rendered by the layout with the signed-in customer's saved products. */
export function WishSeed({ productIds }: { productIds: string[] }) {
  const { setIds } = useContext(Ctx)
  const key = productIds.join()
  useEffect(() => setIds(new Set(key ? key.split(",") : [])), [key, setIds])
  return null
}

function useWish(productId: string) {
  const { ids, setIds } = useContext(Ctx)
  const [, start] = useTransition()
  const ref = useRef<HTMLButtonElement>(null)
  const on = ids.has(productId)
  function click() {
    const el = ref.current
    if (el) {
      el.classList.remove("pop")
      void el.offsetWidth
      el.classList.add("pop")
    }
    start(async () => {
      const r = await toggleWishlist(productId, window.location.pathname)
      if (!r.ok) return toast(r.error)
      const next = new Set(ids)
      if (r.data?.saved) next.add(productId)
      else next.delete(productId)
      setIds(next)
      toast(r.data?.saved ? "Saved. Your wall will be ready when you are." : "Removed from your wishlist.")
    })
  }
  return { on, click, ref }
}

export function WishHeart({ productId, title }: { productId: string; title: string }) {
  const { on, click, ref } = useWish(productId)
  return (
    <button ref={ref} className="card__wish" aria-pressed={on} aria-label={`Save ${title} to wishlist`} onClick={click}>
      {on ? "♥" : "♡"}
    </button>
  )
}

export function WishLink({ productId }: { productId: string }) {
  const { on, click, ref } = useWish(productId)
  return (
    <button ref={ref} className="btn-link" aria-pressed={on} style={{ borderColor: "var(--ink)", color: "var(--ink)" }} onClick={click}>
      {on ? "♥ Saved" : "♡ Save for later"}
    </button>
  )
}
