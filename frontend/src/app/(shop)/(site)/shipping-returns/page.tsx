import type { Metadata } from "next"
import Link from "next/link"

import { Crumbs } from "@/components/sf/bits"
import { money } from "@/lib/format"
import { SITE } from "@/lib/site"

export const metadata: Metadata = { title: "Shipping & returns", description: "Shipping, delivery and returns at The Hot Smoothie Co." }

export default function ShippingReturnsPage() {
  return (
    <>
      <Crumbs items={[["Home", "/"], ["Shipping & returns"]]} />
      <section className="wrap" style={{ paddingTop: 48, paddingBottom: 96 }}>
        <div className="page-head" style={{ paddingTop: 0 }}>
          <span className="t-label brand">THE BORING BUT IMPORTANT BIT</span>
          <h1 className="t-display">Shipping &amp; returns.</h1>
          <p className="t-sub">Short, honest and croc-approved.</p>
        </div>
        <div className="prose">
          <h2>Delivery</h2>
          <ul>
            <li>
              Most orders reach you in <b>4-5 days</b>. Remote pin codes can take longer.
            </li>
            <li>
              Free delivery on orders above {money(SITE.freeShippingAbovePaise)}. Below that, a flat {money(SITE.shippingFeePaise)}.
            </li>
            <li>Posters ship in tamper-proof packaging so they arrive the way we printed them.</li>
            <li>Gift cards are digital and arrive by email.</li>
          </ul>
          <h2>Payment</h2>
          <p>UPI, cards and netbanking. Pay however keeps you happiest.</p>
          <h2>Returns</h2>
          <ul>
            <li>
              Damaged, wrong or misprinted? Write to us within <b>7 days</b> of delivery with a photo.
            </li>
            <li>We will reprint or refund, your pick.</li>
            <li>Posters are limited editions, so we cannot take back a poster that arrived perfectly and just did not match the curtains.</li>
            <li>Gift cards are not refundable.</li>
          </ul>
          <h2>Still unsure?</h2>
          <p>
            Write to us at{" "}
            <a className="brand" style={{ textDecoration: "underline" }} href={`mailto:${SITE.supportEmail}`}>
              {SITE.supportEmail}
            </a>{" "}
            or use the{" "}
            <Link className="brand" style={{ textDecoration: "underline" }} href="/contact">
              contact page
            </Link>
            .
          </p>
        </div>
      </section>
    </>
  )
}
