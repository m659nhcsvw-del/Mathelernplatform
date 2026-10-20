"""Eingabesprache des Formeleditors: Text → Syntaxbaum (ohne Auswertung, ohne SymPy).

Schreibweise (wie im Funktionen-Explorer):
  * Dezimalkomma: 1,5   –   Argumente mit Semikolon trennen: integrate(x^2; x; 0; 1)
  * implizite Multiplikation: 2x, 3 sin(x), ab = a·b (bekannte Namen wie sin, pi, alpha bleiben ganz)
  * Potenz ^ oder **, Fakultät n!, Ableitungsstrich f'(x), Index x_1 oder x1, Betrag |x|, Wurzel √x
  * Vergleiche = < > <= >= != (auch ≤ ≥ ≠), Zuweisung a := 3 bzw. f(x) := x^2
  * [a; b; c] Vektor, [[1; 2]; [3; 4]] Matrix, "+" Text (z. B. Richtung beim Grenzwert), □ Platzhalter

Knoten (Tupel):
  ("zahl", "1,5")  ("name", "x_1")  ("platz",)  ("text", "+")
  ("add", a, b)  ("sub", a, b)  ("mul", a, b, implizit)  ("div", a, b, "/" | ":")
  ("neg", a)  ("pos", a)  ("pot", a, b)  ("fak", a)
  ("ruf", name, [args], striche)  ("strich", name, striche)   – f'(x) bzw. y'
  ("klammer", a)  ("betrag", a)  ("liste", [elemente])
  ("rel", [terme], [ops])  ("zuw", ziel, wert)
Nur für Ergebnisse (aus dem Rechenkern): ("menge", [elemente])  ("intervall", a, b, links_offen, rechts_offen)
  ("oder", [teile])  ("und", [teile])  ("ungefaehr", a)  ("bool", True/False)  ("textzeile", "…")
"""
import re
import unicodedata

PLATZHALTER = "□"


class SprachFehler(ValueError):
    def __init__(self, meldung, pos=None):
        super().__init__(meldung)
        self.pos = pos


# ---------------------------------------------------------------- bekannte Namen
GRIECHISCH = ["alpha", "beta", "gamma", "delta", "epsilon", "zeta", "eta", "theta", "iota", "kappa", "lambda",
              "mu", "nu", "xi", "omicron", "pi", "rho", "sigma", "tau", "upsilon", "phi", "chi", "psi", "omega"]
GRIECHISCH_GROSS = ["Gamma", "Delta", "Theta", "Lambda", "Xi", "Pi", "Sigma", "Upsilon", "Phi", "Psi", "Omega"]
UNICODE_GRIECHISCH = {"α": "alpha", "β": "beta", "γ": "gamma", "δ": "delta", "ε": "epsilon", "ζ": "zeta", "η": "eta",
                      "θ": "theta", "ι": "iota", "κ": "kappa", "λ": "lambda", "μ": "mu", "ν": "nu", "ξ": "xi",
                      "ο": "omicron", "π": "pi", "ρ": "rho", "σ": "sigma", "τ": "tau", "υ": "upsilon", "φ": "phi",
                      "ϕ": "phi", "χ": "chi", "ψ": "psi", "ω": "omega", "Γ": "Gamma", "Δ": "Delta", "Θ": "Theta",
                      "Λ": "Lambda", "Ξ": "Xi", "Π": "Pi", "Σ": "Sigma", "Υ": "Upsilon", "Φ": "Phi", "Ψ": "Psi",
                      "Ω": "Omega"}
KONSTANTEN = {"pi", "e", "i", "oo", "inf"}
FUNKTIONSBUCHSTABEN = {"f", "g", "h", "u", "v", "y", "F", "G", "H"}

