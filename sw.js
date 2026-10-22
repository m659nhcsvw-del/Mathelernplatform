// Offline-Speicher für Formeleditor und Funktionen-Explorer (eigene Dateien + Pyodide aus dem Netz)
const VERSION = "1.3.3";
const EIGEN = "fe-eigen-" + VERSION, FREMD = "fe-pyodide-0.26.4";
const DATEIEN = ["./", "index.html", "explorer/icon-180.png", "explorer/icon-192.png", "explorer/icon-512.png", "explorer/index.html", "explorer/manifest.webmanifest", "formeleditor/formelbild.js", "formeleditor/icon-180.png", "formeleditor/icon-192.png", "formeleditor/icon-512.png", "formeleditor/index.html", "formeleditor/manifest.webmanifest", "formeleditor/pyworker.js", "formeleditor/ziehen.js", "formeleditor/py/__init__.py", "formeleditor/py/rechnen.py", "formeleditor/py/satz.py", "formeleditor/py/sprache.py", "formeleditor/py/vorlagen.py", "formeleditor/py/webapi.py", "formeleditor/katex/LICENSE", "formeleditor/katex/katex.min.css", "formeleditor/katex/katex.min.js", "formeleditor/katex/fonts/KaTeX_AMS-Regular.woff2", "formeleditor/katex/fonts/KaTeX_Caligraphic-Bold.woff2", "formeleditor/katex/fonts/KaTeX_Caligraphic-Regular.woff2", "formeleditor/katex/fonts/KaTeX_Fraktur-Bold.woff2", "formeleditor/katex/fonts/KaTeX_Fraktur-Regular.woff2", "formeleditor/katex/fonts/KaTeX_Main-Bold.woff2", "formeleditor/katex/fonts/KaTeX_Main-BoldItalic.woff2", "formeleditor/katex/fonts/KaTeX_Main-Italic.woff2", "formeleditor/katex/fonts/KaTeX_Main-Regular.woff2", "formeleditor/katex/fonts/KaTeX_Math-BoldItalic.woff2", "formeleditor/katex/fonts/KaTeX_Math-Italic.woff2", "formeleditor/katex/fonts/KaTeX_SansSerif-Bold.woff2", "formeleditor/katex/fonts/KaTeX_SansSerif-Italic.woff2", "formeleditor/katex/fonts/KaTeX_SansSerif-Regular.woff2", "formeleditor/katex/fonts/KaTeX_Script-Regular.woff2", "formeleditor/katex/fonts/KaTeX_Size1-Regular.woff2", "formeleditor/katex/fonts/KaTeX_Size2-Regular.woff2", "formeleditor/katex/fonts/KaTeX_Size3-Regular.woff2", "formeleditor/katex/fonts/KaTeX_Size4-Regular.woff2", "formeleditor/katex/fonts/KaTeX_Typewriter-Regular.woff2", "formeleditor/", "explorer/"];
self.addEventListener("install", e => {
  e.waitUntil(caches.open(EIGEN).then(c => c.addAll(DATEIEN)).then(() => self.skipWaiting()));
});
self.addEventListener("activate", e => {
  e.waitUntil(caches.keys().then(ks => Promise.all(ks.filter(k => k !== EIGEN && k !== FREMD).map(k => caches.delete(k))))
    .then(() => self.clients.claim()));
});
self.addEventListener("fetch", e => {
  const url = new URL(e.request.url);
  if (e.request.method !== "GET") return;
  if (url.origin === self.location.origin) {
    // eigene Dateien: erst Netz (damit Neuerungen ankommen), sonst Speicher
    e.respondWith(fetch(e.request).then(r => {
      if (r.ok) { const k = r.clone(); caches.open(EIGEN).then(c => c.put(e.request, k)); }
      return r;
    }).catch(() => caches.match(e.request, { ignoreSearch: true })));
    return;
  }
  if (url.href.startsWith("https://cdn.jsdelivr.net/pyodide/v0.26.4/full/") || url.hostname === "fonts.gstatic.com" || url.hostname === "fonts.googleapis.com") {
    // Pyodide und Schriften ändern sich nie (feste Version) → Speicher zuerst
    e.respondWith(caches.open(FREMD).then(c => c.match(e.request).then(t => t || fetch(e.request).then(r => {
      if (r.ok || r.type === "opaque") c.put(e.request, r.clone());
      return r;
    }))));
  }
});
