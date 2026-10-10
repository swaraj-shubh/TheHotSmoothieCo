import type { components } from "./schema"

type S = components["schemas"]

export type ApiErrorBody = { success: false; error: { code: string; message: string; details?: unknown } }

export type ProductCard = S["ProductCard"]
export type ProductDetail = S["ProductDetail"]
export type VariantOut = S["VariantOut"]
export type CategoryNode = S["CategoryNode"]
export type CollectionOut = S["CollectionOut"]
export type CartOut = S["CartOut"]
export type CartItemOut = S["CartItemOut"]
export type UserOut = S["UserOut"]
export type AddressOut = S["AddressOut"]
export type AddressIn = S["AddressIn"]
export type OrderOut = S["OrderOut"]
export type OrderSummary = S["OrderSummary"]
export type ShipmentOut = S["ShipmentOut"]
export type InitiateOut = S["InitiateOut"]
export type PublicReview = S["PublicReview"]
export type ReviewSummary = S["ReviewSummary"]
export type WishlistItemOut = S["WishlistItemOut"]
export type BannerOut = S["BannerOut"]
export type SearchPage = S["SearchPage"]
export type Suggestion = S["Suggestion"]

export type AdminProductOut = S["AdminProductOut"]
export type AdminProductRow = S["AdminProductRow"]
export type AdminOrderOut = S["AdminOrderOut"]
export type AdminOrderRow = S["AdminOrderRow"]
export type AdminCategoryOut = S["AdminCategoryOut"]
export type AdminCollectionOut = S["AdminCollectionOut"]
export type AttributeOut = S["AttributeOut"]
export type StockRow = S["StockRow"]
export type TransactionOut = S["TransactionOut"]
export type CustomerRow = S["CustomerRow"]
export type CustomerDetail = S["CustomerDetail"]
export type CouponOut = S["CouponOut"]
export type AdminReview = S["AdminReview"]
export type AdminNotificationOut = S["AdminNotificationOut"]
export type TemplateOut = S["TemplateOut"]
export type MediaItem = S["MediaItem"]
export type StaffOut = S["StaffOut"]
export type AuditOut = S["AuditOut"]
export type SalesPoint = S["SalesPoint"]
export type TopProduct = S["TopProduct"]
export type ReturnOut = S["ReturnOut"]

export type Page<T> = { items: T[]; next_cursor?: string | null }

export const ROLES = [
  "SUPER_ADMIN",
  "ADMIN",
  "PRODUCT_MANAGER",
  "INVENTORY_MANAGER",
  "ORDER_MANAGER",
  "CUSTOMER_SUPPORT",
  "MARKETING_MANAGER",
] as const
export type Role = (typeof ROLES)[number]
