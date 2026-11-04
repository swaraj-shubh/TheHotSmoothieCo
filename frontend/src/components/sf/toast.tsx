"use client"

import { useEffect, useState, type ReactNode } from "react"

type Item = { id: number; node: ReactNode; out?: boolean }
let push: ((node: ReactNode) => void) | null = null

/** Same behaviour as the site's toast(): 3.8 s, then a short exit animation. */
export function toast(node: ReactNode) {
  push?.(node)
}

export function Toaster() {
  const [items, setItems] = useState<Item[]>([])
  useEffect(() => {
    let next = 0
    push = (node) => {
      const id = next++
      setItems((list) => [...list, { id, node }])
      setTimeout(() => {
        setItems((list) => list.map((t) => (t.id === id ? { ...t, out: true } : t)))
        setTimeout(() => setItems((list) => list.filter((t) => t.id !== id)), 260)
      }, 3800)
    }
    return () => {
      push = null
    }
  }, [])
  if (!items.length) return null
  return (
    <div className="toast-region" role="status" aria-live="polite">
      {items.map((t) => (
        <div key={t.id} className={t.out ? "toast out" : "toast"}>
          {t.node}
        </div>
      ))}
    </div>
  )
}
