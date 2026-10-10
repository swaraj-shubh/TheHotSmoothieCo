"use client"

import { useRef, useState } from "react"
import { ChevronLeft, ChevronRight, Minus, Plus, X } from "lucide-react"
import { Dialog as DialogPrimitive } from "radix-ui"

import type { ProductDetail } from "@/lib/api/types"
import { cn } from "@/lib/utils"

import { ProductImage } from "./product-image"

type Image = ProductDetail["media"][number]

export function Gallery({ product }: { product: ProductDetail }) {
  const images = product.media.filter((m) => m.media_type === "IMAGE")
  const [active, setActive] = useState(0)
  const [open, setOpen] = useState(false)
  const current = images[active]

  return (
    <div className="space-y-3">
      {current ? (
        <button type="button" onClick={() => setOpen(true)} className="block w-full cursor-zoom-in" aria-label="View full screen">
          <ProductImage src={current.url} alt={current.alt_text ?? product.title} seed={product.slug} priority sizes="(min-width: 1024px) 50vw, 100vw" />
        </button>
      ) : (
        <ProductImage alt={product.title} seed={product.slug} priority sizes="(min-width: 1024px) 50vw, 100vw" />
      )}
      {images.length > 1 && (
        <ul className="flex gap-2 overflow-x-auto" aria-label="Product images">
          {images.map((img, i) => (
            <li key={img.id}>
              <button
                type="button"
                onClick={() => setActive(i)}
                aria-label={`Show image ${i + 1}`}
                aria-current={i === active}
                className={cn("block w-16 opacity-60 transition-opacity hover:opacity-100", i === active && "opacity-100 ring-1 ring-foreground")}
              >
                <ProductImage src={img.thumbnail_url} alt="" seed={`${product.slug}-${i}`} sizes="80px" bare />
              </button>
            </li>
          ))}
        </ul>
      )}
      {images.length > 0 && (
        <Lightbox images={images} index={active} onIndex={setActive} open={open} onOpenChange={setOpen} title={product.title} />
      )}
    </div>
  )
}

const MIN = 1
const MAX = 5
const clamp = (s: number) => Math.min(MAX, Math.max(MIN, s))

type View = { s: number; x: number; y: number }
const RESET: View = { s: 1, x: 0, y: 0 }

