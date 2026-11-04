"use client"

import Link from "next/link"
import { useState, useTransition, type CSSProperties } from "react"

import { quickAdd } from "@/app/actions/cart"

import { toast } from "./toast"

export const ViewCart = ({ text }: { text: string }) => (
  <>
    <span>{text}</span>
    <Link href="/cart">View cart</Link>
  </>
)

/** The price-tag "Add to cart" on cards and Croc's pick. */
export function QuickAdd({ slug, title, inStock, style }: { slug: string; title: string; inStock: boolean; style?: CSSProperties }) {
  const [added, setAdded] = useState(false)
  const [pending, start] = useTransition()
  return (
    <button
      className={`tag-btn${added ? " is-added" : ""}`}
      style={style}
      disabled={!inStock || pending}
      onClick={() =>
        start(async () => {
          const r = await quickAdd(slug)
          if (!r.ok) return toast(r.error)
          setAdded(true)
          setTimeout(() => setAdded(false), 1400)
          toast(<ViewCart text={`${title} is in your cart.`} />)
        })
      }
    >
      <span>{!inStock ? "Sold out" : added ? "Added ✓" : "Add to cart"}</span>
    </button>
  )
}
