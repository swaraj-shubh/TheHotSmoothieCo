# API

Base URL: `https://api.<domain>/api/v1` (health checks live at `/health/*`).
Interactive docs: `/docs` (Swagger) and `/redoc` in development and staging; disabled in production.

## Conventions

**Authentication.** `Authorization: Bearer <access_token>`. Access tokens are JWTs valid for
15 minutes; refresh tokens are opaque, rotate on every `POST /auth/refresh`, and replaying an old one
revokes the session. The Next.js app keeps both tokens in httpOnly cookies on its own domain and
calls the API server-side (BFF), so tokens never reach browser JavaScript and the API needs no CSRF
protection. Refresh one request at a time per session: two concurrent refreshes with the same token
look like theft and end the session.

**Errors.** Every non-2xx response has the same shape:

```json
{ "success": false, "error": { "code": "INSUFFICIENT_INVENTORY", "message": "…", "details": [...] } }
```

`message` is safe to show to customers; branch on `code`, never on `message`. `details` is optional
structured context (validation fields, short variants, CSV row errors…).

| HTTP | Typical codes |
|---|---|
| 400 | `VALIDATION_ERROR`-style business rules: `INVALID_COUPON`, `CART_NOT_READY`, `INVALID_VARIANTS`, `INVALID_CSV`, `INVALID_TOKEN`, `INVALID_CURSOR`, `INVALID_UPLOAD`, `REFUND_NOT_ALLOWED`, `RETURN_NOT_ALLOWED`, `CANNOT_CANCEL`, `ORDER_TOTAL_TOO_LOW`… |
| 401 | `UNAUTHORIZED`, `INVALID_TOKEN`, `INVALID_CREDENTIALS`, `SESSION_EXPIRED` |
| 403 | `FORBIDDEN`, `ACCOUNT_DISABLED` |
| 404 | `*_NOT_FOUND` (also returned for other users' resources — existence is never revealed) |
| 409 | `INSUFFICIENT_INVENTORY`, `PRICE_CHANGED`, `EMAIL_TAKEN`, `SKU_TAKEN`, `SLUG_TAKEN`, `REVIEW_EXISTS`, `ORDER_NOT_PAYABLE`, `INVALID_STATE_TRANSITION`, `IN_USE`, `CONFLICT` |
| 413 | `PAYLOAD_TOO_LARGE` (1 MB JSON, 16 MB uploads) |
| 422 | `VALIDATION_ERROR` with `details: [{field, message}]` |
| 429 | `RATE_LIMITED`, `LOGIN_LOCKED` |
| 502 / 503 | `PAYMENT_PROVIDER_ERROR`, `SHIPPING_PROVIDER_ERROR`, `PAYMENTS_UNAVAILABLE`, `SHIPPING_UNAVAILABLE`, `MEDIA_STORAGE_UNAVAILABLE` |
| 500 | `INTERNAL_ERROR` (details are logged with the request ID, never returned) |

**Request IDs.** Send `X-Request-ID` (alphanumeric/dashes) or one is generated; it's echoed on the
response and attached to every log line and audit record. Quote it in support tickets.

**Money** is always integer **paise** (`price_paise: 149900` = ₹1,499.00). Format on the client.

**Pagination** is cursor-based: `?limit=24&cursor=<next_cursor>`; responses are
`{ "items": [...], "next_cursor": "…" | null }`. Cursors are opaque; don't build them.

**Idempotency.** `POST /checkout` and staff `POST /admin/orders/{id}/refunds` require an
`Idempotency-Key` header (8–80 chars of `[A-Za-z0-9_-]`, a UUID is ideal). Generate one per user
intent and reuse it on retries: you get the original result (`200` on replay vs `201` first time),
never a duplicate order or refund.

**Guest carts.** The first `POST /cart/items` without a login returns `cart_token`; send it back as
`X-Cart-Token`. After login, call `POST /cart/merge` with the same header. Checkout requires login.

**Price safety.** Send `expected_total_paise` (what the customer saw) to `/checkout`; if prices
changed, you get `409 PRICE_CHANGED` with the new total instead of a surprise charge.

**Rate limits** (per client IP, fixed window, shared across instances):

| Scope | Limit |
|---|---|
| login | 10 / 5 min (+ 10 failures / 15 min per account) |
| register | 5 / hour |
| refresh | 30 / 5 min |
| forgot / reset password | 5 / hour, 10 / hour |
| verify email / resend | 20 / hour, 3 / hour |
| public catalog | 600 / min |
| search | 120 / min |
| cart, wishlist | 120 / min |
| coupon apply | 20 / 5 min |
| checkout | 10 / min |
| payments | 30 / min |
| reviews (write) | 20 / hour |
| admin | 300 / min |

**Webhooks** (not in OpenAPI): `POST /api/v1/webhooks/razorpay` (HMAC `X-Razorpay-Signature`
over the raw body) and `POST /api/v1/webhooks/shipping` (`x-api-key` shared token). Invalid
signatures get `400`; processing failures get `5xx` so the provider retries; duplicates are
acknowledged without reprocessing.

## Endpoints

Regenerate with `python -m scripts.gen_api_index` (🔒 = requires a bearer token; admin routes also
require the roles listed in their descriptions / the README role table).

<!-- BEGIN ENDPOINTS (generated) -->

### auth

| Method | Path | Notes |
|---|---|---|
| `POST` | `/api/v1/auth/change-password` | 🔒 Change Password |
| `POST` | `/api/v1/auth/forgot-password` |  Forgot Password |
| `POST` | `/api/v1/auth/login` |  Login |
| `POST` | `/api/v1/auth/logout` | 🔒 Logout |
| `POST` | `/api/v1/auth/logout-all` | 🔒 Logout All |
| `POST` | `/api/v1/auth/refresh` |  Refresh |
| `POST` | `/api/v1/auth/register` |  Register |
| `POST` | `/api/v1/auth/resend-verification` | 🔒 Resend Verification |
| `POST` | `/api/v1/auth/reset-password` |  Reset Password |
| `GET` | `/api/v1/auth/sessions` | 🔒 Sessions |
| `DELETE` | `/api/v1/auth/sessions/{session_id}` | 🔒 Revoke Session |
| `POST` | `/api/v1/auth/verify-email` |  Verify Email |

### cart

| Method | Path | Notes |
|---|---|---|
| `DELETE` | `/api/v1/cart` | 🔒 Clear Cart |
| `GET` | `/api/v1/cart` | 🔒 Get Cart |
| `DELETE` | `/api/v1/cart/coupon` | 🔒 Remove Coupon |
| `POST` | `/api/v1/cart/coupon` | 🔒 Apply Coupon |
| `POST` | `/api/v1/cart/items` | 🔒 Add Item |
| `DELETE` | `/api/v1/cart/items/{item_id}` | 🔒 Remove Item |
| `PATCH` | `/api/v1/cart/items/{item_id}` | 🔒 Update Item |
| `POST` | `/api/v1/cart/merge` | 🔒 Call right after login with the guest X-Cart-Token; the guest cart is folded in and deleted. |

### catalog

| Method | Path | Notes |
|---|---|---|
| `GET` | `/api/v1/attributes` |  Filterable options (Size, Frame, Paper…) for storefront filters. Cached for an hour. |
| `GET` | `/api/v1/categories` |  Categories |
| `GET` | `/api/v1/categories/{slug}` |  Category |
| `GET` | `/api/v1/collections` |  Collections |
| `GET` | `/api/v1/collections/{slug}` |  Collection |
| `GET` | `/api/v1/products` |  Products |
| `GET` | `/api/v1/products/{slug}` |  Product |

### checkout

| Method | Path | Notes |
|---|---|---|
| `POST` | `/api/v1/checkout` | 🔒 Turns the cart into a PENDING_PAYMENT order and holds stock for the payment window. |

### health

| Method | Path | Notes |
|---|---|---|
| `GET` | `/health` |  Process is up. Never touches dependencies, so a DB blip doesn't get the container killed. |
| `GET` | `/health/live` |  Process is up. Never touches dependencies, so a DB blip doesn't get the container killed. |
| `GET` | `/health/ready` |  Dependencies reachable. Load balancers should route traffic only when this is 200. |
| `GET` | `/health/worker` |  For uptime monitors: is the background worker alive? (heartbeat every ~1 s, 60 s TTL) |

### notifications

| Method | Path | Notes |
|---|---|---|
| `GET` | `/api/v1/admin/notification-templates` | 🔒 List Templates |
| `DELETE` | `/api/v1/admin/notification-templates/{code}` | 🔒 Revert to the built-in wording. |
| `PUT` | `/api/v1/admin/notification-templates/{code}` | 🔒 Edit Template |
| `GET` | `/api/v1/admin/notifications` | 🔒 `?status=FAILED` is the dead-letter list. |
| `POST` | `/api/v1/admin/notifications/{notification_id}/retry` | 🔒 Retry |
| `GET` | `/api/v1/notifications` | 🔒 My Notifications |

### orders

| Method | Path | Notes |
|---|---|---|
| `GET` | `/api/v1/orders` | 🔒 My Orders |
| `GET` | `/api/v1/orders/{order_id}` | 🔒 Get Order |
| `POST` | `/api/v1/orders/{order_id}/cancel` | 🔒 Unpaid: cancelled immediately. Paid but not yet dispatched: cancelled and refunded in full. |
| `POST` | `/api/v1/orders/{order_id}/return` | 🔒 Request Return |

### payments

| Method | Path | Notes |
|---|---|---|
| `GET` | `/api/v1/payments/orders/{order_id}` | 🔒 Poll after checkout while waiting for the webhook. |
| `POST` | `/api/v1/payments/orders/{order_id}/initiate` | 🔒 Creates (or reuses) the gateway order; pass the result to the Razorpay Checkout widget. |
| `POST` | `/api/v1/payments/orders/{order_id}/simulate` | 🔒 Development only (PAYMENTS_PROVIDER=dev): complete or decline the payment for an order. |
| `POST` | `/api/v1/payments/orders/{order_id}/verify` | 🔒 Widget success callback. Signature-checked and re-fetched from the gateway; the webhook |

### reviews

| Method | Path | Notes |
|---|---|---|
| `GET` | `/api/v1/admin/reviews` | 🔒 Moderation Queue |
| `POST` | `/api/v1/admin/reviews/{review_id}/approve` | 🔒 Approve |
| `POST` | `/api/v1/admin/reviews/{review_id}/reject` | 🔒 Reject |
| `GET` | `/api/v1/products/{slug}/reviews` |  Product Reviews |
| `GET` | `/api/v1/products/{slug}/reviews/summary` |  Review Summary |
| `POST` | `/api/v1/reviews` | 🔒 Every review is moderated before it appears; verified-purchase badge is computed server-side. |
| `GET` | `/api/v1/reviews/mine` | 🔒 My Reviews |
| `DELETE` | `/api/v1/reviews/{review_id}` | 🔒 Delete |
| `PATCH` | `/api/v1/reviews/{review_id}` | 🔒 Update |
| `POST` | `/api/v1/reviews/{review_id}/media` | 🔒 Upload Photo |

### search

| Method | Path | Notes |
|---|---|---|
| `GET` | `/api/v1/search` |  Keyword search with every catalog filter (category, price, size/frame, stock) and sorting. |
| `GET` | `/api/v1/search/suggest` |  Search-as-you-type. |

### shipping

| Method | Path | Notes |
|---|---|---|
| `GET` | `/api/v1/shipping/orders/{order_id}` | 🔒 Tracking |
| `GET` | `/api/v1/shipping/serviceability` |  Can we deliver to this PIN code, and how fast? Cached per pincode for 6 hours. |

### storefront

| Method | Path | Notes |
|---|---|---|
| `GET` | `/api/v1/banners` |  Storefront Banners |

### users

| Method | Path | Notes |
|---|---|---|
| `DELETE` | `/api/v1/users/me` | 🔒 Delete Me |
| `GET` | `/api/v1/users/me` | 🔒 Me |
| `PATCH` | `/api/v1/users/me` | 🔒 Update Me |
| `GET` | `/api/v1/users/me/addresses` | 🔒 List Addresses |
| `POST` | `/api/v1/users/me/addresses` | 🔒 Create Address |
| `DELETE` | `/api/v1/users/me/addresses/{address_id}` | 🔒 Delete Address |
| `PUT` | `/api/v1/users/me/addresses/{address_id}` | 🔒 Replace Address |

### wishlist

| Method | Path | Notes |
|---|---|---|
| `GET` | `/api/v1/wishlist` | 🔒 List Items |
| `POST` | `/api/v1/wishlist` | 🔒 Add |
| `DELETE` | `/api/v1/wishlist/{item_id}` | 🔒 Remove |
| `POST` | `/api/v1/wishlist/{item_id}/move-to-cart` | 🔒 Move To Cart |

### admin

| Method | Path | Notes |
|---|---|---|
| `GET` | `/api/v1/admin/analytics/customers` | 🔒 Customer Analytics |
| `GET` | `/api/v1/admin/analytics/sales` | 🔒 Sales |
| `GET` | `/api/v1/admin/analytics/top-products` | 🔒 Top Products |
| `GET` | `/api/v1/admin/audit-logs` | 🔒 Audit Logs |
| `GET` | `/api/v1/admin/banners` | 🔒 List Banners |
| `POST` | `/api/v1/admin/banners` | 🔒 Create Banner |
| `DELETE` | `/api/v1/admin/banners/{banner_id}` | 🔒 Delete Banner |
| `PUT` | `/api/v1/admin/banners/{banner_id}` | 🔒 Update Banner |
| `GET` | `/api/v1/admin/customers` | 🔒 Customers |
| `GET` | `/api/v1/admin/customers/{user_id}` | 🔒 Customer |
| `PATCH` | `/api/v1/admin/customers/{user_id}` | 🔒 Deactivating signs the customer out of every device immediately. |
| `GET` | `/api/v1/admin/dashboard` | 🔒 Dashboard |
| `GET` | `/api/v1/admin/media` | 🔒 Every product image, newest first (uploads happen on the product page). |
| `GET` | `/api/v1/admin/products/export.csv` | 🔒 Export Products |
| `POST` | `/api/v1/admin/products/import` | 🔒 All-or-nothing. Errors come back per row (422-style details) and nothing is saved. |
| `GET` | `/api/v1/admin/settings` | 🔒 Read-only view of store policy and which integrations are configured (never secrets). |
| `GET` | `/api/v1/admin/users` | 🔒 Staff |
| `PUT` | `/api/v1/admin/users/{user_id}/roles` | 🔒 Set Roles |

### admin: catalog

| Method | Path | Notes |
|---|---|---|
| `GET` | `/api/v1/admin/attributes` | 🔒 List Attributes |
| `POST` | `/api/v1/admin/attributes` | 🔒 Create Attribute |
| `POST` | `/api/v1/admin/attributes/{attribute_id}/values` | 🔒 Add Attribute Values |
| `GET` | `/api/v1/admin/categories` | 🔒 List Categories |
| `POST` | `/api/v1/admin/categories` | 🔒 Create Category |
| `DELETE` | `/api/v1/admin/categories/{category_id}` | 🔒 Delete Category |
| `PATCH` | `/api/v1/admin/categories/{category_id}` | 🔒 Update Category |
| `GET` | `/api/v1/admin/collections` | 🔒 List Collections |
| `POST` | `/api/v1/admin/collections` | 🔒 Create Collection |
| `DELETE` | `/api/v1/admin/collections/{collection_id}` | 🔒 Delete Collection |
| `PATCH` | `/api/v1/admin/collections/{collection_id}` | 🔒 Update Collection |
| `GET` | `/api/v1/admin/products` | 🔒 List Products |
| `POST` | `/api/v1/admin/products` | 🔒 Create Product |
| `GET` | `/api/v1/admin/products/{product_id}` | 🔒 Get Product |
| `PATCH` | `/api/v1/admin/products/{product_id}` | 🔒 Archive with `{"status": "ARCHIVED"}`. Products are never hard-deleted (orders reference them). |
| `POST` | `/api/v1/admin/products/{product_id}/media` | 🔒 Upload Media |
| `DELETE` | `/api/v1/admin/products/{product_id}/media/{media_id}` | 🔒 Delete Media |
| `PATCH` | `/api/v1/admin/products/{product_id}/media/{media_id}` | 🔒 Update Media |
| `POST` | `/api/v1/admin/products/{product_id}/variants` | 🔒 Add Variant |
| `PATCH` | `/api/v1/admin/products/{product_id}/variants/{variant_id}` | 🔒 Update Variant |

### admin: coupons

| Method | Path | Notes |
|---|---|---|
| `GET` | `/api/v1/admin/coupons` | 🔒 List Coupons |
| `POST` | `/api/v1/admin/coupons` | 🔒 Create |
| `GET` | `/api/v1/admin/coupons/{coupon_id}` | 🔒 Get |
| `PATCH` | `/api/v1/admin/coupons/{coupon_id}` | 🔒 Disable with `{"is_active": false}`; coupons are never deleted (orders reference them). |

### admin: inventory

| Method | Path | Notes |
|---|---|---|
| `GET` | `/api/v1/admin/inventory` | 🔒 Stock |
| `POST` | `/api/v1/admin/inventory/{variant_id}/adjust` | 🔒 Adjust |
| `GET` | `/api/v1/admin/inventory/{variant_id}/history` | 🔒 History |

### admin: orders

| Method | Path | Notes |
|---|---|---|
| `GET` | `/api/v1/admin/orders` | 🔒 List Orders |
| `GET` | `/api/v1/admin/orders/{order_id}` | 🔒 Get Order |
| `POST` | `/api/v1/admin/orders/{order_id}/cancel` | 🔒 Cancels at any pre-dispatch stage: cancels the courier booking, restocks, refunds in full. |
| `POST` | `/api/v1/admin/orders/{order_id}/process` | 🔒 Start Processing |
| `POST` | `/api/v1/admin/orders/{order_id}/refunds` | 🔒 Partial or full refund. Reusing an Idempotency-Key returns the original refund, never a second one. |
| `POST` | `/api/v1/admin/orders/{order_id}/shipments` | 🔒 Books the courier, assigns an AWB and generates the label. If AWB assignment fails the |
| `GET` | `/api/v1/admin/returns` | 🔒 List Returns |
| `POST` | `/api/v1/admin/returns/{return_id}/approve` | 🔒 Approve Return |
| `POST` | `/api/v1/admin/returns/{return_id}/receive` | 🔒 Parcel is back: closes the return, optionally restocks, refunds in full. |
| `POST` | `/api/v1/admin/returns/{return_id}/reject` | 🔒 Reject Return |
| `POST` | `/api/v1/admin/shipments/{shipment_id}/awb` | 🔒 Retry Awb |
| `POST` | `/api/v1/admin/shipments/{shipment_id}/sync` | 🔒 Sync Tracking |

<!-- END ENDPOINTS -->
