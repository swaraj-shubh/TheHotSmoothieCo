import Image from "next/image"

import { cn } from "@/lib/utils"

// [paper, ink, accent, soft] — muted, print-shop tones.
const PALETTES = [
  ["#f3eee4", "#1d1d1b", "#c4552f", "#d9cbb4"],
  ["#e9ece4", "#24302a", "#7d8f6a", "#c9d1bd"],
  ["#f1ece6", "#1f2a44", "#002bcf", "#c9cfe0"],
  ["#efe6d8", "#3b2a1e", "#d49a3a", "#e2cfb3"],
  ["#ece9e4", "#1b1b1b", "#8c8c86", "#d6d3cc"],
]

function hash(s: string): number {
  let h = 2166136261
  for (let i = 0; i < s.length; i++) h = Math.imul(h ^ s.charCodeAt(i), 16777619)
  return h >>> 0
}

/** Deterministic minimal artwork for products without photos (seeded by the slug). */
function ArtPlaceholder({ seed, title }: { seed: string; title: string }) {
  const h = hash(seed)
  const [paper, ink, accent, soft] = PALETTES[h % PALETTES.length]
  const r = (n: number, mod = 100) => (h >>> n) % mod
  const kind = r(4, 3)
  return (
    <svg viewBox="0 0 300 400" role="img" aria-label={title} className="h-full w-full">
      <rect width="300" height="400" fill={paper} />
      {kind === 0 && (
        // Sun over a horizon.
        <>
          <circle cx={110 + r(7, 80)} cy={150 + r(11, 40)} r={46 + r(13, 20)} fill={accent} />
          <rect y={250 + r(17, 20)} width="300" height="200" fill={soft} />
          <rect y={250 + r(17, 20)} width="300" height="2" fill={ink} opacity="0.85" />
        </>
      )}
      {kind === 1 && (
        // Arch.
        <>
          <path d="M70 330 V190 A80 80 0 0 1 230 190 V330 Z" fill={soft} />
          <path d={`M110 330 V${210 + r(9, 20)} A40 40 0 0 1 190 ${210 + r(9, 20)} V330 Z`} fill={accent} />
          <rect x="50" y="330" width="200" height="2" fill={ink} />
        </>
      )}
      {kind === 2 && (
        // Line study.
        <g stroke={ink} strokeWidth="1.5" fill="none">
          {Array.from({ length: 9 }, (_, i) => (
            <path key={i} d={`M50 ${130 + i * 18} Q 150 ${80 + i * 18 + r(i + 3, 40)} 250 ${130 + i * 18}`} />
          ))}
          <circle cx={150 + r(19, 60) - 30} cy="96" r="14" fill={accent} stroke="none" />
        </g>
      )}
    </svg>
  )
}

/**
 * A print on a wall: the artwork sits in a mat with a soft shadow on a neutral backdrop.
 * ponytail: real photos are assumed to be flat artwork (print files); lifestyle shots would want
 * `bare` (full-bleed) instead.
 */
export function ProductImage({
  src,
  alt,
  seed,
  priority,
  bare,
  sizes = "(min-width: 1024px) 25vw, (min-width: 640px) 33vw, 50vw",
  className,
}: {
  src?: string | null
  alt: string
  seed: string
  priority?: boolean
  bare?: boolean
  sizes?: string
  className?: string
}) {
  const art = src ? (
    <Image src={src} alt={alt} fill sizes={sizes} priority={priority} className="object-cover" />
  ) : (
    <ArtPlaceholder seed={seed} title={alt} />
  )
  if (bare) return <div className={cn("relative aspect-[3/4] overflow-hidden bg-muted", className)}>{art}</div>
  return (
    <div className={cn("relative grid aspect-[4/5] place-items-center overflow-hidden bg-muted", className)}>
      <div className="relative aspect-[3/4] w-[64%] bg-white p-[5%] shadow-[0_1px_1px_rgba(0,0,0,0.04),0_12px_28px_-10px_rgba(30,25,15,0.28)] transition-transform duration-500 ease-out group-hover:scale-[1.025]">
        <div className="relative h-full w-full overflow-hidden">{art}</div>
      </div>
    </div>
  )
}
