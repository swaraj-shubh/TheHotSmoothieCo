"use client"

import { useEffect, useRef, useState } from "react"

const MIN = 1
const MAX = 5
const clamp = (s: number) => Math.min(MAX, Math.max(MIN, s))

type View = { s: number; x: number; y: number }
const RESET: View = { s: 1, x: 0, y: 0 }
type Shot = { url: string; alt: string }

/** Fullscreen viewer: wheel / pinch / double-click / buttons zoom toward the pointer, drag pans. */
export function Lightbox({ images, index, onIndex, open, onClose }: { images: Shot[]; index: number; onIndex: (i: number) => void; open: boolean; onClose: () => void }) {
  const dialog = useRef<HTMLDialogElement>(null)
  const stage = useRef<HTMLDivElement>(null)
  const pointers = useRef(new Map<number, { x: number; y: number }>())
  const pinch = useRef<{ dist: number } | null>(null)
  const [view, setView] = useState<View>(RESET)
  const [dragging, setDragging] = useState(false)

  // Fresh zoom for every image and every opening (state adjusted during render, not in an effect).
  const [shown, setShown] = useState(`${index}-${open}`)
  if (shown !== `${index}-${open}`) {
    setShown(`${index}-${open}`)
    setView(RESET)
  }

  useEffect(() => {
    const d = dialog.current
    if (!d) return
    if (open && !d.open) d.showModal()
    if (!open && d.open) d.close()
  }, [open])

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

  const img = images[index]
  return (
    <dialog
      ref={dialog}
      className="lb"
      aria-label="Image preview"
      onClose={onClose}
      onKeyDown={(e) => {
        if (e.key === "ArrowRight") go(1)
        else if (e.key === "ArrowLeft") go(-1)
        else if (e.key === "+" || e.key === "=") zoomAt(1.5)
        else if (e.key === "-") zoomAt(1 / 1.5)
      }}
    >
      <div className="lb__bar t-cap">
        <span>
          {index + 1} / {images.length}
        </span>
        <div className="lb__tools">
          <button type="button" aria-label="Zoom out" disabled={view.s <= MIN} onClick={() => zoomAt(1 / 1.5)}>
            −
          </button>
          <button type="button" className="lb__pct" aria-label="Reset zoom" onClick={() => setView(RESET)}>
            {Math.round(view.s * 100)}%
          </button>
          <button type="button" aria-label="Zoom in" disabled={view.s >= MAX} onClick={() => zoomAt(1.5)}>
            +
          </button>
          <button type="button" aria-label="Close" onClick={onClose}>
            ×
          </button>
        </div>
      </div>
      <div
        ref={stage}
        className={`lb__stage ${view.s > 1 ? (dragging ? "is-dragging" : "is-zoomed") : ""}`}
        onWheel={(e) => zoomAt(Math.exp(-e.deltaY * 0.0015), e.clientX, e.clientY)}
        onDoubleClick={(e) => (view.s > 1 ? setView(RESET) : zoomAt(2.5, e.clientX, e.clientY))}
        onPointerDown={(e) => {
          e.currentTarget.setPointerCapture(e.pointerId)
          pointers.current.set(e.pointerId, { x: e.clientX, y: e.clientY })
          setDragging(true)
        }}
        onPointerMove={(e) => {
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
        }}
        onPointerUp={(e) => {
          pointers.current.delete(e.pointerId)
          if (pointers.current.size < 2) pinch.current = null
          if (pointers.current.size === 0) setDragging(false)
        }}
        onPointerCancel={(e) => {
          pointers.current.delete(e.pointerId)
          if (pointers.current.size === 0) setDragging(false)
        }}
      >
        {open && img && (
          <img
            key={img.url}
            src={img.url}
            alt={img.alt}
            draggable={false}
            style={{ transform: `translate(${view.x}px, ${view.y}px) scale(${view.s})`, transition: dragging ? "none" : undefined }}
          />
        )}
        {images.length > 1 && view.s === 1 && (
          <>
            <button type="button" className="lb__nav lb__nav--prev" aria-label="Previous image" onPointerDown={(e) => e.stopPropagation()} onDoubleClick={(e) => e.stopPropagation()} onClick={() => go(-1)}>
              ‹
            </button>
            <button type="button" className="lb__nav lb__nav--next" aria-label="Next image" onPointerDown={(e) => e.stopPropagation()} onDoubleClick={(e) => e.stopPropagation()} onClick={() => go(1)}>
              ›
            </button>
          </>
        )}
      </div>
    </dialog>
  )
}
