import { logout } from "@/app/actions/auth"
import { AccountLinks } from "@/components/sf/account"

export default function AccountLayout({ children }: LayoutProps<"/account">) {
  return (
    <section className="wrap" style={{ paddingTop: 64, paddingBottom: 96 }}>
      <nav className="acct-nav" aria-label="Account">
        <AccountLinks />
        <form action={logout}>
          <button type="submit" className="link-quiet">
            Sign out
          </button>
        </form>
      </nav>
      {children}
    </section>
  )
}
