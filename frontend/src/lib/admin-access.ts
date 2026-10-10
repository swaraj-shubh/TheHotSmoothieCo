import type { Role } from "./api/types"

/** Which roles see which admin section. Mirrors the API's own checks (the API is authoritative;
 *  this only decides what to show). SUPER_ADMIN implicitly has everything. */
export const ACCESS = {
  dashboard: [] as Role[], // any staff
  catalog: ["ADMIN", "PRODUCT_MANAGER"] as Role[],
  inventory: ["ADMIN", "INVENTORY_MANAGER"] as Role[],
  orders: ["ADMIN", "ORDER_MANAGER", "CUSTOMER_SUPPORT"] as Role[],
  ordersWrite: ["ADMIN", "ORDER_MANAGER"] as Role[],
  customers: ["ADMIN", "CUSTOMER_SUPPORT"] as Role[],
  customersWrite: ["ADMIN"] as Role[],
  marketing: ["ADMIN", "MARKETING_MANAGER"] as Role[],
  reviews: ["ADMIN", "PRODUCT_MANAGER", "CUSTOMER_SUPPORT"] as Role[],
  notifications: ["ADMIN", "CUSTOMER_SUPPORT"] as Role[],
  analytics: ["ADMIN", "MARKETING_MANAGER"] as Role[],
  audit: ["ADMIN"] as Role[],
  roles: [] as Role[], // SUPER_ADMIN only (see canManageRoles)
} as const

export type Section = keyof typeof ACCESS

export function can(roles: string[], section: Section): boolean {
  if (roles.includes("SUPER_ADMIN")) return true
  if (section === "roles") return false
  const needed = ACCESS[section]
  return needed.length === 0 ? roles.length > 0 : needed.some((r) => roles.includes(r))
}

export const NAV: { href: string; label: string; section: Section }[] = [
  { href: "/admin/dashboard", label: "Dashboard", section: "dashboard" },
  { href: "/admin/orders", label: "Orders", section: "orders" },
  { href: "/admin/products", label: "Products", section: "catalog" },
  { href: "/admin/categories", label: "Categories", section: "catalog" },
  { href: "/admin/collections", label: "Collections", section: "catalog" },
  { href: "/admin/media", label: "Media", section: "catalog" },
  { href: "/admin/inventory", label: "Inventory", section: "inventory" },
  { href: "/admin/customers", label: "Customers", section: "customers" },
  { href: "/admin/reviews", label: "Reviews", section: "reviews" },
  { href: "/admin/coupons", label: "Coupons", section: "marketing" },
  { href: "/admin/notifications", label: "Notifications", section: "notifications" },
  { href: "/admin/analytics", label: "Analytics", section: "analytics" },
  { href: "/admin/settings", label: "Settings", section: "dashboard" },
]
