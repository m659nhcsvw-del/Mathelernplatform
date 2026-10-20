// Gemeinsame Hilfen für Formeleditor und Funktionen-Explorer: Ziehen in andere Apps und Zurückziehen.
// PNG-Textblock (tEXt) schreiben/lesen, Bild-Fingerabdruck (Differenz-Hash), Abwurfzone für Dateien, Bilder und Links.
"use strict";
window.Ziehen = (() => {
  const CRC = (() => { const t = new Uint32Array(256); for (let n = 0; n < 256; n++) { let c = n; for (let k = 0; k < 8; k++) c = c & 1 ? 0xedb88320 ^ (c >>> 1) : c >>> 1; t[n] = c >>> 0; } return t; })();
  const crc32 = b => { let c = 0xffffffff; for (const x of b) c = CRC[(c ^ x) & 255] ^ (c >>> 8); return (c ^ 0xffffffff) >>> 0; };
  const typ4 = (a, p) => String.fromCharCode(a[p], a[p + 1], a[p + 2], a[p + 3]);

  // Text (ASCII) als tEXt-Block vor dem ersten IDAT einsetzen
  async function pngMitText(blob, schluessel, text) {
    const a = new Uint8Array(await blob.arrayBuffer());
    const inhalt = new TextEncoder().encode(schluessel + "\0" + text);
    const typ = new TextEncoder().encode("tEXt");
    const block = new Uint8Array(12 + inhalt.length), dv = new DataView(block.buffer);
    dv.setUint32(0, inhalt.length); block.set(typ, 4); block.set(inhalt, 8);
    const fuerCrc = new Uint8Array(4 + inhalt.length); fuerCrc.set(typ, 0); fuerCrc.set(inhalt, 4);
    dv.setUint32(8 + inhalt.length, crc32(fuerCrc));
    let p = 8;
    while (p + 8 <= a.length) {
      const len = new DataView(a.buffer, p).getUint32(0);
      if (typ4(a, p + 4) === "IDAT") break;
      p += 12 + len;
    }
    return new Blob([a.subarray(0, p), block, a.subarray(p)], { type: "image/png" });
  }
  function pngText(buf) {
    const a = new Uint8Array(buf), aus = {};
    if (a.length < 8 || a[0] !== 0x89 || a[1] !== 0x50) return aus;
    let p = 8;
    while (p + 8 <= a.length) {
      const len = new DataView(a.buffer, a.byteOffset + p).getUint32(0), t = typ4(a, p + 4);
      if (t === "tEXt") {
        const d = a.subarray(p + 8, p + 8 + len), i = d.indexOf(0);
        if (i > 0) aus[new TextDecoder("latin1").decode(d.subarray(0, i))] = new TextDecoder("latin1").decode(d.subarray(i + 1));
      }
      if (t === "IEND") break;
      p += 12 + len;
    }
    return aus;
  }

  // Fingerabdruck: 48×32-Graustufen-Miniatur auf Weiß (als Hex-Text) + Seitenverhältnis
  function ladeBild(quelle) {
    return new Promise((ok, fehler) => {
      const img = new Image();
      img.onload = () => ok(img);
      img.onerror = () => fehler(new Error("Bild nicht lesbar"));
      img.src = quelle;
    });
  }
  function blobZuDataUrl(b) { return new Promise(ok => { const r = new FileReader(); r.onload = () => ok(r.result); r.readAsDataURL(b); }); }
  async function fingerabdruck(quelle) {
    const img = quelle instanceof Blob ? await ladeBild(await blobZuDataUrl(quelle)) : (typeof quelle === "string" ? await ladeBild(quelle) : quelle);
    // schrittweise halbieren (Mittelung statt Stichprobe) → unabhängig von der Auflösung
    let w = img.naturalWidth || img.width, h = img.naturalHeight || img.height;
    let q = document.createElement("canvas"); q.width = w; q.height = h;
    let qg = q.getContext("2d"); qg.fillStyle = "#fff"; qg.fillRect(0, 0, w, h); qg.drawImage(img, 0, 0, w, h);
    while (w > 96 || h > 64) {
      const nw = Math.max(48, Math.round(w / 2)), nh = Math.max(32, Math.round(h / 2));
      const n = document.createElement("canvas"); n.width = nw; n.height = nh;
      const ng = n.getContext("2d"); ng.imageSmoothingQuality = "high"; ng.drawImage(q, 0, 0, nw, nh);
      q = n; w = nw; h = nh;
    }
    const c = document.createElement("canvas"); c.width = 48; c.height = 32;
    const g = c.getContext("2d", { willReadFrequently: true });
    g.imageSmoothingQuality = "high";
    g.drawImage(q, 0, 0, 48, 32);
    const d = g.getImageData(0, 0, 48, 32).data;
    let hex = "";
    for (let i = 0; i < d.length; i += 4) hex += Math.round(0.299 * d[i] + 0.587 * d[i + 1] + 0.114 * d[i + 2]).toString(16).padStart(2, "0");
    return { hex, seiten: img.naturalWidth / Math.max(1, img.naturalHeight) };
  }
  function abstand(a, b) {               // 1 − Korrelation der 48×32-Miniaturen (0 = gleich, 1 = unabhängig)
    if (!a || !b || a.hex.length !== b.hex.length) return Infinity;
    if (Math.abs(Math.log((a.seiten || 1) / (b.seiten || 1))) > 0.08) return Infinity;   // anderes Seitenverhältnis
    const n = a.hex.length / 2, x = new Float64Array(n), y = new Float64Array(n);
    let mx = 0, my = 0;
    for (let i = 0; i < n; i++) { x[i] = parseInt(a.hex.substr(2 * i, 2), 16); y[i] = parseInt(b.hex.substr(2 * i, 2), 16); mx += x[i]; my += y[i]; }
    mx /= n; my /= n;
    let sxy = 0, sxx = 0, syy = 0;
    for (let i = 0; i < n; i++) { const u = x[i] - mx, v = y[i] - my; sxy += u * v; sxx += u * u; syy += v * v; }
    if (sxx < 1e-9 || syy < 1e-9) return sxx < 1e-9 && syy < 1e-9 ? 0 : 1;
    return 1 - sxy / Math.sqrt(sxx * syy);
  }
  // bestes Verlaufs-Element zum Fingerabdruck: höchstens grenze entfernt und deutlich näher als das zweitbeste
  function suche(fp, eintraege, grenze = 0.02, vorsprung = 0.03) {
    const d = eintraege.map(e => [abstand(fp, e.fp), e]).filter(x => x[0] < Infinity).sort((a, b) => a[0] - b[0]);
    if (!d.length || d[0][0] > grenze) return null;
    if (d.length > 1 && d[1][0] - d[0][0] < vorsprung) return null;
    return d[0][1];
  }
  // Abwurfzone: ganze Seite. behandle({datei, text, url}) → true, wenn erkannt
  function abwurfzone(behandle, hinweis) {
    let eigen = false, tiefe = 0;
    document.addEventListener("dragstart", () => { eigen = true; });
    document.addEventListener("dragend", () => { eigen = false; });
    const zeige = an => { if (hinweis) hinweis.hidden = !an; };
    document.addEventListener("dragenter", e => { if (eigen) return; tiefe++; e.preventDefault(); zeige(true); });
    document.addEventListener("dragleave", () => { if (--tiefe <= 0) { tiefe = 0; zeige(false); } });
    document.addEventListener("dragover", e => { if (eigen) return; e.preventDefault(); if (e.dataTransfer) e.dataTransfer.dropEffect = "copy"; });
    document.addEventListener("drop", async e => {
      tiefe = 0; zeige(false);
      if (eigen) return;
      const ziel = e.target;
      if (ziel && (ziel.tagName === "TEXTAREA" || (ziel.tagName === "INPUT" && ziel.type === "text"))) {
        // Text in ein Eingabefeld: nur übernehmen, wenn es ein Explorer-/Editor-Link ist
        const t = e.dataTransfer.getData("text/uri-list") || e.dataTransfer.getData("text/plain");
        if (!/[#&](zustand|quelle)=|%FE1:/.test(t || "")) return;
      }
      e.preventDefault();
      const dt = e.dataTransfer, daten = { datei: null, text: "", url: "" };
      if (dt.files && dt.files.length) daten.datei = dt.files[0];
      daten.url = (dt.getData("text/uri-list") || "").split(/\r?\n/).find(z => z && !z.startsWith("#")) || "";
      daten.text = dt.getData("text/plain") || "";
      if (!daten.datei && dt.items) {
        for (const it of dt.items) if (it.kind === "file") { daten.datei = it.getAsFile(); break; }
      }
      try { await behandle(daten); } catch (err) { console.warn("Abwurf:", err); }
    });
  }
  return { pngMitText, pngText, fingerabdruck, abstand, suche, abwurfzone, blobZuDataUrl, ladeBild };
})();
