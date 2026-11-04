/* Catalogue. Names, images and the Rs. 499 A4 price come from the Figma home page.
   PLACEHOLDER (not in the design, confirm before launch): A3/A2 prices, edition sizes,
   collection assignments for Soul Punk and Pani Puri Wala, all product copy, support email,
   shipping fee, return window, coupon code. */
window.HSC = {
  freeShippingAbove: 999,
  shippingFee: 79,
  coupon: { code: "WELCOME10", percent: 10 },
  supportEmail: "hello@thehotsmoothieco.com",
  dropDate: "2026-11-05T18:00:00+05:30",

  sizes: [
    { id: "A4", label: "A4", cm: "21 × 29.7 cm", price: 499 },
    { id: "A3", label: "A3", cm: "29.7 × 42 cm", price: 799 },
    { id: "A2", label: "A2", cm: "42 × 59.4 cm", price: 1199 }
  ],

  collections: [
    {
      slug: "pretentious-fanboy",
      name: "Pretentious Fanboy",
      img: "assets/collection-pretentious-fanboy.png",
      tagline: "For people who say “actually” before every sentence.",
      story: "You know the lap times, the tyre strategy and who should have won in 2021. Nobody asked. The wall will listen anyway."
    },
    {
      slug: "nerd-fiction",
      name: "Nerd Fiction",
      img: "assets/collection-nerd-fiction.png",
      tagline: "Lore-heavy. Opinion-heavy. Slightly defensive.",
      story: "A fictional world has lived rent-free in your head for years. Time it paid something. Hang the proof."
    },
    {
      slug: "baddie-era",
      name: "Baddie Era",
      img: "assets/collection-baddie-era.png",
      tagline: "Main character energy, framed.",
      story: "Soft launch, hard stare. These are for walls that have never once apologised."
    }
  ],

  products: [
    {
      slug: "red-bull-1", title: "Red Bull #1", collection: "pretentious-fanboy",
      img: "assets/poster-red-bull-1.png", room: "assets/collection-pretentious-fanboy.png",
      editions: 250, tag: "Bestseller",
      blurb: "Lights out and away you go, straight onto your wall.",
      story: "A pit-lane-fast poster for the friend who calls tyre degradation “a vibe”. Loud colour, 300 GSM gloss, zero podium humility.",
      hangIf: "you have ever paused a race to explain DRS."
    },
    {
      slug: "baddie-profile-1", title: "Baddie Profile #1", collection: "baddie-era",
      img: "assets/poster-baddie-profile-1.png", room: "assets/collection-baddie-era.png",
      editions: 250, tag: "Bestseller",
      blurb: "Lotus-pink, unbothered, and not here to explain herself.",
      story: "Collage-loud and unapologetic. It looks great in daylight and even better when someone asks who she is.",
      hangIf: "your last profile photo started a debate."
    },
    {
      slug: "demon-slayer-1", title: "Demon Slayer #1", collection: "nerd-fiction",
      img: "assets/poster-demon-slayer-1.png", room: "assets/collection-nerd-fiction.png",
      editions: 250, tag: "Bestseller",
      blurb: "The first light, in vintage ink and sun-red.",
      story: "A field-notes style print for people who have a favourite breathing technique and are ready to discuss it.",
      hangIf: "you have a ranking of every Hashira and it is non-negotiable."
    },
    {
      slug: "soul-punk", title: "Soul Punk", collection: "nerd-fiction",
      img: "assets/poster-soul-punk.png", room: null,
      editions: 150, tag: "New drop",
      blurb: "Blue skin. Gold hoops. Zero chill.",
      story: "A riot of risograph red and a mohawk that has never heard the word “tone it down”. It will make your living room louder.",
      hangIf: "your playlist has more screaming than lyrics."
    },
    {
      slug: "badmash-pani-puri-wala", title: "Badmash Pani Puri Wala", collection: "baddie-era",
      img: "assets/poster-pani-puri-wala.png", room: null,
      editions: 150, tag: "Croc’s pick",
      blurb: "Street-food royalty, now in poster form.",
      story: "The croc has spoken. He serves the spiciest pani and the sassiest side-eye on the lane. Extra imli, no apologies.",
      hangIf: "you judge a city by its golgappa."
    }
  ],

  faqs: [
    { q: "How long does delivery take?", a: "Most orders reach you in 4-5 days. Remote pin codes can take a little longer, and we will tell you before your poster leaves, not after." },
    { q: "What paper do you print on?", a: "300 GSM glossy sheets, so the colours stay as loud as the idea." },
    { q: "Can I return a poster?", a: "Yes. If it arrives damaged, wrong or somehow unloved, write to us within 7 days with a photo and we will sort it. Details are on the Shipping & Returns page." },
    { q: "Do posters come framed?", a: "Not yet. They arrive flat in tamper-proof packaging, ready for the frame of your choice." },
    { q: "When is the next drop?", a: "Drop 002 lands soon. Join the Smoothie Club and you get first dibs before everyone else." },
    { q: "Will this poster fix my personality?", a: "No, but it will distract people from it." },
    { q: "Can I hang it upside down?", a: "Legally, yes. Emotionally, we’d have questions." },
    { q: "Is the croc single?", a: "He’s married to the brand. It’s complicated." },
    { q: "My mom hates it. Can I return it?", a: "Returns are easy. Your mom’s taste is not our department." },
    { q: "Do I need good taste to buy one?", a: "Absolutely not. It’s actively discouraged." }
  ]
};
