"use client"

import Form from "next/form"
import Link from "next/link"
import { useEffect, useId, useRef, useState } from "react"
import { Search } from "lucide-react"

import { Input } from "@/components/ui/input"

type Suggestion = { slug: string; title: string }

/** GET form to /search (works without JS) + debounced search-as-you-type suggestions. */
export function SearchBox() {
  const [q, setQ] = useState("")
  const [suggestions, setSuggestions] = useState<Suggestion[]>([])
  const [open, setOpen] = useState(false)
  const listId = useId()
  const abort = useRef<AbortController | null>(null)

  useEffect(() => {
    if (q.trim().length < 2) return
    const t = setTimeout(async () => {
      abort.current?.abort()
      abort.current = new AbortController()
      try {
        const res = await fetch(`/api/suggest?q=${encodeURIComponent(q.trim())}`, { signal: abort.current.signal })
        if (res.ok) setSuggestions(await res.json())
      } catch {
        /* superseded or offline: suggestions are optional */
      }
    }, 200)
    return () => clearTimeout(t)
  }, [q])

  const shown = q.trim().length >= 2 ? suggestions : []

  return (
    <div className="relative hidden md:block">
      <Form action="/search" role="search" className="relative">
        <Search className="pointer-events-none absolute top-1/2 left-0 size-4 -translate-y-1/2 text-muted-foreground" />
        <Input
          name="q"
          value={q}
          onChange={(e) => {
            setQ(e.target.value)
            setOpen(true)
          }}
          onFocus={() => setOpen(true)}
          onBlur={() => setTimeout(() => setOpen(false), 150)}
          placeholder="Search"
          aria-label="Search"
          aria-controls={listId}
          aria-expanded={open && shown.length > 0}
          autoComplete="off"
          className="h-8 w-44 rounded-none border-0 border-b border-transparent bg-transparent pl-6 shadow-none transition-[width,border-color] focus-visible:w-60 focus-visible:border-foreground focus-visible:ring-0 dark:bg-transparent"
          maxLength={100}
        />
      </Form>
      {open && shown.length > 0 && (
        <ul id={listId} className="absolute right-0 z-50 mt-2 w-72 overflow-hidden border bg-popover py-1 shadow-[0_12px_32px_-12px_rgba(0,0,0,0.25)]">
          {shown.map((s) => (
            <li key={s.slug}>
              <Link href={`/product/${s.slug}`} className="block px-4 py-2 text-sm hover:bg-muted">
                {s.title}
              </Link>
            </li>
          ))}
        </ul>
      )}
    </div>
  )
}
