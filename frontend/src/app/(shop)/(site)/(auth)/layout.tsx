import type { Metadata } from "next"

export const metadata: Metadata = { robots: { index: false, follow: true } }

export default function AuthLayout({ children }: { children: React.ReactNode }) {
  return (
    <section className="wrap" style={{ paddingTop: 64, paddingBottom: 96, display: "grid", gap: 32 }}>
      {children}
    </section>
  )
}