/** Fullscreen viewer: wheel / pinch / double-click / buttons zoom toward the pointer, drag pans. */
function Lightbox({
  images,
  index,
  onIndex,
  open,
  onOpenChange,
  title,
}: {
  images: Image[]
  index: number
  onIndex: (i: number) => void
  open: boolean
  onOpenChange: (o: boolean) => void
  title: string
}) {
  const [view, setView] = useState<View>(RESET)
  const [dragging, setDragging] = useState(false)
  const stage = useRef<HTMLDivElement>(null)
  const pointers = useRef(new Map<number, { x: number; y: number }>())
  const pinch = useRef<{ dist: number } | null>(null)
  const img = images[index]

  // Fresh zoom for every image and every opening (state adjusted during render, not in an effect).
  const [shown, setShown] = useState(`${index}-${open}`)
  if (shown !== `${index}-${open}`) {
    setShown(`${index}-${open}`)
    setView(RESET)
  }

  /** Zoom by `factor`, keeping the screen point (cx, cy) fixed under the pointer. */
  const zoomAt = (factor: number, cx?: number, cy?: number) =>
    setView((v) => {
      const s = clamp(v.s * factor)
      if (s === 1) return RESET
      const r = stage.current?.getBoundingClientRect()
      const px = r && cx !== undefined ? cx - r.left - r.width / 2 : 0
      const py = r && cy !== undefined ? cy - r.top - r.height / 2 : 0
      return { s, x: px - (px - v.x) * (s / v.s), y: py - (py - v.y) * (s / v.s) }
    })

  const go = (d: number) => onIndex((index + d + images.length) % images.length)

  const onPointerDown = (e: React.PointerEvent) => {
    e.currentTarget.setPointerCapture(e.pointerId)
    pointers.current.set(e.pointerId, { x: e.clientX, y: e.clientY })
    setDragging(true)
  }
  const onPointerMove = (e: React.PointerEvent) => {
    const prev = pointers.current.get(e.pointerId)
    if (!prev) return
    pointers.current.set(e.pointerId, { x: e.clientX, y: e.clientY })
    const pts = [...pointers.current.values()]
    if (pts.length === 2) {
      const dist = Math.hypot(pts[0].x - pts[1].x, pts[0].y - pts[1].y)
      if (pinch.current) zoomAt(dist / pinch.current.dist, (pts[0].x + pts[1].x) / 2, (pts[0].y + pts[1].y) / 2)
      pinch.current = { dist }
    } else if (view.s > 1) {
      setView((v) => ({ ...v, x: v.x + e.clientX - prev.x, y: v.y + e.clientY - prev.y }))
    }
  }
  const onPointerUp = (e: React.PointerEvent) => {
    pointers.current.delete(e.pointerId)
    if (pointers.current.size < 2) pinch.current = null
    if (pointers.current.size === 0) setDragging(false)
  }

  return (
    <DialogPrimitive.Root open={open} onOpenChange={onOpenChange}>
      <DialogPrimitive.Portal>
        <DialogPrimitive.Overlay className="fixed inset-0 z-50 bg-black/95 data-open:animate-in data-open:fade-in-0 data-closed:animate-out data-closed:fade-out-0" />
        <DialogPrimitive.Content
          className="fixed inset-0 z-50 flex flex-col text-white outline-none data-open:animate-in data-open:fade-in-0 data-closed:animate-out data-closed:fade-out-0"
          onKeyDown={(e) => {
            if (e.key === "ArrowRight") go(1)
            else if (e.key === "ArrowLeft") go(-1)
            else if (e.key === "+" || e.key === "=") zoomAt(1.5)
            else if (e.key === "-") zoomAt(1 / 1.5)
          }}
        >
          <DialogPrimitive.Title className="sr-only">{title}</DialogPrimitive.Title>
          <DialogPrimitive.Description className="sr-only">
            Image {index + 1} of {images.length}. Scroll, pinch or double-click to zoom; drag to move.
          </DialogPrimitive.Description>

          <div className="flex items-center justify-between gap-4 p-3 text-sm">
            <span className="px-2 text-white/60 tabular-nums">
              {index + 1} / {images.length}
            </span>
            <div className="flex items-center gap-1">
              <IconButton label="Zoom out" onClick={() => zoomAt(1 / 1.5)} disabled={view.s <= MIN}>
                <Minus />
              </IconButton>
              <button
                type="button"
                onClick={() => setView(RESET)}
                className="w-14 rounded-full py-2 text-xs text-white/70 tabular-nums hover:text-white"
                aria-label="Reset zoom"
              >
                {Math.round(view.s * 100)}%
              </button>
              <IconButton label="Zoom in" onClick={() => zoomAt(1.5)} disabled={view.s >= MAX}>
                <Plus />
              </IconButton>
              <DialogPrimitive.Close asChild>
                <IconButton label="Close" className="ml-2">
                  <X />
                </IconButton>
              </DialogPrimitive.Close>
            </div>
          </div>

          <div
            ref={stage}
            className={cn(
              "relative flex-1 touch-none overflow-hidden select-none",
              view.s > 1 ? (dragging ? "cursor-grabbing" : "cursor-grab") : "cursor-zoom-in",
            )}
            onWheel={(e) => zoomAt(Math.exp(-e.deltaY * 0.0015), e.clientX, e.clientY)}
            onDoubleClick={(e) => (view.s > 1 ? setView(RESET) : zoomAt(2.5, e.clientX, e.clientY))}
            onPointerDown={onPointerDown}
            onPointerMove={onPointerMove}
            onPointerUp={onPointerUp}
            onPointerCancel={onPointerUp}
          >
            {/* Original file (not a resized next/image variant) so zooming in stays sharp. */}
            {/* eslint-disable-next-line @next/next/no-img-element */}
            <img
              key={img.id}
              src={img.url}
              alt={img.alt_text ?? title}
              draggable={false}
              className={cn(
                "absolute inset-0 m-auto max-h-full max-w-full object-contain will-change-transform",
                // Smooth for wheel/button/double-click zoom; instant while dragging or pinching.
                !dragging && "transition-transform duration-200 ease-out",
              )}
              style={{ transform: `translate(${view.x}px, ${view.y}px) scale(${view.s})` }}
            />
            {images.length > 1 && view.s === 1 && (
              <>
                <IconButton label="Previous image" onClick={() => go(-1)} className="absolute top-1/2 left-3 -translate-y-1/2 bg-black/40">
                  <ChevronLeft />
                </IconButton>
                <IconButton label="Next image" onClick={() => go(1)} className="absolute top-1/2 right-3 -translate-y-1/2 bg-black/40">
                  <ChevronRight />
                </IconButton>
              </>
            )}
          </div>
        </DialogPrimitive.Content>
      </DialogPrimitive.Portal>
    </DialogPrimitive.Root>
  )
}

function IconButton({ label, className, ...props }: React.ComponentProps<"button"> & { label: string }) {
  return (
    <button
      type="button"
      aria-label={label}
      title={label}
      // Keep clicks on controls from starting a drag/double-click zoom on the stage underneath.
      onPointerDown={(e) => e.stopPropagation()}
      onDoubleClick={(e) => e.stopPropagation()}
      className={cn(
        "grid size-10 place-items-center rounded-full text-white/80 transition hover:bg-white/10 hover:text-white disabled:opacity-30 [&_svg]:size-5 [&_svg]:stroke-[1.5]",
        className,
      )}
      {...props}
    />
  )
}