# mathematische Funktionen: Name → (kleinste, größte Argumentzahl)
FUNKTIONEN = {
    "sin": (1, 1), "cos": (1, 1), "tan": (1, 1), "cot": (1, 1),
    "arcsin": (1, 1), "arccos": (1, 1), "arctan": (1, 1), "asin": (1, 1), "acos": (1, 1), "atan": (1, 1),
    "sinh": (1, 1), "cosh": (1, 1), "tanh": (1, 1),
    "exp": (1, 1), "ln": (1, 1), "log": (1, 2), "lg": (1, 1), "sqrt": (1, 1), "root": (2, 2),
    "abs": (1, 1), "floor": (1, 1), "ceil": (1, 1), "sign": (1, 1), "sgn": (1, 1),
    "factorial": (1, 1), "binomial": (2, 2), "binom": (2, 2), "gamma": (1, 1),
    "max": (1, 99), "min": (1, 99), "gcd": (2, 99), "lcm": (2, 99), "mod": (2, 2),
    "re": (1, 1), "im": (1, 1), "conjugate": (1, 1),
}
# Befehle (Auswertung im Rechenkern): Name → (kleinste, größte Argumentzahl)
BEFEHLE = {
    # Analysis
    "diff": (1, 3), "integrate": (1, 4), "limit": (3, 4), "summation": (4, 4), "product": (4, 4),
    "series": (2, 4), "dsolve": (1, 3), "tangente": (3, 3),
    # Algebra
    "simplify": (1, 1), "expand": (1, 1), "factor": (1, 1), "apart": (1, 2), "together": (1, 1),
    "cancel": (1, 1), "trigsimp": (1, 1), "nsimplify": (1, 1), "N": (1, 2), "solve": (1, 2), "csolve": (1, 2),
    "subs": (3, 3), "Eq": (2, 2),
    # Lineare Algebra
    "Matrix": (1, 1), "det": (1, 1), "inv": (1, 1), "transpose": (1, 1), "rank": (1, 1), "trace": (1, 1),
    "eigenvals": (1, 1), "eigenvects": (1, 1), "rref": (1, 1), "dot": (2, 2), "cross": (2, 2), "norm": (1, 1),
    "linsolve": (2, 2), "eye": (1, 1), "zeros": (1, 2),
    # Numerik (NumPy / SciPy / mpmath)
    "nsolve": (3, 3), "fsolve": (3, 3), "brentq": (4, 4), "quad": (4, 4), "nroots": (1, 1),
    "minimize": (3, 3), "maximize": (3, 3),
    # Stochastik (scipy.stats)
    "binompdf": (3, 3), "binomcdf": (3, 4), "normpdf": (3, 3), "normcdf": (4, 4), "invnorm": (3, 3),
    "poissonpdf": (2, 2), "poissoncdf": (2, 2), "mean": (1, 1), "median": (1, 1), "var": (1, 1), "std": (1, 1),
    "erwartungswert": (2, 2),
}
ALLE_FUNKTIONSNAMEN = set(FUNKTIONEN) | set(BEFEHLE)


def bekannte_namen(benutzer=()):
    return ALLE_FUNKTIONSNAMEN | KONSTANTEN | set(GRIECHISCH) | set(GRIECHISCH_GROSS) | set(benutzer)


# ---------------------------------------------------------------- Zerlegung in Zeichen
_OPS = [":=", "<=", ">=", "!=", "**", "<>", "≤", "≥", "≠", "+", "-", "−", "*", "·", "×", "/", ":", "^", "!", "=", "<", ">",
        "(", ")", "[", "]", "{", "}", ";", "|", "√", "∞", "'", "_", PLATZHALTER, "÷", "≈"]
_ERSATZ = {"−": "-", "×": "*", "·": "*", "÷": "/", "≤": "<=", "≥": ">=", "≠": "!=", "<>": "!=", "**": "^"}


def _tokens(text):
    t = unicodedata.normalize("NFC", text)
    i, aus = 0, []
    while i < len(t):
        c = t[i]
        if c.isspace():
            i += 1
            continue
        m = re.match(r"\d+(?:[.,]\d+)?|[.,]\d+", t[i:])
        if m:
            aus.append(("zahl", m.group(0).replace(".", ","), i))
            i += len(m.group(0))
            continue
        if c == '"':
            j = t.find('"', i + 1)
            if j < 0:
                raise SprachFehler("Anführungszeichen wird nicht geschlossen", i)
            aus.append(("text", t[i + 1:j], i))
            i = j + 1
            continue
        if c.isalpha() and c not in UNICODE_GRIECHISCH:
            m = re.match(r"[^\W\d_]+\d*", t[i:])
            aus.append(("wort", m.group(0), i))
            i += len(m.group(0))
            continue
        if c in UNICODE_GRIECHISCH:
            aus.append(("wort", UNICODE_GRIECHISCH[c], i))
            i += 1
            continue
        for op in _OPS:
            if t.startswith(op, i):
                aus.append(("op", _ERSATZ.get(op, op), i))
                i += len(op)
                break
        else:
            if c == ",":
                raise SprachFehler("Komma nur als Dezimalkomma (z. B. 1,5) – Argumente mit Semikolon trennen", i)
            raise SprachFehler(f"Unbekanntes Zeichen „{c}“", i)
    aus.append(("ende", "", len(t)))
    return aus


