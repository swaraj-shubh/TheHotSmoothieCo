import type { CollectionOut, ProductDetail } from "./api/types"

export const FAQS = [
  { q: "How long does delivery take?", a: "Most orders reach you in 4-5 days. Remote pin codes can take a little longer, and we will tell you before your poster leaves, not after." },
  { q: "What paper do you print on?", a: "300 GSM glossy sheets, so the colours stay as loud as the idea." },
  { q: "Can I return a poster?", a: "Yes. If it arrives damaged, wrong or somehow unloved, write to us within 7 days with a photo and we will sort it. Details are on the Shipping & Returns page." },
  { q: "Do posters come framed?", a: "Not yet. They arrive flat in tamper-proof packaging, ready for the frame of your choice." },
  { q: "When is the next drop?", a: "Drop 002 lands soon. Join the Smoothie Club and you get first dibs before everyone else." },
  { q: "Will this poster fix my personality?", a: "No, but it will distract people from it." },
  { q: "Can I hang it upside down?", a: "Legally, yes. Emotionally, we’d have questions." },
  { q: "Is the croc single?", a: "He’s married to the brand. It’s complicated." },
  { q: "My mom hates it. Can I return it?", a: "Returns are easy. Your mom’s taste is not our department." },
  { q: "Do I need good taste to buy one?", a: "Absolutely not. It’s actively discouraged." },
]

export const WALLS = [
  { name: "Peach", full: "Peach blush", color: "#e8b7a0" },
  { name: "Linen", full: "Linen", color: "#f2eadb" },
  { name: "Ink", full: "Ink", color: "#1c1a19" },
  { name: "Croc green", full: "Croc green", color: "#4ca33b" },
]

export const COUPON = { code: "WELCOME10", percent: 10 }
export const CROC_PICK_SLUG = "badmash-pani-puri-wala"
export const WALL_PRODUCT_SLUG = "soul-punk"

/** A collection's description holds its tagline, a blank line, then its story. */
export function collectionCopy(c: CollectionOut) {
  const [tagline, ...story] = (c.description ?? "").split(/\n\s*\n/)
  return { tagline, story: story.join("\n\n") }
}

/** Product copy conventions (editable in the admin): description paragraphs, where one starting
 *  "Hang it if" becomes the caption; a tag like "250 editions" sets the print run. */
export function productCopy(p: ProductDetail) {
  const paragraphs = (p.description ?? "").split(/\n\s*\n/).filter(Boolean)
  const hang = paragraphs.find((x) => /^hang it if\b/i.test(x))
  const editions = p.tags.map((t) => /^(\d+) editions?$/i.exec(t.name)?.[1]).find(Boolean)
  return {
    story: paragraphs.filter((x) => x !== hang),
    hangIf: hang?.replace(/^hang it if\s*/i, ""),
    editions,
  }
}
