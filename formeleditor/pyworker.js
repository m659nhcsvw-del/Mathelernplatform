// Rechenkern im Browser (iPad, iPhone, Mac ohne Installation): Python über Pyodide in einem Web-Worker.
// Stufe 1: Python + Formelsatz (sofort nutzbar) · Stufe 2: SymPy · Stufe 3: NumPy und SciPy (im Hintergrund)
"use strict";
const params = new URL(self.location.href).searchParams;
const PYODIDE = params.get("pyodide") || "https://cdn.jsdelivr.net/pyodide/v0.26.4/full/";
const QUELLEN = params.get("quellen") || "py/";
const DATEIEN = ["__init__.py", "sprache.py", "satz.py", "vorlagen.py", "rechnen.py", "webapi.py"];

let py = null, ruf = null;
const meldung = (stufe, text) => self.postMessage({ status: { stufe, text } });

async function kern() {
  meldung(0, "Python wird geladen …");
  importScripts(PYODIDE + "pyodide.js");
  py = await loadPyodide({ indexURL: PYODIDE });
  py.FS.mkdirTree("/home/pyodide/formeleditor");
  for (const d of DATEIEN) {
    const r = await fetch(QUELLEN + d, { cache: "no-cache" });
    if (!r.ok) throw new Error("Quelldatei fehlt: " + d);
    py.FS.writeFile("/home/pyodide/formeleditor/" + d, await r.text());
  }
  py.runPython("import sys\nif '/home/pyodide' not in sys.path: sys.path.insert(0, '/home/pyodide')\nfrom formeleditor.webapi import ruf_json");
  ruf = py.globals.get("ruf_json");
  meldung(1, "Formelsatz bereit · SymPy wird geladen …");
}
const stufe1 = kern();
const stufe2 = stufe1.then(async () => { await py.loadPackage(["sympy"]); meldung(2, "SymPy bereit · NumPy und SciPy werden geladen …"); });
const stufe3 = stufe2.then(async () => { await py.loadPackage(["numpy", "scipy"]); meldung(3, "bereit"); });
stufe3.catch(e => meldung(-1, "Rechenkern konnte nicht geladen werden: " + (e && e.message || e)));

const RECHNEN = new Set(["/api/berechne", "/api/info"]);

async function bearbeite(pfad, daten) {
  await stufe1;
  if (RECHNEN.has(pfad)) await stufe2;
  if (pfad === "/api/info") await stufe3.catch(() => {});
  let antwort = JSON.parse(ruf(pfad, JSON.stringify(daten || {})));
  if (pfad === "/api/berechne" && antwort && typeof antwort.fehler === "string" && /ModuleNotFoundError|No module named/.test(antwort.fehler)) {
    await stufe3;                                     // NumPy/SciPy werden noch geladen → danach erneut
    antwort = JSON.parse(ruf(pfad, JSON.stringify(daten || {})));
  }
  return antwort;
}

self.onmessage = async ev => {
  const { id, pfad, daten } = ev.data;
  try { self.postMessage({ id, antwort: await bearbeite(pfad, daten) }); }
  catch (e) { self.postMessage({ id, antwort: { fehler: "Rechenkern: " + (e && e.message || e) } }); }
};
