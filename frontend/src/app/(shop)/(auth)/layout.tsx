import type { Metadata } from "next"

export const metadata: Metadata = { robots: { index: false, follow: true } }

export default function AuthLayout({ children }: { children: React.ReactNode }) {
  return (
    <div className="mx-auto flex w-full max-w-sm flex-col px-4 py-20 md:py-28">{children}</div>
  )
}
