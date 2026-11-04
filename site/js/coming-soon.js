/* Coming soon page: depth parallax, card tilt, waiting-list form.
   No dependencies. All motion is skipped when the visitor prefers reduced motion. */
(() => {
  const reduce = matchMedia("(prefers-reduced-motion: reduce)").matches;
  const $ = (s, r = document) => r.querySelector(s);

  /* ---------- parallax + spotlight + card tilt ---------- */
  const layers = [...document.querySelectorAll("[data-depth]")].map((el) => ({ el, d: parseFloat(el.dataset.depth) }));
  const tilt = $("#tilt");
  let tx = 0, ty = 0, cx = 0, cy = 0, lastMove = -1e9, raf = 0;

  if (!reduce) {
    addEventListener("pointermove", (e) => {
      tx = (e.clientX / innerWidth) * 2 - 1;
      ty = (e.clientY / innerHeight) * 2 - 1;
      lastMove = performance.now();
    }, { passive: true });

    const frame = (now) => {
      // With no pointer (phones, idle desktop) the camera sways on its own so depth stays visible.
      if (now - lastMove > 2500) {
        const t = now / 1000;
        tx = Math.sin(t * 0.35) * 0.65;
        ty = Math.cos(t * 0.27) * 0.4;
      }
      cx += (tx - cx) * 0.06;
      cy += (ty - cy) * 0.06;
      for (const { el, d } of layers) el.style.translate = `${(cx * d).toFixed(2)}px ${(cy * d * 0.6).toFixed(2)}px`;
      tilt.style.transform = `rotateY(${(cx * 3.5).toFixed(2)}deg) rotateX(${(-cy * 2.5).toFixed(2)}deg)`;
      raf = requestAnimationFrame(frame);
    };
    const start = () => { if (!raf) raf = requestAnimationFrame(frame); };
    const stop = () => { cancelAnimationFrame(raf); raf = 0; };
    document.addEventListener("visibilitychange", () => (document.hidden ? stop() : start()));
    start();
  }

  /* ---------- waiting-list form ---------- */
  const form = $("#form"), field = $("#field"), input = $("#email"), msg = $("#email-msg");
  const btn = $("#submit"), card = $("#signup"), panels = $("#panels"), done = $("#done");
  const stamp = $("#stamp"), stampLabel = $("#stamp-label");
  const EMAIL = /^[^\s@]+@[^\s@]+\.[^\s@]{2,}$/;
  const KEY = "hsc_waitlist";

  const read = () => { try { return JSON.parse(localStorage.getItem(KEY)) || []; } catch { return []; } };
  const write = (list) => { try { localStorage.setItem(KEY, JSON.stringify(list)); } catch { /* private mode: still show success */ } };

  function setError(text) {
    msg.textContent = text;
    field.classList.add("is-error");
    input.setAttribute("aria-invalid", "true");
    field.classList.remove("is-shake");
    void field.offsetWidth; // restart the shake
    field.classList.add("is-shake");
    input.focus();
  }
  function clearError() {
    field.classList.remove("is-error", "is-shake");
    input.removeAttribute("aria-invalid");
  }
  input.addEventListener("input", clearError);

  async function save(email) {
    const list = read();
    const dupe = list.includes(email);
    const endpoint = window.HSC_WAITLIST_ENDPOINT;
    const minWait = new Promise((r) => setTimeout(r, reduce ? 0 : 650)); // lets the button state read
    if (endpoint) {
      const res = await fetch(endpoint, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ email, source: "coming-soon" }),
      });
      if (!res.ok) throw new Error("waitlist " + res.status);
    }
    if (!dupe) write([...list, email]);
    await minWait;
    return { dupe };
  }

  function slap(label) {
    stampLabel.textContent = label;
    if (reduce) return;
    stamp.classList.remove("is-slap");
    void stamp.offsetWidth;
    stamp.classList.add("is-slap");
  }

  function burst() {
    if (reduce) return;
    const box = $("#confetti");
    const r = btn.getBoundingClientRect();
    const ox = r.left + r.width / 2, oy = r.top + r.height / 2;
    const colors = ["#c8261e", "#4ca33b", "#f3cc32", "#2869b8", "#1c1a19", "#fff9ef"];
    for (let i = 0; i < 34; i++) {
      const p = document.createElement("i");
      p.style.background = colors[i % colors.length];
      if (i % 3 === 0) { p.style.borderRadius = "50%"; p.style.width = p.style.height = "9px"; }
      box.appendChild(p);
      const a = (-Math.PI / 2) + (Math.random() - 0.5) * Math.PI * 1.15;
      const v = 220 + Math.random() * 320;
      const dx = Math.cos(a) * v, dy = Math.sin(a) * v;
      const rot = (Math.random() - 0.5) * 900;
      p.animate([
        { transform: `translate(${ox}px, ${oy}px) rotate(0)`, opacity: 1 },
        { transform: `translate(${ox + dx * 0.6}px, ${oy + dy * 0.6}px) rotate(${rot * 0.6}deg)`, opacity: 1, offset: 0.45 },
        { transform: `translate(${ox + dx}px, ${oy + dy + 340}px) rotate(${rot}deg)`, opacity: 0 },
      ], { duration: 1300 + Math.random() * 600, easing: "cubic-bezier(.2,.6,.3,1)", fill: "forwards" })
        .onfinish = () => p.remove();
    }
  }

  function showDone(dupe) {
    if (dupe) {
      $("#done-title").textContent = "Already in.";
      $("#done-body").textContent = "That email is on the list already. We will email you when Drop 001 opens.";
      $(".chip", done).textContent = "Still on the list";
    }
    // Animate the card height between the two panels.
    const from = panels.offsetHeight;
    panels.style.height = from + "px";
    card.classList.add("is-done");
    done.removeAttribute("inert");
    done.setAttribute("aria-hidden", "false");
    form.setAttribute("inert", "");
    requestAnimationFrame(() => { panels.style.height = done.offsetHeight + "px"; });
    slap(dupe ? "On the list" : "Confirmed");
    burst();
    document.querySelectorAll(".float").forEach((f) => f.classList.add("is-jolt"));
    setTimeout(() => $("#done-title").focus({ preventScroll: true }), reduce ? 0 : 700);
  }

  form.addEventListener("submit", async (e) => {
    e.preventDefault();
    const email = input.value.trim().toLowerCase();
    if (form.elements.company.value) return showDone(false); // honeypot: pretend it worked
    if (!EMAIL.test(email)) return setError("That does not look like an email. Check it and try again.");
    clearError();
    const label = btn.textContent;
    btn.classList.add("is-loading");
    btn.textContent = "Saving…";
    try {
      const { dupe } = await save(email);
      showDone(dupe);
    } catch {
      btn.classList.remove("is-loading");
      btn.textContent = label;
      setError("Could not save that just now. Try again in a moment.");
    }
  });
})();