# ---------------------------------------------------------------- Parser
class _Parser:
    def __init__(self, text, variablen=(), funktionen=()):
        self.t = _tokens(text)
        self.p = 0
        self.variablen, self.funktionen = set(variablen), set(funktionen)
        self.bekannt = bekannte_namen(self.variablen | self.funktionen)

    def sieh(self, k=0):
        return self.t[self.p + k]

    def ist(self, *ops):
        a = self.sieh()
        return a[0] == "op" and a[1] in ops

    def nimm(self):
        a = self.t[self.p]
        self.p += 1
        return a

    def erwarte(self, op):
        if not self.ist(op):
            a = self.sieh()
            raise SprachFehler(f"„{op}“ erwartet" + (f", gefunden „{a[1]}“" if a[1] else " am Ende"), a[2])
        self.nimm()

    def fehler(self, msg):
        raise SprachFehler(msg, self.sieh()[2])

    # ganze Eingabe
    def eingabe(self):
        if self.sieh()[0] == "ende":
            return ("platz",)
        a = self.relation()
        if self.ist(":="):
            self.nimm()
            if a[0] not in ("name", "ruf"):
                self.fehler("Links von := muss ein Name oder eine Funktion wie f(x) stehen")
            a = ("zuw", a, self.relation())
        if self.sieh()[0] != "ende":
            a2 = self.sieh()
            self.fehler(f"Unerwartet: „{a2[1]}“")
        return a

    def relation(self):
        terme, ops = [self.summe()], []
        while self.ist("=", "<", ">", "<=", ">=", "!="):
            ops.append(self.nimm()[1])
            terme.append(self.summe())
        return terme[0] if not ops else ("rel", terme, ops)

    def summe(self):
        a = self.produkt()
        while self.ist("+", "-"):
            op = self.nimm()[1]
            b = self.produkt()
            a = ("add" if op == "+" else "sub", a, b)
        return a

    def _startet_faktor(self):
        a = self.sieh()
        return a[0] in ("zahl", "wort", "text") or (a[0] == "op" and a[1] in ("(", "[", "√", "∞", PLATZHALTER))

    def produkt(self):
        a = self.vorzeichen()
        while True:
            if self.ist("*"):
                self.nimm()
                a = ("mul", a, self.vorzeichen(), False)
            elif self.ist("/", ":"):
                op = self.nimm()[1]
                a = ("div", a, self.vorzeichen(), op)
            elif self._startet_faktor():
                a = ("mul", a, self.potenz(), True)
            else:
                return a

    def vorzeichen(self):
        if self.ist("-"):
            self.nimm()
            return ("neg", self.vorzeichen())
        if self.ist("+"):
            self.nimm()
            return ("pos", self.vorzeichen())
        return self.potenz()

    def potenz(self):
        a = self.postfix()
        if self.ist("^"):
            self.nimm()
            return ("pot", a, self.vorzeichen())
        return a

    def postfix(self):
        a = self.primaer()
        while self.ist("!"):
            self.nimm()
            a = ("fak", a)
        return a

    def argumente(self):
        self.erwarte("(")
        args = []
        if not self.ist(")"):
            args.append(self.relation_oder_zuw())
            while self.ist(";"):
                self.nimm()
                args.append(self.relation_oder_zuw())
        self.erwarte(")")
        return args

    def relation_oder_zuw(self):
        return self.relation()

    def name_mit_index(self, wort):
        # x_1, x_{12}, a_n
        if self.ist("_"):
            self.nimm()
            a = self.sieh()
            if a[0] in ("zahl", "wort"):
                self.nimm()
                return wort + "_" + a[1].replace(",", "")
            if self.ist("{"):
                self.nimm()
                teile = []
                while not self.ist("}"):
                    b = self.nimm()
                    if b[0] == "ende":
                        self.fehler("„}“ erwartet")
                    teile.append(b[1])
                self.nimm()
                return wort + "_" + "".join(teile)
            self.fehler("Nach _ muss ein Index folgen")
        return wort

    def zerlege_wort(self, wort):
        """Teilt unbekannte Buchstabenfolgen in einzelne Variablen (ab → a·b); bekannte Namen bleiben ganz."""
        m = re.match(r"([^\W\d_]+)(\d*)$", wort)
        buchst, ziffern = m.group(1), m.group(2)
        if wort in self.bekannt:
            return [wort]
        if buchst in self.bekannt:
            return [buchst + ("_" + ziffern if ziffern else "")]
        teile, i = [], 0
        namen = sorted(self.bekannt, key=len, reverse=True)
        while i < len(buchst):
            for n in namen:
                if len(n) > 1 and buchst.startswith(n, i):
                    teile.append(n)
                    i += len(n)
                    break
            else:
                teile.append(buchst[i])
                i += 1
        if ziffern:
            teile[-1] += "_" + ziffern                  # x1 → x_1
        return teile

    def primaer(self):
        a = self.sieh()
        if a[0] == "zahl":
            self.nimm()
            return ("zahl", a[1])
        if a[0] == "text":
            self.nimm()
            return ("text", a[1])
        if a[0] == "wort":
            self.nimm()
            teile = self.zerlege_wort(a[1])
            knoten = [("name", n) for n in teile[:-1]]
            letzter = self.name_mit_index(teile[-1])
            striche = 0
            while self.ist("'"):
                self.nimm()
                striche += 1
            if self.ist("(") and self._ist_aufruf(letzter, striche):
                args = self.argumente()
                self._pruefe_anzahl(letzter, len(args), a[2])
                letzt = ("ruf", letzter, args, striche)
            elif striche:
                letzt = ("strich", letzter, striche)
            else:
                if (letzter in ALLE_FUNKTIONSNAMEN and letzter not in KONSTANTEN and letzter not in GRIECHISCH
                        and len(letzter) > 1 and letzter not in self.variablen):
                    self.fehler(f"Nach {letzter} fehlt die Klammer, z. B. {letzter}(x)")
                letzt = ("name", letzter)
            knoten.append(letzt)
            erg = knoten[0]
            for k in knoten[1:]:
                erg = ("mul", erg, k, True)
            return erg
        if self.ist("("):
            self.nimm()
            inhalt = self.relation()
            self.erwarte(")")
            return ("klammer", inhalt)
        if self.ist("["):
            self.nimm()
            el = []
            if not self.ist("]"):
                el.append(self.relation())
                while self.ist(";"):
                    self.nimm()
                    el.append(self.relation())
            self.erwarte("]")
            return ("liste", el)
        if self.ist("|"):
            self.nimm()
            inhalt = self.summe()
            self.erwarte("|")
            return ("betrag", inhalt)
        if self.ist("√"):
            self.nimm()
            return ("ruf", "sqrt", [self.postfix()], 0)
        if self.ist("∞"):
            self.nimm()
            return ("name", "oo")
        if self.ist(PLATZHALTER):
            self.nimm()
            return ("platz",)
        if a[0] == "ende":
            self.fehler("Ausdruck unvollständig")
        self.fehler(f"Unerwartet: „{a[1]}“")

    def _ist_aufruf(self, name, striche):
        """name(…) ist ein Funktionsaufruf bei bekannten Funktionen/Befehlen, Benutzerfunktionen, f'(x) und den üblichen
        Funktionsbuchstaben f, g, h, u, v, y, F, G, H (auch mit Index); sonst Multiplikation, z. B. x(x − 2)."""
        if striche or name in self.funktionen:
            return True
        if name in self.variablen or name in KONSTANTEN:
            return False
        if name in ALLE_FUNKTIONSNAMEN:
            return True
        return name.split("_")[0] in FUNKTIONSBUCHSTABEN

    def _pruefe_anzahl(self, name, n, pos):
        grenzen = FUNKTIONEN.get(name) or BEFEHLE.get(name)
        if grenzen and not grenzen[0] <= n <= grenzen[1]:
            soll = str(grenzen[0]) if grenzen[0] == grenzen[1] else f"{grenzen[0]} bis {grenzen[1]}"
            raise SprachFehler(f"{name} erwartet {soll} Argument(e), gefunden {n}", pos)


def parse(text, variablen=(), funktionen=()):
    """Text → Syntaxbaum. variablen/funktionen: vom Benutzer mit := definierte Namen (beeinflusst ab → a·b
    und ob name(…) als Funktionsaufruf gilt)."""
    return _Parser(text, variablen, funktionen).eingabe()


def platzhalter_in(knoten):
    if not isinstance(knoten, tuple):
        return False
    if knoten[0] == "platz":
        return True
    for k in knoten[1:]:
        if isinstance(k, tuple) and platzhalter_in(k):
            return True
        if isinstance(k, list) and any(platzhalter_in(e) for e in k):
            return True
    return False


def definierte_namen(knoten):
    """Bei einer Zuweisung: ("variable", name) oder ("funktion", name, [parameter]); sonst None."""
    if knoten[0] != "zuw":
        return None
    ziel = knoten[1]
    if ziel[0] == "name":
        return ("variable", ziel[1])
    return ("funktion", ziel[1], [a[1] for a in ziel[2] if a[0] == "name"])
