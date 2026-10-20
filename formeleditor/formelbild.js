// Formel als Bild: setzt LaTeX mit KaTeX unsichtbar und überträgt Glyphen, Linien und SVG-Teile auf eine Leinwand.
// (Kein SVG-foreignObject – das würde in Safari die Leinwand sperren.) Ergebnis: PNG mit durchsichtigem Hintergrund.
"use strict";
window.Formelbild = (() => {
  const GROESSE = 26;        // CSS-Pixel der Grundschrift
  const RAND = 6;

  function svgBild(svg, farbe) {
    const kopie = svg.cloneNode(true);
    kopie.setAttribute("xmlns", "http://www.w3.org/2000/svg");
    const r = svg.getBoundingClientRect();
    kopie.setAttribute("width", r.width); kopie.setAttribute("height", r.height);
    kopie.setAttribute("style", "fill:" + farbe + ";stroke:none");
    kopie.querySelectorAll("*").forEach(el => { if (!el.getAttribute("fill")) el.setAttribute("fill", farbe); });
    const url = "data:image/svg+xml;charset=utf-8," + encodeURIComponent(new XMLSerializer().serializeToString(kopie));
    return new Promise(ok => { const img = new Image(); img.onload = () => ok(img); img.onerror = () => ok(null); img.src = url; });
  }

  function clipVon(start, wurzel) {        // Schnitt der Rechtecke von start und seinen Vorfahren mit overflow ≠ visible
    let r = null;
    for (let p = start; p && p !== wurzel; p = p.parentElement) {
      const cs = getComputedStyle(p);
      if (cs.overflow !== "visible" || cs.overflowX !== "visible") {
        const q = p.getBoundingClientRect();
        r = r ? { l: Math.max(r.l, q.left), t: Math.max(r.t, q.top), r: Math.min(r.r, q.right), b: Math.min(r.b, q.bottom) }
              : { l: q.left, t: q.top, r: q.right, b: q.bottom };
      }
    }
    return r;
  }

  async function zeichne(tex, { skala = 3, farbe = "#000000", groesse = GROESSE } = {}) {
    const box = document.createElement("div");
    box.style.cssText = `position:fixed;left:-10000px;top:0;font-size:${groesse}px;color:${farbe};background:transparent;white-space:nowrap;padding:0;margin:0;line-height:normal`;
    document.body.appendChild(box);
    try {
      katex.render(tex, box, { throwOnError: false, displayMode: true, strict: "ignore", output: "html" });
      const kd = box.querySelector(".katex-display"); if (kd) kd.style.margin = "0";
      const wurzel = box.querySelector(".katex-html") || box;
      if (document.fonts) {
        const schriften = new Set();
        wurzel.querySelectorAll("*").forEach(el => { const cs = getComputedStyle(el); schriften.add(`${cs.fontStyle} ${cs.fontWeight} ${cs.fontSize} ${cs.fontFamily}`); });
        await Promise.all([...schriften].map(f => document.fonts.load(f).catch(() => null)));
        await document.fonts.ready;
      }
      // Grenzen aus allen sichtbaren Teilen
      const katexEl = box.querySelector(".katex") || box;
      const g = katexEl.getBoundingClientRect();
      let L = g.left, T = g.top, R = g.right, B = g.bottom;
      const teile = [];
      // Glyphen: jeder Textknoten mit Grundlinie über eine Messmarke
      const lauf = document.createTreeWalker(wurzel, NodeFilter.SHOW_TEXT);
      const texte = [];
      for (let n = lauf.nextNode(); n; n = lauf.nextNode()) if (n.nodeValue.trim()) texte.push(n);
      for (const n of texte) {
        const el = n.parentElement, cs = getComputedStyle(el);
        if (cs.visibility === "hidden" || cs.display === "none") continue;
        const marke = document.createElement("span");
        marke.style.cssText = "display:inline-block;width:0;height:0;vertical-align:baseline;padding:0;margin:0;border:0";
        el.insertBefore(marke, n);
        const grund = marke.getBoundingClientRect().bottom;
        const rg = document.createRange(); rg.selectNodeContents(n);
        const rr = rg.getBoundingClientRect();
        el.removeChild(marke);
        teile.push({ art: "text", text: n.nodeValue, x: rr.left, y: grund,
                     font: `${cs.fontStyle} ${cs.fontWeight} ${cs.fontSize} ${cs.fontFamily}`, farbe: cs.color, clip: clipVon(el, wurzel) });
        L = Math.min(L, rr.left); R = Math.max(R, rr.right); T = Math.min(T, rr.top); B = Math.max(B, rr.bottom);
      }
      // Linien (Bruchstriche, Überstriche, \rule) aus Rahmen und Hintergründen
      for (const el of wurzel.querySelectorAll("*")) {
        if (el.closest("svg")) continue;
        const cs = getComputedStyle(el), r = el.getBoundingClientRect();
        if (r.width === 0 && r.height === 0) continue;
        const seiten = [["Top", r.left, r.top, r.width, null], ["Bottom", r.left, null, r.width, null], ["Left", r.left, r.top, null, r.height], ["Right", null, r.top, null, r.height]];
        for (const [s, x, y, w, h] of seiten) {
          const breite = parseFloat(cs[`border${s}Width`]) || 0;
          if (breite <= 0 || cs[`border${s}Style`] === "none" || cs[`border${s}Style`] === "hidden") continue;
          teile.push({ art: "rechteck", farbe: cs[`border${s}Color`], x: x === null ? r.right - breite : x, y: y === null ? r.bottom - breite : y,
                       w: w === null ? breite : w, h: h === null ? breite : h, clip: clipVon(el.parentElement, wurzel) });
        }
        const bg = cs.backgroundColor;
        if (bg && bg !== "transparent" && !/rgba\(\s*0,\s*0,\s*0,\s*0\s*\)/.test(bg)) teile.push({ art: "rechteck", farbe: bg, x: r.left, y: r.top, w: r.width, h: r.height, clip: clipVon(el.parentElement, wurzel) });
      }
      // SVG-Teile (Wurzelzeichen, große Klammern, Pfeile)
      for (const svg of wurzel.querySelectorAll("svg")) {
        const r = svg.getBoundingClientRect(), cs = getComputedStyle(svg);
        const bild = await svgBild(svg, cs.color || farbe);
        if (bild) teile.push({ art: "bild", bild, x: r.left, y: r.top, w: r.width, h: r.height, clip: clipVon(svg.parentElement, wurzel) });
      }
      L -= RAND; T -= RAND; R += RAND; B += RAND;
      const c = document.createElement("canvas");
      c.width = Math.ceil((R - L) * skala); c.height = Math.ceil((B - T) * skala);
      const ctx = c.getContext("2d");
      ctx.scale(skala, skala); ctx.translate(-L, -T);
      ctx.textBaseline = "alphabetic"; ctx.textAlign = "left";
      for (const t of teile) {
        ctx.save();
        if (t.clip) { ctx.beginPath(); ctx.rect(t.clip.l, t.clip.t, t.clip.r - t.clip.l, t.clip.b - t.clip.t); ctx.clip(); }
        if (t.art === "text") { ctx.font = t.font; ctx.fillStyle = t.farbe; ctx.fillText(t.text, t.x, t.y); }
        else if (t.art === "rechteck") { ctx.fillStyle = t.farbe; ctx.fillRect(t.x, t.y, t.w, t.h); }
        else ctx.drawImage(t.bild, t.x, t.y, t.w, t.h);
        ctx.restore();
      }
      return await new Promise((ok, fehler) => c.toBlob(b => b ? ok(b) : fehler(new Error("PNG nicht erzeugbar")), "image/png"));
    } finally { box.remove(); }
  }
  return { zeichne };
})();
