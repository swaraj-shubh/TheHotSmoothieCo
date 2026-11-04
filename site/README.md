# The Hot Smoothie Co. storefront (customer-facing)

Static multi-page site built from the Figma file "The Hot Smoothie Co." (page: Final Suyash). No build step.

```bash
node serve.mjs 5173   # then open http://localhost:5173
```

| Page | File |
|---|---|
| Home (from Figma) | `index.html` |
| All posters, filter + sort | `shop.html` |
| Collection | `collection.html?c=nerd-fiction` |
| Product | `product.html?p=soul-punk` |
| Cart | `cart.html` |
| Checkout / Order confirmed | `checkout.html`, `order-confirmed.html` |
| Wishlist, Gift cards | `wishlist.html`, `gift-cards.html` |
| About, FAQ, Contact, Shipping & returns, 404 | `about.html`, `faq.html`, `contact.html`, `shipping-returns.html`, `404.html` |
| Coming soon (layered parallax + waiting-list form) | `coming-soon.html`, `css/coming-soon.css`, `js/coming-soon.js`, art in `assets/coming-soon/` |

- Catalogue and policy numbers live in `js/data.js`. Cart and wishlist use `localStorage`.
- Placeholders to confirm are listed at the top of `js/data.js`.
- Checkout is front-end only: no payment is taken and no order is sent anywhere. Wire `pages.checkout` in `js/app.js` to the backend (`/api/v1/checkout`, `/payments`) when ready.
- Display font: install Apfel Grotezk (or add an `@font-face`) and it replaces the Space Grotesk stand-in.
