"""Reine Rechen-Schnittstelle des Formeleditors – ohne Server, ohne Dateizugriff.

Wird vom lokalen Server (Mac-Programm) und von Pyodide (Browser, iPad) gleichermaßen benutzt:
    ruf(pfad, daten) → Antwort-dict   bzw.   ruf_json(pfad, json_text) → json_text
"""
import json
import sys

from .sprache import parse, SprachFehler, definierte_namen
from . import satz
from .vorlagen import katalog

IWORK_PRAEFIX = "%FE1:"


def satz_antwort(text, variablen=(), funktionen=()):
    try:
        k = parse(text, variablen, funktionen)
    except SprachFehler as e:
        return {"fehler": str(e), "pos": e.pos}
    d = definierte_namen(k)
    return {"latex": satz.latex(k), "starmath": satz.starmath(k), "definiert": d}


def info():
    aus = {"python": sys.version.split()[0], "umgebung": "pyodide" if sys.platform == "emscripten" else "lokal"}
    for modul in ("sympy", "numpy", "scipy"):
        try:
            aus[modul] = __import__(modul).__version__
        except Exception:
            aus[modul] = None
    return aus


def berechne_zeilen(zeilen, index):
    try:
        from .rechnen import Arbeitsblatt, RechenFehler
    except ImportError as e:
        return {"fehler": "SymPy ist nicht installiert – bitte das Installationsskript ausführen (" + str(e) + ")"}
    blatt = Arbeitsblatt()
    for i, z in enumerate(zeilen[:index]):           # Festlegungen der Zeilen davor übernehmen
        if ":=" in z:
            try:
                blatt.berechne(z)
            except Exception as e:
                return {"fehler": f"Zeile {i + 1} (Festlegung) ist fehlerhaft: {e}"}
    try:
        return blatt.berechne(zeilen[index])
    except SprachFehler as e:
        return {"fehler": str(e), "pos": e.pos}
    except RechenFehler as e:
        return {"fehler": str(e)}
    except NotImplementedError as e:
        return {"fehler": "Das kann SymPy nicht lösen" + (f": {e}" if str(e) else "")}
    except Exception as e:
        return {"fehler": f"Nicht berechenbar ({type(e).__name__}: {e})"}


# ---------------------------------------------------------------- iWork (Pages, Keynote, Numbers)
_IWORK_ERSATZ = [
    (r"\coloneqq", r"\mathrel{:=}"),    # mathtools-Befehl, im iWork-Gleichungseditor nicht sicher vorhanden
]


def iwork_latex(latex, quelle=None):
    """LaTeX für „Einfügen → Gleichung“ in Pages/Keynote/Numbers.
    Die Quelle des Editors reist als LaTeX-Kommentar in der letzten Zeile mit (unsichtbar im Satz)."""
    import urllib.parse
    for alt, neu in _IWORK_ERSATZ:
        latex = latex.replace(alt, neu)
    latex = " ".join(latex.split())
    if quelle is not None:
        kodiert = urllib.parse.quote(json.dumps(quelle, ensure_ascii=False, separators=(",", ":")), safe="")
        latex += "\n" + IWORK_PRAEFIX + kodiert
    return latex


def iwork_quelle(text):
    """Holt die Editor-Quelle aus einem aus iWork kopierten Gleichungs-LaTeX (oder None)."""
    import urllib.parse
    for zeile in reversed(text.splitlines()):
        zeile = zeile.strip()
        if zeile.startswith(IWORK_PRAEFIX):
            try:
                return json.loads(urllib.parse.unquote(zeile[len(IWORK_PRAEFIX):]))
            except ValueError:
                return None
    return None


def ruf(pfad, daten=None):
    daten = daten or {}
    if pfad == "/api/vorlagen":
        return katalog()
    if pfad == "/api/info":
        return info()
    if pfad == "/api/ping":
        return {"ok": True}
    if pfad == "/api/satz":
        return satz_antwort(daten.get("text", ""), daten.get("variablen", []), daten.get("funktionen", []))
    if pfad == "/api/satz_liste":
        return [satz_antwort(t) for t in daten.get("texte", [])]
    if pfad == "/api/berechne":
        return berechne_zeilen(daten.get("zeilen", []), int(daten.get("index", 0)))
    if pfad == "/api/iwork_latex":
        return {"latex": iwork_latex(daten.get("latex", ""), daten.get("quelle"))}
    if pfad == "/api/iwork_quelle":
        return {"quelle": iwork_quelle(daten.get("text", ""))}
    return None


def ruf_json(pfad, json_text="{}"):
    """Einstieg für Pyodide: JSON hinein, JSON hinaus."""
    antwort = ruf(pfad, json.loads(json_text or "{}"))
    if antwort is None:
        antwort = {"fehler": "Im Browser nicht verfügbar: " + pfad}
    return json.dumps(antwort, ensure_ascii=False)
