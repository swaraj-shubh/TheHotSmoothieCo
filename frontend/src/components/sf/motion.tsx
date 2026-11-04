const REVEAL =
  ".card,.coll,.usp,.step,.review,.acc,.pick,.gift,.pass,.summary,.check-sec,.mini,.order-steps > *,.split > *,.wall-section > *,.vinyl-split > *,.statement > *,.page-head > *,.pdp__gallery,.pdp__info > *,.prose > *,.empty > *,.footer__col,.t-display,.drop-bar > *,.gift-card-preview,.err-page > *"

// The site's initMotion(): scroll reveal, header shadow, back-to-top. It works on the DOM so it also
// covers content that streams in or arrives on client navigation.
const run = `
document.documentElement.classList.add("js");
var REVEAL=${JSON.stringify(REVEAL)};
var io=new IntersectionObserver(function(es){es.forEach(function(e){if(e.isIntersecting){e.target.classList.add("in");io.unobserve(e.target)}})},{threshold:.12,rootMargin:"0px 0px -6% 0px"});
function tag(root){
  var hits=[].slice.call(root.querySelectorAll(REVEAL));
  if(root.matches(REVEAL))hits.unshift(root);
  hits.filter(function(el){return !el.classList.contains("reveal")&&!el.closest(".hero,.header,.topbar,.toast-region,.line")}).forEach(function(el){
    var sibs=el.parentElement?[].slice.call(el.parentElement.children).filter(function(c){return c.matches(REVEAL)}):[];
    el.style.setProperty("--d",Math.min(sibs.indexOf(el),5)*90+"ms");
    el.classList.add("reveal");
    io.observe(el);
  });
}
tag(document.body);
new MutationObserver(function(ms){ms.forEach(function(m){m.addedNodes.forEach(function(n){if(n.nodeType===1)tag(n)})})}).observe(document.body,{childList:true,subtree:true});
addEventListener("load",function(){
  var up=document.createElement("button");
  up.className="page-top";up.setAttribute("aria-label","Back to top");up.textContent="↑";
  up.addEventListener("click",function(){scrollTo({top:0,behavior:"smooth"})});
  document.body.append(up);
  function onScroll(){
    var h=document.getElementById("hdr");
    if(h)h.classList.toggle("scrolled",scrollY>8&&!h.classList.contains("header--overlay"));
    up.classList.toggle("show",scrollY>900);
  }
  addEventListener("scroll",onScroll,{passive:true});onScroll();
});
`

/** Runs before hydration, as on the site, so first-screen content rises in rather than popping.
 *  In development it waits for hydration: React's dev checks would flag the added classes. */
export function Motion() {
  const code =
    process.env.NODE_ENV === "production"
      ? `(function(){${run}})()`
      : `addEventListener("load",function(){setTimeout(function(){${run.replace('addEventListener("load",function(){', "(function(){").replace(/\}\);\n$/, "})();\n")}},800)})`
  return <script dangerouslySetInnerHTML={{ __html: code }} />
}
