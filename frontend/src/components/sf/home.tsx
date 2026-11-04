"use client"

import Link from "next/link"
import { useEffect, useRef, useState } from "react"

import { COUPON, WALLS } from "@/lib/content"
import { SITE } from "@/lib/site"

import { toast } from "./toast"

export function DropTimer() {
  const [v, setV] = useState([0, 0, 0, 0])
  useEffect(() => {
    const tick = () => {
      const s = Math.max(0, Math.floor((new Date(SITE.dropDate).getTime() - Date.now()) / 1000))
      setV([Math.floor(s / 86400), Math.floor((s % 86400) / 3600), Math.floor((s % 3600) / 60), s % 60])
    }
    tick()
    const id = setInterval(tick, 1000)
    return () => clearInterval(id)
  }, [])
  return (
    <div className="timer" data-timer aria-hidden="true">
      {["DAYS", "HRS", "MIN", "SEC"].map((l, i) => (
        <div key={l}>
          <b>{String(v[i]).padStart(2, "0")}</b>
          <small>{l}</small>
        </div>
      ))}
    </div>
  )
}

export function WallSection({ posterUrl, productHref, title }: { posterUrl: string; productHref: string; title: string }) {
  const [wall, setWall] = useState(WALLS[0])
  const [photo, setPhoto] = useState<string | null>(null)
  const file = useRef<HTMLInputElement>(null)
  return (
    <div className="wall-section">
      <div className="wall-copy">
        <span className="t-label brand">TRY BEFORE YOU HANG</span>
        <h2 className="t-display" id="wall-h">
          See it on your wall.
        </h2>
        <p className="t-sub">Pick a wall color and see how a poster sits in the room before it ships.</p>
        <div className="pill-group" role="radiogroup" aria-label="Wall color">
          {WALLS.map((w) => (
            <label key={w.color} className="pill">
              <input
                type="radio"
                name="wall"
                value={w.color}
                checked={wall.color === w.color}
                onChange={() => {
                  setPhoto(null)
                  setWall(w)
                }}
              />
              <span>
                <i className="swatch" style={{ background: w.color }} />
                {w.name}
              </span>
            </label>
          ))}
        </div>
        <div className="divider t-label" style={{ opacity: 0.6 }}>
          OR
        </div>
        <div className="upload">
          <img src="/assets/icon-upload.svg" alt="" width="48" height="48" />
          <div>
            <b>Upload a photo of your wall</b>
            <span className="t-cap muted">Drag it here. JPG or PNG. We&apos;ll hang the poster for you.</span>
          </div>
          <button className="btn btn--outline" type="button" onClick={() => file.current?.click()}>
            [ Browse ]
          </button>
          <input
            ref={file}
            type="file"
            accept="image/jpeg,image/png"
            hidden
            onChange={(e) => {
              const f = e.target.files?.[0]
              if (!f || !/^image\/(jpeg|png)$/.test(f.type)) return toast("JPG or PNG only, please.")
              setPhoto(URL.createObjectURL(f))
            }}
          />
        </div>
        <Link className="btn" href={productHref}>
          [ Try it with your poster ]
        </Link>
      </div>
      <div
        className={`wall-mock${photo ? " has-photo" : ""}`}
        role="img"
        aria-label={`${title} poster framed on a wall`}
        style={{ "--wall": wall.color, ...(photo ? { backgroundImage: `url(${photo})` } : {}) } as React.CSSProperties}
      >
        <div className="wall-mock__floor" />
        <div className="wall-mock__frame">
          <img src={posterUrl} alt="" />
        </div>
        <span className="chip chip--outline">{photo ? "YOUR WALL" : `WALL: ${wall.full.toUpperCase()}`}</span>
      </div>
    </div>
  )
}

const TRACKS = [
  "Hang Tight (Croc Remix) — The Smoothies",
  "Side Eye, Slow Burn",
  "Pani Puri at 2 AM",
  "Lights Out, Opinions On",
  "Frame It Crooked",
  "Fanboy Without a Cause",
  "Croc Outro (He Knows)",
]
const LENGTH = 227
const fmt = (n: number) => `${Math.floor(n / 60)}:${String(n % 60).padStart(2, "0")}`

export function VinylPlayer() {
  const [{ i, sec }, setPos] = useState({ i: 0, sec: 0 })
  const [playing, setPlaying] = useState(true)
  useEffect(() => {
    if (!playing) return
    const id = setInterval(
      () => setPos((p) => (p.sec + 1 >= LENGTH ? { i: (p.i + 1) % TRACKS.length, sec: 0 } : { i: p.i, sec: p.sec + 1 })),
      1000,
    )
    return () => clearInterval(id)
  }, [playing])
  return (
    <div className={`player${playing ? "" : " paused"}`}>
      <span className="t-label">PRESS PLAY. FEEL THE VIBE.</span>
      <span className="player__status t-label">
        <i className="rec-dot" />
        <span>{playing ? "PLAYING" : "PAUSED"}</span>
      </span>
      <div className="record" aria-hidden="true">
        <div className="record__label">
          <img src="/assets/croc-wordmark.png" alt="" />
        </div>
      </div>
      <img className="tonearm" src="/assets/tonearm.svg" alt="" aria-hidden="true" />
      <div className="player__now">
        <span className="t-label muted">NOW SPINNING</span>
        <b>{TRACKS[i]}</b>
      </div>
      <div className="progress">
        <i style={{ width: `${(sec / LENGTH) * 100}%` }} />
      </div>
      <div className="player__times t-cap">
        <span>{fmt(sec)}</span>
        <span>
          {i + 1} / {TRACKS.length}
        </span>
        <span>3:47</span>
      </div>
      <div className="controls">
        <button className="ctrl" aria-label="Previous" onClick={() => setPos((p) => ({ i: (p.i + TRACKS.length - 1) % TRACKS.length, sec: 0 }))}>
          ◀◀
        </button>
        <button className="ctrl ctrl--main" aria-label={playing ? "Pause" : "Play"} onClick={() => setPlaying(!playing)}>
          {playing ? "❚❚" : "▶"}
        </button>
        <button className="ctrl" aria-label="Next" onClick={() => setPos((p) => ({ i: (p.i + 1) % TRACKS.length, sec: 0 }))}>
          ▶▶
        </button>
      </div>
    </div>
  )
}

/** ponytail: like the site, the address stays in this browser. Needs a newsletter endpoint on the
 *  API before it collects anything. */
export function ClubForm() {
  const [done, setDone] = useState(false)
  if (done) {
    return (
      <p className="t-sub">
        You&apos;re in. Code <b>{COUPON.code}</b> takes {COUPON.percent}% off your first order.
      </p>
    )
  }
  return (
    <form
      className="pass__form"
      noValidate
      onSubmit={(e) => {
        e.preventDefault()
        const em = e.currentTarget.elements.namedItem("email") as HTMLInputElement
        if (!em.checkValidity()) return em.reportValidity()
        try {
          localStorage.setItem("hsc_club", JSON.stringify(em.value))
        } catch {
          /* private mode */
        }
        setDone(true)
      }}
    >
      <label className="sr-only" htmlFor="club-email">
        Email address
      </label>
      <input className="input input--pill" id="club-email" name="email" type="email" placeholder="Email address" required autoComplete="email" />
      <button className="ticket-btn" type="submit" style={{ "--notch": "var(--page)" } as React.CSSProperties}>
        Join the club
      </button>
    </form>
  )
}
