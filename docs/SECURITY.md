# Security

Report vulnerabilities privately to `security@<your-domain>` (placeholder: create this mailbox before launch). Please don't open public issues.

## Controls

| Threat | Control |
|---|---|
| Credential stuffing / brute force | Per-IP rate limits on every auth route; per-account lockout after 10 failures in 15 min (checked before the password, identical for unknown emails); Argon2id hashing with transparent rehash |
| Account enumeration | Identical response and timing for wrong password vs unknown email (dummy hash); forgot-password always returns 202. Trade-off: registration does reveal an existing email (`EMAIL_TAKEN`), a standard UX choice |
| Session theft | 15-min JWTs; opaque refresh tokens stored hashed and rotated on every use; reuse of a rotated token revokes the session; every request re-checks the session row, so logout, password reset and deactivation are immediate |
| XSS / token exfiltration | Tokens live in httpOnly cookies on the Next.js domain (BFF), never in browser JS; API returns JSON only; user content stored as plain text, control characters rejected; banner links restricted to on-site paths or https |
| CSRF | Not applicable to the API (bearer tokens, no cookies); the Next.js BFF uses SameSite cookies |
| Broken access control (IDOR) | Every customer query is scoped by `user_id`; other users' resources return 404; RBAC enforced server-side on every admin route (`require_roles`); SUPER_ADMIN can't remove their own role |
| Injection | SQLAlchemy bound parameters everywhere (no string-built SQL); full-text queries built only from `\w` tokens; CSV export neutralises spreadsheet formulas |
| Price / payment manipulation | Prices, discounts, shipping and tax computed server-side from the DB; `expected_total_paise` guard; payment state only from verified gateway data (HMAC signature + server-side re-fetch); amount mismatch → auto-refund |
| Replay / double processing | Idempotency keys (checkout, refunds), webhook event dedupe, single-use email tokens consumed atomically |
| Webhook forgery | Razorpay: HMAC-SHA256 over the raw body, constant-time compare; Shiprocket: shared token, constant-time compare; 512 KB cap |
| Malicious uploads | Magic-byte sniffing (JPEG/PNG/WebP only), 15 MB cap, bounded reads; files go to Cloudinary, never the API's disk |
| Resource exhaustion | Body limits (1 MB JSON / 16 MB uploads, enforced before parsing, including chunked bodies); bounded page sizes (max 100 per page); rate limits |
| IP spoofing (rate-limit bypass) | Client IP only from `CLIENT_IP_HEADER` (e.g. Cloudflare's) or the entry our own proxy appended (`TRUSTED_PROXY_HOPS`); uvicorn `--no-proxy-headers` |
| Secrets exposure | Secrets only from environment; `SecretStr` in config; production refuses to boot with a weak JWT secret or rate limiting disabled; reset/verify tokens scrubbed from the outbox after sending; audit log redacts password/token/secret fields; Sentry `send_default_pii=False`; error responses never include internals |
| Clickjacking / sniffing | `X-Frame-Options: DENY`, `X-Content-Type-Options: nosniff`, HSTS, strict referrer and permissions policies on every response |
| Insider misuse | Audit log of every admin mutation (actor snapshot, target, outcome incl. denied attempts, IP, request ID, redacted body); least-privilege roles |
| Vulnerable dependencies | `pip-audit` and Trivy image scan in CI (build fails on fixable HIGH/CRITICAL) |

## Roles

| Role | Can |
|---|---|
| SUPER_ADMIN | everything, incl. granting roles |
| ADMIN | everything except roles; customer deactivation; audit log |
| PRODUCT_MANAGER | catalog, media, CSV import/export, review moderation |
| INVENTORY_MANAGER | stock levels, adjustments, history |
| ORDER_MANAGER | orders, shipments, cancellations, refunds, returns |
| CUSTOMER_SUPPORT | read orders/customers, review moderation, notification retries |
| MARKETING_MANAGER | coupons, banners, email templates, analytics |

## Deployment requirements

- **Client IP**: behind Cloudflare set `CLIENT_IP_HEADER=cf-connecting-ip` *and* only accept origin
  traffic from Cloudflare (Render custom domain behind the orange cloud; optionally Authenticated
  Origin Pulls). Without Cloudflare: `TRUSTED_PROXY_HOPS=1`. Never trust `X-Forwarded-For` blindly.
- `ENVIRONMENT=production` disables `/docs` and enforces the config checks above.
- `CORS_ORIGINS` must list only your own frontends.
- Rotate `JWT_SECRET` to sign everyone out (incident response); rotate gateway webhook secrets in
  both the provider dashboard and the environment at the same time.

## Known trade-offs

- **Lockout as DoS**: an attacker can lock a real customer out of password login for 15 minutes;
  password reset still works.
- **At-least-once email**: a worker crash after the provider accepted a message can resend it once.
- **Audit write after the response**: a crash in that instant loses one audit row (see
  `app/audit/middleware.py` for the upgrade path if compliance requires a guaranteed trail).
- **Concurrent refresh**: two simultaneous refreshes with the same token end the session (the BFF
  must serialise refreshes).

## Go-live checklist

- [ ] Strong `JWT_SECRET` (Render `generateValue`), all gateway secrets set, `.env` never committed
- [ ] `CORS_ORIGINS`, `FRONTEND_URL`, client-IP settings correct for the real topology
- [ ] Razorpay webhook secret set and events subscribed; Shiprocket webhook token set
- [ ] First SUPER_ADMIN created with `scripts.create_admin`; staff accounts least-privilege
- [ ] Sentry DSN set for API and worker; uptime monitors on `/health/ready` and `/health/worker`
- [ ] Backups verified with a test restore (see DATABASE.md)
- [ ] GitHub: branch protection on `main`, required reviewers on the `production` environment
