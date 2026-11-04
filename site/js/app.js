/* The Hot Smoothie Co. storefront: shared chrome, cart, wishlist and page controllers.
   No build step. State lives in localStorage; swap the `api` section for real endpoints
   (the backend in swaraj-shubh/TheHotSmoothieCo exposes /api/v1/*) when wiring up. */
(function () {
  "use strict";
  document.documentElement.classList.add("js");
  const D = window.HSC;
  const $ = (s, r = document) => r.querySelector(s);
  const $$ = (s, r = document) => [...r.querySelectorAll(s)];
  const esc = (s) => String(s ?? "").replace(/[&<>"']/g, (c) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" }[c]));
  const money = (n) => "Rs. " + Number(n).toLocaleString("en-IN");
  const byProduct = (slug) => D.products.find((p) => p.slug === slug);
  const byCollection = (slug) => D.collections.find((c) => c.slug === slug);
  const priceFor = (sizeId) => (D.sizes.find((s) => s.id === sizeId) || D.sizes[0]).price;
  const param = (k) => new URLSearchParams(location.search).get(k);

  /* ---------- storage ---------- */
  const store = {
    get(k, fb) { try { const v = localStorage.getItem(k); return v ? JSON.parse(v) : fb; } catch { return fb; } },
    set(k, v) { try { localStorage.setItem(k, JSON.stringify(v)); } catch { /* private mode */ } },
    del(k) { try { localStorage.removeItem(k); } catch { /* ignore */ } }
  };

  /* ---------- cart ---------- */
  const cart = {
    items: () => store.get("hsc_cart", []),
    save(items) { store.set("hsc_cart", items); updateBadge(); document.dispatchEvent(new Event("cart:change")); },
    count: () => cart.items().reduce((n, i) => n + i.qty, 0),
    add(line) {
      const items = cart.items();
      const hit = items.find((i) => i.id === line.id);
      if (hit) hit.qty = Math.min(10, hit.qty + (line.qty || 1)); else items.push({ ...line, qty: line.qty || 1 });
      cart.save(items);
    },
    setQty(id, qty) {
      const items = cart.items().map((i) => (i.id === id ? { ...i, qty } : i)).filter((i) => i.qty > 0);
      cart.save(items);
    },
    remove(id) { cart.save(cart.items().filter((i) => i.id !== id)); },
    clear() { cart.save([]); },
    totals() {
      const items = cart.items();
      const physical = items.filter((i) => i.slug !== "gift-card");
      const subtotal = items.reduce((n, i) => n + i.price * i.qty, 0);
      const physSub = physical.reduce((n, i) => n + i.price * i.qty, 0);
      const code = store.get("hsc_coupon", null);
      const discount = code === D.coupon.code ? Math.round(physSub * D.coupon.percent / 100) : 0;
      const afterDisc = subtotal - discount;
      const shipping = physical.length === 0 ? 0 : afterDisc >= D.freeShippingAbove ? 0 : D.shippingFee;
      return { subtotal, discount, shipping, total: afterDisc + shipping, away: Math.max(0, D.freeShippingAbove - afterDisc), hasPhysical: physical.length > 0, code };
    }
  };
  const lineFor = (p, size, qty = 1) => ({ id: `${p.slug}|${size}`, slug: p.slug, title: p.title, size, price: priceFor(size), qty, img: p.img });

  /* ---------- wishlist ---------- */
  const wish = {
    all: () => store.get("hsc_wish", []),
    has: (slug) => wish.all().includes(slug),
    toggle(slug) { const w = wish.all(); const i = w.indexOf(slug); if (i >= 0) w.splice(i, 1); else w.push(slug); store.set("hsc_wish", w); return i < 0; }
  };

  /* ---------- toast ---------- */
  function toast(html) {
    let r = $(".toast-region");
    if (!r) { r = document.createElement("div"); r.className = "toast-region"; r.setAttribute("role", "status"); r.setAttribute("aria-live", "polite"); document.body.append(r); }
    const t = document.createElement("div"); t.className = "toast"; t.innerHTML = html; r.append(t);
    setTimeout(() => { t.classList.add("out"); setTimeout(() => t.remove(), 260); }, 3800);
  }

  /* ---------- chrome ---------- */
  const NAV = [["collections", "Collections", "shop.html"], ["about", "About", "about.html"]];
  function header(page, overlay) {
    const cur = (k) => (page === k || (k === "collections" && ["shop", "collection", "product"].includes(page)) ? ' aria-current="page"' : "");
    return `<header class="header${overlay ? " header--overlay" : ""}" id="hdr">
      <a class="logo" href="index.html" aria-label="The Hot Smoothie Co. home"><span>The Hot Smoothie Co.</span></a>
      <button class="nav-toggle" aria-expanded="false" aria-controls="nav">Menu</button>
      <nav id="nav" aria-label="Main">
        ${NAV.map(([k, l, h]) => `<a href="${h}"${cur(k)}>${l}</a>`).join("")}
        <a href="wishlist.html"${cur("wishlist")}>Wishlist</a>
        <a class="cart-link" href="cart.html"${cur("cart")}>Cart (<span data-cart-count>0</span>)</a>
      </nav>
    </header>`;
  }
  function footer() {
    return `<footer class="footer">
      <div class="footer__cols">
        <div class="footer__col"><span class="t-label">Shop</span><a href="shop.html">Collections</a><a href="shop.html?new=1">New drops</a><a href="gift-cards.html">Gift cards</a><a href="about.html">About</a></div>
        <div class="footer__col"><span class="t-label">Help</span><a href="shipping-returns.html">Shipping &amp; returns</a><a href="faq.html">FAQ</a><a href="contact.html">Contact</a></div>
        <div class="footer__col"><span class="t-label">Follow</span><a href="#" rel="noopener">Instagram</a><a href="#" rel="noopener">YouTube</a></div>
      </div>
      <p class="footer__mark">The Hot Smoothie Co.</p>
      <div class="footer__fine t-cap"><span>© 2026 The Hot Smoothie Co.</span><span>300 GSM glossy. Zero good taste required.</span></div>
    </footer>`;
  }
  function mountChrome() {
    const body = document.body, page = body.dataset.page, overlay = body.dataset.header === "overlay";
    const top = `<div class="topbar"><span>300 GSM Glossy Print</span><span>Free Delivery on orders above ${money(D.freeShippingAbove)}</span></div>`;
    body.insertAdjacentHTML("afterbegin", top + header(page, overlay));
    body.insertAdjacentHTML("beforeend", footer());
    const hdr = $("#hdr"), tgl = $(".nav-toggle");
    tgl.addEventListener("click", () => { const o = hdr.classList.toggle("open"); tgl.setAttribute("aria-expanded", o); });
    updateBadge();
  }
  let lastCount = null;
  function updateBadge() {
    const n = cart.count();
    $$("[data-cart-count]").forEach((e) => { e.textContent = n; if (lastCount !== null && n !== lastCount) { e.classList.remove("bump"); void e.offsetWidth; e.classList.add("bump"); } });
    lastCount = n;
  }

  /* ---------- bits of html ---------- */
  const tagBtn = (attrs, label = "Add to cart") => `<button class="tag-btn" ${attrs}><span>${label}</span></button>`;
  function productCard(p) {
    const on = wish.has(p.slug);
    return `<article class="card">
      <a class="card__media" href="product.html?p=${p.slug}" aria-label="${esc(p.title)}"><img src="${p.img}" alt="${esc(p.title)} poster" loading="lazy"></a>
      ${p.tag ? `<span class="chip">${esc(p.tag)}</span>` : ""}
      <button class="card__wish" data-wish="${p.slug}" aria-pressed="${on}" aria-label="Save ${esc(p.title)} to wishlist">${on ? "♥" : "♡"}</button>
      <div class="card__meta"><span class="t-cap muted">${esc(byCollection(p.collection).name)}</span><a class="card__title" href="product.html?p=${p.slug}">${esc(p.title)}</a></div>
      <div class="card__row"><span class="t-price">From ${money(D.sizes[0].price)}</span>${tagBtn(`data-add="${p.slug}"`)}</div>
    </article>`;
  }
  const faqItem = (f, open) => `<details class="acc"${open ? " open" : ""}><summary>${esc(f.q)}</summary><p class="acc__body">${esc(f.a)}</p></details>`;
  const crumbs = (list) => `<nav class="crumbs wrap t-cap" aria-label="Breadcrumb">${list.map(([l, h], i) => (h ? `<a href="${h}">${l}</a>` : `<span aria-current="page">${l}</span>`) + (i < list.length - 1 ? '<span aria-hidden="true">/</span>' : "")).join("")}</nav>`;

  function flash(btn) {
    const span = btn.querySelector("span"); if (!span || btn.classList.contains("is-added")) return;
    const old = span.textContent; btn.classList.add("is-added"); span.textContent = "Added ✓";
    setTimeout(() => { btn.classList.remove("is-added"); span.textContent = old; }, 1400);
  }

  /* ---------- motion: scroll reveal, header shadow, back-to-top ---------- */
  const REVEAL = ".card,.coll,.usp,.step,.review,.acc,.pick,.gift,.pass,.summary,.check-sec,.mini,.order-steps > *,.split > *,.wall-section > *,.vinyl-split > *,.statement > *,.page-head > *,.pdp__gallery,.pdp__info > *,.prose > *,.empty > *,.footer__col,.t-display,.drop-bar > *,.gift-card-preview,.err-page > *";
  function initMotion() {
    const io = "IntersectionObserver" in window ? new IntersectionObserver((es) => es.forEach((e) => { if (e.isIntersecting) { e.target.classList.add("in"); io.unobserve(e.target); } }), { threshold: 0.12, rootMargin: "0px 0px -6% 0px" }) : null;
    const tag = (root) => {
      const hits = [...(root.matches?.(REVEAL) ? [root] : []), ...root.querySelectorAll(REVEAL)].filter((el) => !el.classList.contains("reveal") && !el.closest(".hero,.header,.topbar,.toast-region,.line"));
      hits.forEach((el) => {
        const sibs = el.parentElement ? [...el.parentElement.children].filter((c) => c.matches(REVEAL)) : [];
        el.style.setProperty("--d", Math.min(sibs.indexOf(el), 5) * 90 + "ms");
        el.classList.add("reveal");
        if (io) io.observe(el); else el.classList.add("in");
      });
    };
    tag(document.body);
    new MutationObserver((ms) => ms.forEach((m) => m.addedNodes.forEach((n) => n.nodeType === 1 && tag(n)))).observe(document.body, { childList: true, subtree: true });
    const hdr = $("#hdr"), up = document.createElement("button");
    up.className = "page-top"; up.setAttribute("aria-label", "Back to top"); up.textContent = "↑";
    up.addEventListener("click", () => window.scrollTo({ top: 0, behavior: "smooth" })); document.body.append(up);
    const onScroll = () => { hdr.classList.toggle("scrolled", scrollY > 8 && !hdr.classList.contains("header--overlay")); up.classList.toggle("show", scrollY > 900); };
    addEventListener("scroll", onScroll, { passive: true }); onScroll();
  }

  /* ---------- global click delegation ---------- */
  document.addEventListener("click", (e) => {
    const add = e.target.closest("[data-add]");
    if (add) {
      const p = byProduct(add.dataset.add); if (!p) return;
      cart.add(lineFor(p, add.dataset.size || "A4"));
      flash(add);
      toast(`<span>${esc(p.title)} is in your cart.</span><a href="cart.html">View cart</a>`);
    }
    const w = e.target.closest("[data-wish]");
    if (w) {
      const on = wish.toggle(w.dataset.wish);
      w.classList.remove("pop"); void w.offsetWidth; w.classList.add("pop");
      $$(`[data-wish="${w.dataset.wish}"]`).forEach((b) => { b.setAttribute("aria-pressed", on); if (b.classList.contains("card__wish")) b.textContent = on ? "♥" : "♡"; else b.textContent = on ? "♥ Saved" : "♡ Save for later"; });
      toast(on ? "Saved. Your wall will be ready when you are." : "Removed from your wishlist.");
      if (document.body.dataset.page === "wishlist") pages.wishlist();
    }
  });

  /* ---------- pages ---------- */
  const pages = {};

  pages.home = function () {
    const grid = $("#bestsellers"); if (grid) grid.innerHTML = D.products.slice(0, 3).map(productCard).join("");
    const faq = $("#home-faq"); if (faq) faq.innerHTML = D.faqs.map((f, i) => faqItem(f, i === 0)).join("");
    // drop countdown
    const t = $("[data-timer]");
    if (t) {
      const tick = () => {
        let s = Math.max(0, Math.floor((new Date(D.dropDate) - Date.now()) / 1000));
        const v = [Math.floor(s / 86400), Math.floor(s % 86400 / 3600), Math.floor(s % 3600 / 60), s % 60];
        $$("b", t).forEach((b, i) => (b.textContent = String(v[i]).padStart(2, "0")));
      };
      tick(); setInterval(tick, 1000);
    }
    // wall colour + upload
    const mock = $("#wall-mock"), chip = $("#wall-chip");
    $$('input[name="wall"]').forEach((r) => r.addEventListener("change", () => {
      mock.style.backgroundImage = ""; mock.classList.remove("has-photo");
      mock.style.setProperty("--wall", r.value); chip.textContent = "WALL: " + r.dataset.name.toUpperCase();
    }));
    const file = $("#wall-file");
    if (file) {
      $("#wall-browse").addEventListener("click", () => file.click());
      file.addEventListener("change", () => {
        const f = file.files[0]; if (!f || !/^image\/(jpeg|png)$/.test(f.type)) { toast("JPG or PNG only, please."); return; }
        mock.style.backgroundImage = `url(${URL.createObjectURL(f)})`; mock.classList.add("has-photo"); chip.textContent = "YOUR WALL";
      });
    }
    // vinyl
    const player = $("#player");
    if (player) {
      const tracks = ["Hang Tight (Croc Remix) — The Smoothies", "Side Eye, Slow Burn", "Pani Puri at 2 AM", "Lights Out, Opinions On", "Frame It Crooked", "Fanboy Without a Cause", "Croc Outro (He Knows)"];
      let i = 0, sec = 0, playing = true;
      const len = 227, fmt = (n) => `${Math.floor(n / 60)}:${String(n % 60).padStart(2, "0")}`;
      const paint = () => { $("#track").textContent = tracks[i]; $("#track-n").textContent = `${i + 1} / ${tracks.length}`; $("#t-now").textContent = fmt(sec); $("#bar").style.width = (sec / len * 100) + "%"; };
      const setPlaying = (p) => { playing = p; player.classList.toggle("paused", !p); $("#play").textContent = p ? "❚❚" : "▶"; $("#play").setAttribute("aria-label", p ? "Pause" : "Play"); $("#status").textContent = p ? "PLAYING" : "PAUSED"; };
      $("#play").addEventListener("click", () => setPlaying(!playing));
      $("#prev").addEventListener("click", () => { i = (i + tracks.length - 1) % tracks.length; sec = 0; paint(); });
      $("#next").addEventListener("click", () => { i = (i + 1) % tracks.length; sec = 0; paint(); });
      setInterval(() => { if (!playing) return; sec++; if (sec >= len) { i = (i + 1) % tracks.length; sec = 0; } paint(); }, 1000);
      paint(); setPlaying(true);
    }
    pages.clubForm();
  };

  pages.clubForm = function () {
    const f = $("#club-form"); if (!f) return;
    f.addEventListener("submit", (e) => {
      e.preventDefault();
      const em = $("input", f);
      if (!em.checkValidity()) { em.reportValidity(); return; }
      store.set("hsc_club", em.value);
      f.innerHTML = `<p class="t-sub">You're in. Code <b>${D.coupon.code}</b> takes ${D.coupon.percent}% off your first order.</p>`;
    });
  };

  pages.shop = function () {
    const grid = $("#grid"), count = $("#count");
    const state = { c: param("c") || "all", sort: "featured", onlyNew: param("new") === "1" };
    const chips = $("#filters");
    chips.innerHTML = [["all", "All"], ...D.collections.map((c) => [c.slug, c.name])].map(([v, l]) =>
      `<label class="pill"><input type="radio" name="f" value="${v}"${state.c === v ? " checked" : ""}><span>${esc(l)}</span></label>`).join("");
    const draw = () => {
      let list = D.products.filter((p) => (state.c === "all" || p.collection === state.c) && (!state.onlyNew || p.tag === "New drop"));
      if (state.sort === "az") list = [...list].sort((a, b) => a.title.localeCompare(b.title));
      count.textContent = `${list.length} ${list.length === 1 ? "poster" : "posters"}`;
      grid.innerHTML = list.length ? list.map(productCard).join("") : `<div class="empty"><p class="t-head">Nothing here yet.</p><p>The next drop is on its way.</p><a class="btn" href="shop.html">[ See everything ]</a></div>`;
    };
    chips.addEventListener("change", (e) => { state.c = e.target.value; state.onlyNew = false; draw(); });
    $("#sort").addEventListener("change", (e) => { state.sort = e.target.value; draw(); });
    draw();
  };

  pages.collection = function () {
    const c = byCollection(param("c")) || D.collections[0];
    document.title = `${c.name} · The Hot Smoothie Co.`;
    $("#c-name").textContent = c.name; $("#c-tag").textContent = c.tagline; $("#c-story").textContent = c.story;
    $("#c-crumb").textContent = c.name; $("#c-img").src = c.img; $("#c-img").alt = `${c.name} posters in a living room`;
    const list = D.products.filter((p) => p.collection === c.slug);
    $("#c-count").textContent = `${list.length} ${list.length === 1 ? "poster" : "posters"}`;
    $("#grid").innerHTML = list.map(productCard).join("");
    $("#others").innerHTML = D.collections.filter((x) => x.slug !== c.slug).map((x) => `
      <a class="coll" href="collection.html?c=${x.slug}"><span class="coll__media"><img src="${x.img}" alt="" loading="lazy"><span class="coll__name t-head">${esc(x.name)}</span></span></a>`).join("");
  };

  pages.product = function () {
    const p = byProduct(param("p"));
    const root = $("#pdp");
    if (!p) { root.innerHTML = `<div class="empty wrap"><img src="assets/croc-wordmark.png" alt=""><h2 class="t-display">That poster doesn't exist.</h2><p>The croc checked twice.</p><a class="btn" href="shop.html">[ Back to the shop ]</a></div>`; return; }
    document.title = `${p.title} · The Hot Smoothie Co.`;
    const col = byCollection(p.collection);
    $("#crumbs").innerHTML = crumbs([["Home", "index.html"], ["Collections", "shop.html"], [esc(col.name), `collection.html?c=${col.slug}`], [esc(p.title)]]);
    const views = [{ l: "Poster", img: p.img, framed: false }, { l: "On the wall", img: p.img, framed: true }];
    if (p.room) views.push({ l: "In a room", img: p.room, framed: false });
    let size = "A4", qty = 1, view = 0;
    const walls = [["Peach", "#e8b7a0"], ["Linen", "#f2eadb"], ["Ink", "#1c1a19"], ["Croc green", "#4ca33b"]];
    const sizeFor = () => D.sizes.find((s) => s.id === size);
    root.innerHTML = `
      <div class="pdp__gallery">
        <div class="pdp__thumbs" id="thumbs">${views.map((v, i) => `<button data-v="${i}" aria-label="${v.l}" aria-current="${i === 0}"><img src="${v.img}" alt=""></button>`).join("")}</div>
        <div class="pdp__main" id="main"><img id="main-img" src="${p.img}" alt="${esc(p.title)} poster"></div>
      </div>
      <div class="pdp__info">
        <div class="pdp__title-row"><div style="display:grid;gap:12px"><a class="chip" href="collection.html?c=${col.slug}" style="width:fit-content">${esc(col.name)}</a><h1 class="t-display">${esc(p.title)}</h1></div></div>
        <p class="t-sub">${esc(p.blurb)}</p>
        <p>${esc(p.story)}</p>
        <p class="t-cap"><b>Hang it if</b> ${esc(p.hangIf)}</p>
        <div class="pdp__buy">
          <div style="display:flex;justify-content:space-between;align-items:baseline;gap:12px"><span class="t-label">Size</span><span class="t-cap muted" id="cm"></span></div>
          <div class="pill-group" role="radiogroup" aria-label="Size">${D.sizes.map((s) => `<label class="pill"><input type="radio" name="size" value="${s.id}"${s.id === size ? " checked" : ""}><span>${s.label}</span></label>`).join("")}</div>
          <div style="display:flex;align-items:center;gap:24px;flex-wrap:wrap"><span class="t-price" id="price"></span>
            <div class="stepper" role="group" aria-label="Quantity"><button type="button" id="minus" aria-label="Fewer">−</button><output id="qty" aria-live="polite">1</output><button type="button" id="plus" aria-label="More">+</button></div></div>
          <div style="display:flex;gap:20px;align-items:center;flex-wrap:wrap">${tagBtn('id="add"', "Add to cart")}
            <button class="btn-link" data-wish="${p.slug}" aria-pressed="${wish.has(p.slug)}" style="border-color:var(--ink);color:var(--ink)">${wish.has(p.slug) ? "♥ Saved" : "♡ Save for later"}</button></div>
          <p class="t-cap muted">Only ${p.editions} made. When they're gone, they're gone.</p>
        </div>
        <ul class="perks"><li>300 GSM glossy sheets</li><li>4-5 days delivery</li><li>Tamper-proof packaging</li><li>Easy returns</li></ul>
        <div><p class="t-label" style="margin-bottom:12px">See it on your wall</p>
          <div class="pill-group">${walls.map(([n, c], i) => `<label class="pill"><input type="radio" name="wall" value="${c}"${i === 0 ? " checked" : ""}><span><i class="swatch" style="background:${c}"></i>${n}</span></label>`).join("")}</div></div>
        <div>
          <details class="acc" open><summary>The details</summary><div class="acc__body"><ul style="margin:0;padding-left:20px"><li>300 GSM glossy paper</li><li>Sizes: A4, A3 or A2. Frame not included</li><li>Limited to ${p.editions} prints per design</li></ul></div></details>
          <details class="acc"><summary>Shipping</summary><p class="acc__body">Free delivery above ${money(D.freeShippingAbove)}, otherwise ${money(D.shippingFee)}. Most orders reach you in 4-5 days, packed tamper-proof and rolled flat-safe.</p></details>
          <details class="acc"><summary>Returns</summary><p class="acc__body">Arrived damaged or wrong? Write to us within 7 days with a photo. <a class="brand" href="shipping-returns.html" style="text-decoration:underline">Read the full policy.</a></p></details>
        </div>
      </div>`;
    const main = $("#main"), img = $("#main-img");
    const showView = (i) => {
      view = i; const v = views[i]; img.classList.add("swap");
      setTimeout(() => { img.src = v.img; main.classList.toggle("is-framed", v.framed); img.classList.remove("swap"); }, 180);
      $$("#thumbs button").forEach((b, j) => b.setAttribute("aria-current", j === i));
    };
    $("#thumbs").addEventListener("click", (e) => { const b = e.target.closest("button"); if (b) showView(+b.dataset.v); });
    $$('input[name="wall"]').forEach((r) => r.addEventListener("change", () => { main.style.setProperty("--wall", r.value); showView(1); }));
    main.style.setProperty("--wall", walls[0][1]);
    const paint = () => { $("#price").textContent = money(sizeFor().price * qty); $("#cm").textContent = sizeFor().cm; $("#qty").textContent = qty; };
    $$('input[name="size"]').forEach((r) => r.addEventListener("change", () => { size = r.value; paint(); }));
    $("#minus").addEventListener("click", () => { qty = Math.max(1, qty - 1); paint(); });
    $("#plus").addEventListener("click", () => { qty = Math.min(10, qty + 1); paint(); });
    $("#add").addEventListener("click", () => { cart.add(lineFor(p, size, qty)); toast(`<span>${qty} × ${esc(p.title)} (${size}) added.</span><a href="cart.html">View cart</a>`); });
    paint();
    const rel = D.products.filter((x) => x.slug !== p.slug).slice(0, 3);
    $("#related").innerHTML = rel.map(productCard).join("");
  };

  pages.wishlist = function () {
    const list = wish.all().map(byProduct).filter(Boolean);
    $("#grid").innerHTML = list.length ? list.map(productCard).join("") :
      `<div class="empty" style="grid-column:1/-1"><img src="assets/croc-wordmark.png" alt=""><p class="t-head">Nothing saved. Very disciplined.</p><p>Tap the heart on anything that made you feel personally attacked.</p><a class="btn" href="shop.html">[ Browse the posters ]</a></div>`;
  };

  pages.cart = function () {
    const root = $("#cart");
    let first = true;
    const draw = () => {
      root.classList.toggle("first-draw", first); first = false;
      const items = cart.items();
      if (!items.length) {
        root.innerHTML = `<div class="empty"><img src="assets/croc-wordmark.png" alt=""><h2 class="t-display">Your cart is as empty as your wall.</h2><p class="t-sub">Let's fix both.</p><a class="btn" href="shop.html">[ Shop the drop ]</a></div>`;
        return;
      }
      const t = cart.totals();
      const pct = Math.min(100, Math.round((t.subtotal - t.discount) / D.freeShippingAbove * 100));
      root.innerHTML = `<div class="cart-layout">
        <section aria-label="Items in your cart">
          ${items.map((i) => `<div class="line">
            <a href="${i.slug === "gift-card" ? "gift-cards.html" : "product.html?p=" + i.slug}"><img src="${i.img}" alt=""></a>
            <div class="line__info"><a class="t-sub" href="${i.slug === "gift-card" ? "gift-cards.html" : "product.html?p=" + i.slug}">${esc(i.title)}</a><span class="t-cap muted">${i.slug === "gift-card" ? "Digital · by email" : "Size " + esc(i.size)}</span>
              <button class="link-quiet" data-rm="${esc(i.id)}" style="width:fit-content">Remove</button></div>
            <div class="line__end"><span class="t-price">${money(i.price * i.qty)}</span>
              <div class="stepper" role="group" aria-label="Quantity for ${esc(i.title)}"><button data-dec="${esc(i.id)}" aria-label="Fewer">−</button><output>${i.qty}</output><button data-inc="${esc(i.id)}" aria-label="More">+</button></div></div>
          </div>`).join("")}
          <a class="btn-link" href="shop.html" style="margin-top:24px">Keep browsing →</a>
        </section>
        <aside class="summary" aria-label="Order summary">
          <h2 class="t-head">Summary</h2>
          ${t.hasPhysical ? `<div><p class="t-cap" style="margin-bottom:8px">${t.away > 0 ? `You're <b>${money(t.away)}</b> away from free delivery.` : "Free delivery unlocked. The croc approves."}</p><div class="meter"><i style="width:${pct}%"></i></div></div>` : ""}
          <div class="summary__row"><span>Subtotal</span><span>${money(t.subtotal)}</span></div>
          ${t.discount ? `<div class="summary__row brand"><span>${D.coupon.code} (−${D.coupon.percent}%)</span><span>− ${money(t.discount)}</span></div>` : ""}
          <div class="summary__row"><span>Delivery</span><span>${t.hasPhysical ? (t.shipping ? money(t.shipping) : "Free") : "Not needed"}</span></div>
          <div class="summary__row summary__row--total t-price"><span>Total</span><span>${money(t.total)}</span></div>
          <form id="coupon" class="field"><label for="code">Promo code</label><div style="display:flex;gap:8px"><input class="input input--pill" id="code" placeholder="WELCOME10" value="${t.code ? esc(t.code) : ""}" autocomplete="off"><button class="btn btn--outline" type="submit">Apply</button></div><span class="err" id="code-err" role="alert"></span></form>
          <a class="btn btn--block" href="checkout.html">[ Checkout ]</a>
          <p class="t-cap muted" style="text-align:center">UPI &amp; Cash on Delivery accepted</p>
        </aside></div>`;
      $("#coupon").addEventListener("submit", (e) => {
        e.preventDefault();
        const v = $("#code").value.trim().toUpperCase();
        if (!v) { store.del("hsc_coupon"); draw(); return; }
        if (v === D.coupon.code) { store.set("hsc_coupon", v); draw(); } else $("#code-err").textContent = "That code doesn't exist. Nice try though.";
      });
    };
    root.addEventListener("click", (e) => {
      const g = (a) => e.target.closest(`[${a}]`)?.getAttribute(a);
      const find = (id) => cart.items().find((i) => i.id === id);
      if (g("data-rm")) { const row = e.target.closest(".line"); if (row) { row.classList.add("leaving"); setTimeout(() => cart.remove(g("data-rm")), 330); } else cart.remove(g("data-rm")); }
      if (g("data-inc")) cart.setQty(g("data-inc"), Math.min(10, find(g("data-inc")).qty + 1));
      if (g("data-dec")) cart.setQty(g("data-dec"), find(g("data-dec")).qty - 1);
    });
    document.addEventListener("cart:change", draw);
    draw();
  };

  pages.checkout = function () {
    const items = cart.items();
    if (!items.length) { location.replace("cart.html"); return; }
    const t = cart.totals();
    $("#sum").innerHTML = `
      ${items.map((i) => `<div class="mini"><img src="${i.img}" alt=""><div><p>${esc(i.title)}</p><p class="t-cap muted">${i.slug === "gift-card" ? "Digital" : esc(i.size)} × ${i.qty}</p></div><span class="t-cap">${money(i.price * i.qty)}</span></div>`).join("")}
      <div class="summary__row"><span>Subtotal</span><span>${money(t.subtotal)}</span></div>
      ${t.discount ? `<div class="summary__row brand"><span>${esc(t.code)}</span><span>− ${money(t.discount)}</span></div>` : ""}
      <div class="summary__row"><span>Delivery</span><span>${t.hasPhysical ? (t.shipping ? money(t.shipping) : "Free") : "Not needed"}</span></div>
      <div class="summary__row summary__row--total t-price"><span>Total</span><span>${money(t.total)}</span></div>`;
    const physical = t.hasPhysical;
    $("#ship-sec").hidden = !physical;
    const form = $("#checkout");
    const rules = {
      email: (v) => /^[^@\s]+@[^@\s]+\.[^@\s]+$/.test(v) || "Enter a valid email.",
      name: (v) => v.trim().length > 1 || "We need a name for the parcel.",
      phone: (v) => /^[6-9]\d{9}$/.test(v.replace(/\s/g, "")) || "Enter a 10-digit mobile number.",
      line1: (v) => v.trim().length > 4 || "Where should the croc deliver?",
      city: (v) => v.trim().length > 1 || "City, please.",
      state: (v) => v.trim().length > 1 || "State, please.",
      pin: (v) => /^\d{6}$/.test(v) || "Pin code is 6 digits."
    };
    form.addEventListener("submit", (e) => {
      e.preventDefault();
      let ok = true, first = null;
      Object.keys(rules).forEach((k) => {
        const el = form.elements[k]; if (!el || (!physical && ["line1", "city", "state", "pin"].includes(k))) return;
        const r = rules[k](el.value), err = $(`#err-${k}`);
        err.textContent = r === true ? "" : r; el.setAttribute("aria-invalid", r !== true);
        if (r !== true) { ok = false; first = first || el; }
      });
      if (!ok) { first.focus(); return; }
      const d = Object.fromEntries(new FormData(form));
      const order = { id: "HSC-" + Math.random().toString(36).slice(2, 8).toUpperCase(), placed: new Date().toISOString(), items, totals: t, payment: d.pay, email: d.email, name: d.name, address: physical ? { line1: d.line1, line2: d.line2, city: d.city, state: d.state, pin: d.pin } : null };
      store.set("hsc_last_order", order); store.del("hsc_coupon"); cart.clear();
      location.href = "order-confirmed.html";
    });
  };

  pages.confirmed = function () {
    const o = store.get("hsc_last_order", null);
    if (!o) { $("#done").innerHTML = `<div class="empty"><img src="assets/croc-wordmark.png" alt=""><h2 class="t-display">No order here.</h2><p>Maybe the croc ate it. Start fresh.</p><a class="btn" href="shop.html">[ Shop the drop ]</a></div>`; return; }
    const pay = { upi: "UPI", online: "Card / Netbanking", cod: "Cash on Delivery" }[o.payment] || "UPI";
    $("#oid").textContent = o.id; $("#oname").textContent = o.name.split(" ")[0]; $("#oemail").textContent = o.email;
    $("#osum").innerHTML = o.items.map((i) => `<div class="mini"><img src="${i.img}" alt=""><div><p>${esc(i.title)}</p><p class="t-cap muted">${i.slug === "gift-card" ? "Digital" : esc(i.size)} × ${i.qty}</p></div><span class="t-cap">${money(i.price * i.qty)}</span></div>`).join("") +
      `<div class="summary__row summary__row--total t-price"><span>Total (${pay})</span><span>${money(o.totals.total)}</span></div>`;
    $("#oaddr").innerHTML = o.address ? `${esc(o.name)}<br>${esc(o.address.line1)}${o.address.line2 ? ", " + esc(o.address.line2) : ""}<br>${esc(o.address.city)}, ${esc(o.address.state)} ${esc(o.address.pin)}` : "Digital order. Nothing to ship.";
  };

  pages.gift = function () {
    let amt = 1000;
    const amounts = [500, 1000, 2000, 5000];
    $("#amts").innerHTML = amounts.map((a) => `<label class="pill"><input type="radio" name="amt" value="${a}"${a === amt ? " checked" : ""}><span>${money(a)}</span></label>`).join("");
    const paint = () => { $("#gc-amt").textContent = money(amt); };
    $("#amts").addEventListener("change", (e) => { amt = +e.target.value; paint(); });
    $("#gift-form").addEventListener("submit", (e) => {
      e.preventDefault();
      const f = e.target; const em = f.elements.to;
      if (!em.checkValidity()) { em.reportValidity(); return; }
      cart.add({ id: `gift-card|${amt}|${em.value}`, slug: "gift-card", title: `Gift card for ${em.value}`, size: String(amt), price: amt, qty: 1, img: "assets/croc-wordmark.png" });
      toast(`<span>Gift card added.</span><a href="cart.html">View cart</a>`);
    });
    paint();
  };

  pages.contact = function () {
    const f = $("#contact-form");
    f.addEventListener("submit", (e) => {
      e.preventDefault();
      if (!f.checkValidity()) { f.reportValidity(); return; }
      f.innerHTML = `<div class="empty" style="padding:24px 0"><img src="assets/croc-wordmark.png" alt="" style="width:140px"><p class="t-head">Message received.</p><p>A human (or at least a very organised croc) will reply soon.</p></div>`;
    });
  };

  pages.faq = function () { $("#faqs").innerHTML = D.faqs.map((f, i) => faqItem(f, i === 0)).join(""); };

  /* ---------- boot ---------- */
  document.addEventListener("DOMContentLoaded", () => {
    mountChrome();
    initMotion();
    const fn = pages[document.body.dataset.page]; if (fn) fn();
    $$("[data-email]").forEach((a) => { a.href = "mailto:" + D.supportEmail; a.textContent = D.supportEmail; });
  });
})();
