"use client"

import Link from "next/link"
import { useRef, useState, useTransition } from "react"

import { addToCart } from "@/app/actions/cart"
import type { ProductDetail } from "@/lib/api/types"
import { productCopy, WALLS } from "@/lib/content"
import { cdn, money } from "@/lib/format"
import { SITE } from "@/lib/site"

import { ViewCart } from "./add-button"
import { Lightbox } from "./lightbox"
import { toast } from "./toast"
import { WishLink } from "./wish"

const orList = (xs: string[]) => (xs.length > 1 ? `${xs.slice(0, -1).join(", ")} or ${xs[xs.length - 1]}` : xs[0])

/** The site's product page. Options, prices and stock come from the product's variants. */
export function Pdp({ product: p }: { product: ProductDetail }) {
  const media = p.media.filter((m) => m.media_type === "IMAGE")
  const first = media[0]?.url ?? "/assets/croc-wordmark.png"
  // Poster, the same poster framed on the wall colour, then every other photo.
  const views = [
    { label: "Poster", url: first, framed: false },
    { label: "On the wall", url: first, framed: true },
    ...media.slice(1).map((m) => ({ label: "In a room", url: m.url, framed: false })),
  ]
  const shots = (media.length ? media : [{ url: first, alt_text: null }]).map((m) => ({ url: cdn(m.url, 2400), alt: m.alt_text ?? `${p.title} poster` }))

  const { story, hangIf, editions } = productCopy(p)
  const collection = p.collections[0]
  const initial = p.variants.find((v) => v.in_stock) ?? p.variants[0]
  const [selection, setSelection] = useState<Record<string, string>>(initial?.attributes ?? {})
  const variant = p.variants.find((v) => p.options.every((o) => v.attributes[o.code] === selection[o.code])) ?? null
  const [qty, setQty] = useState(1)
  const max = Math.max(1, Math.min(10, variant?.max_purchasable ?? 10))
  const [view, setView] = useState(0)
  const [shown, setShown] = useState(0)
  const [swap, setSwap] = useState(false)
  const [wall, setWall] = useState(WALLS[0].color)
  const [pending, start] = useTransition()
  const [preview, setPreview] = useState<number | null>(null)
  const timer = useRef<ReturnType<typeof setTimeout>>(undefined)

  function showView(i: number) {
    setView(i)
    setSwap(true)
    clearTimeout(timer.current)
    timer.current = setTimeout(() => {
      setShown(i)
      setSwap(false)
    }, 180)
  }

  const cm = variant?.width_mm && variant.length_mm ? `${variant.width_mm / 10} × ${variant.length_mm / 10} cm` : ""
  const label = variant ? Object.values(variant.attributes).join(", ") : ""
  const sizes = p.options.find((o) => o.code === "size")?.values ?? []
  const shipping = `Free delivery above ${money(SITE.freeShippingAbovePaise)}, otherwise ${money(SITE.shippingFeePaise)}. Most orders reach you in 4-5 days, packed tamper-proof and rolled flat-safe.`

  return (
    <>
      <div className="pdp__gallery">
        <div className="pdp__thumbs">
          {views.map((v, i) => (
            <button key={i} aria-label={v.label} aria-current={i === view} onClick={() => showView(i)}>
              <img src={cdn(v.url, 200)} alt="" />
            </button>
          ))}
        </div>
        <div className={`pdp__main${views[shown].framed ? " is-framed" : ""}`} style={{ "--wall": wall } as React.CSSProperties}>
          <img
            className={swap ? "swap" : undefined}
            src={cdn(views[shown].url, 1400)}
            alt={`${p.title} poster`}
            onClick={() => setPreview(Math.max(0, shown - 1))}
          />
        </div>
      </div>
      <div className="pdp__info">
        <div className="pdp__title-row">
          <div style={{ display: "grid", gap: 12 }}>
            {collection && (
              <Link className="chip" href={`/collection/${collection.slug}`} style={{ width: "fit-content" }}>
                {collection.name}
              </Link>
            )}
            <h1 className="t-display">{p.title}</h1>
          </div>
        </div>
        {p.short_description && <p className="t-sub">{p.short_description}</p>}
        {story.map((s) => (
          <p key={s}>{s}</p>
        ))}
        {hangIf && (
          <p className="t-cap">
            <b>Hang it if</b> {hangIf}
          </p>
        )}
        <div className="pdp__buy">
          {p.options.map((o) => (
            <div key={o.code} style={{ display: "grid", gap: 30 }}>
              <div style={{ display: "flex", justifyContent: "space-between", alignItems: "baseline", gap: 12 }}>
                <span className="t-label">{o.name}</span>
                {o.code === "size" && <span className="t-cap muted">{cm}</span>}
              </div>
              <div className="pill-group" role="radiogroup" aria-label={o.name}>
                {o.values.map((value) => (
                  <label key={value} className="pill">
                    <input type="radio" name={o.code} value={value} checked={selection[o.code] === value} onChange={() => setSelection((s) => ({ ...s, [o.code]: value }))} />
                    <span>{value}</span>
                  </label>
                ))}
              </div>
            </div>
          ))}
          <div style={{ display: "flex", alignItems: "center", gap: 24, flexWrap: "wrap" }}>
            <span className="t-price">{variant ? money(variant.price_paise * qty) : "Not available"}</span>
            <div className="stepper" role="group" aria-label="Quantity">
              <button type="button" aria-label="Fewer" onClick={() => setQty((q) => Math.max(1, q - 1))}>
                −
              </button>
              <output aria-live="polite">{Math.min(qty, max)}</output>
              <button type="button" aria-label="More" onClick={() => setQty((q) => Math.min(max, q + 1))}>
                +
              </button>
            </div>
          </div>
          <div style={{ display: "flex", gap: 20, alignItems: "center", flexWrap: "wrap" }}>
            <button
              className="tag-btn"
              disabled={!variant?.in_stock || pending}
              onClick={() =>
                variant &&
                start(async () => {
                  const n = Math.min(qty, max)
                  const r = await addToCart(variant.id, n)
                  toast(r.ok ? <ViewCart text={`${n} × ${p.title} (${label}) added.`} /> : r.error)
                })
              }
            >
              <span>{variant && !variant.in_stock ? "Sold out" : "Add to cart"}</span>
            </button>
            <WishLink productId={p.id} />
          </div>
          {editions && <p className="t-cap muted">Only {editions} made. When they&apos;re gone, they&apos;re gone.</p>}
        </div>
        <ul className="perks">
          <li>300 GSM glossy sheets</li>
          <li>4-5 days delivery</li>
          <li>Tamper-proof packaging</li>
          <li>Easy returns</li>
        </ul>
        <div>
          <p className="t-label" style={{ marginBottom: 12 }}>
            See it on your wall
          </p>
          <div className="pill-group">
            {WALLS.map((w) => (
              <label key={w.color} className="pill">
                <input
                  type="radio"
                  name="wall"
                  value={w.color}
                  checked={wall === w.color}
                  onChange={() => {
                    setWall(w.color)
                    showView(1)
                  }}
                />
                <span>
                  <i className="swatch" style={{ background: w.color }} />
                  {w.name}
                </span>
              </label>
            ))}
          </div>
        </div>
        <div>
          <details className="acc" open>
            <summary>The details</summary>
            <div className="acc__body">
              <ul style={{ margin: 0, paddingLeft: 20 }}>
                <li>300 GSM glossy paper</li>
                {sizes.length > 0 && <li>Sizes: {orList(sizes)}. Frame not included</li>}
                {editions && <li>Limited to {editions} prints per design</li>}
              </ul>
            </div>
          </details>
          <details className="acc">
            <summary>Shipping</summary>
            <p className="acc__body">{shipping}</p>
          </details>
          <details className="acc">
            <summary>Returns</summary>
            <p className="acc__body">
              Arrived damaged or wrong? Write to us within 7 days with a photo.{" "}
              <Link className="brand" href="/shipping-returns" style={{ textDecoration: "underline" }}>
                Read the full policy.
              </Link>
            </p>
          </details>
        </div>
      </div>
      <Lightbox images={shots} index={preview ?? 0} onIndex={setPreview} open={preview !== null} onClose={() => setPreview(null)} />
    </>
  )
}
