"""Formelsatz: Syntaxbaum → LaTeX (Anzeige mit KaTeX) und → StarMath (LibreOffice-Formelobjekt).

Der Satz zeigt die Eingabe so, wie sie geschrieben wurde (keine Auswertung); Befehle wie integrate oder limit
erscheinen in der üblichen mathematischen Schreibweise. Ergebnisse aus dem Rechenkern werden ebenfalls als
Syntaxbaum übergeben und mit denselben Regeln gesetzt.
"""
from .sprache import GRIECHISCH, GRIECHISCH_GROSS

# Rangfolge für Klammern
R_REL, R_ADD, R_MUL, R_NEG, R_POT, R_ATOM = 0, 1, 2, 3, 4, 5

KONST_NAMEN = {"pi", "e", "i", "oo", "inf"}


def _rang(k):
    t = k[0]
    if t in ("rel", "zuw", "oder", "und"):
        return R_REL
    if t in ("add", "sub"):
        return R_ADD
    if t == "mul" or (t == "div" and k[3] == ":"):
        return R_MUL
    if t == "div":
        return R_ATOM                                  # Bruchstrich gruppiert selbst
    if t in ("neg", "pos"):
        return R_NEG
    if t == "pot":
        return R_POT
    if t == "zahl" and k[1].startswith("-"):
        return R_NEG
    return R_ATOM


def _beginnt_mit_zahl(k):
    t = k[0]
    if t == "zahl":
        return True
    if t in ("mul", "pot", "fak"):
        return _beginnt_mit_zahl(k[1])
    if t == "div" and k[3] == ":":
        return _beginnt_mit_zahl(k[1])
    return False


def _beginnt_mit_minus(k):
    if k[0] == "neg" or (k[0] == "zahl" and k[1].startswith("-")):
        return True
    if k[0] in ("mul", "div") and k[0] != "div" or (k[0] == "div" and k[3] == ":"):
        return _beginnt_mit_minus(k[1])
    return False


class _Setzer:
    """Gemeinsame Regeln; die Unterklassen liefern die Bausteine der Zielsprache."""

    def setze(self, k):
        return getattr(self, "k_" + k[0])(k)

    def teil(self, k, mindest):
        s = self.setze(k)
        return self.klammer(s) if _rang(k) < mindest else s

    # ---- Grundknoten
    def k_platz(self, k):
        return self.platz()

    def k_zahl(self, k):
        return self.zahl(k[1])

    def k_text(self, k):
        return self.text(k[1])

    def k_textzeile(self, k):
        return self.text(k[1])

    def k_bool(self, k):
        return self.text("wahr" if k[1] else "falsch")

    def k_name(self, k):
        return self.name(k[1])

    def k_klammer(self, k):
        return self.klammer(self.setze(k[1]))

    def k_betrag(self, k):
        return self.betrag(self.setze(k[1]))

    def k_add(self, k):
        b = k[2]
        rechts = self.teil(b, R_ADD) if not _beginnt_mit_minus(b) else self.klammer(self.setze(b))
        return self.setze_links_summe(k[1]) + self.op_plus() + rechts

    def k_sub(self, k):
        b = k[2]
        rechts = self.teil(b, R_MUL) if not _beginnt_mit_minus(b) else self.klammer(self.setze(b))
        return self.setze_links_summe(k[1]) + self.op_minus() + rechts

    def setze_links_summe(self, a):
        return self.teil(a, R_ADD)

    def k_mul(self, k):
        a, b, implizit = k[1], k[2], k[3]
        links = self.teil(a, R_MUL)
        rechts = self.teil(b, R_POT) if _beginnt_mit_minus(b) else self.teil(b, R_MUL)
        if _beginnt_mit_minus(b):
            rechts = self.klammer(self.setze(b))
        # implizit nur, wenn rechts nicht mit einer Zahl beginnt (sonst 2·3 statt 23)
        if implizit and not _beginnt_mit_zahl(b):
            return self.juxta(links, rechts, b)
        return links + self.op_mal() + rechts

    def k_div(self, k):
        if k[3] == ":":
            return self.teil(k[1], R_MUL) + self.op_geteilt() + self.teil(k[2], R_POT)
        return self.bruch(self.ohne_klammer(k[1]), self.ohne_klammer(k[2]))

    def ohne_klammer(self, k):
        return self.setze(k[1] if k[0] == "klammer" else k)

    def k_neg(self, k):
        return self.op_vorzeichen_minus() + self.teil(k[1], R_MUL if k[1][0] != "neg" else R_ATOM)

    def k_pos(self, k):
        return "+" + self.teil(k[1], R_MUL)

    def k_pot(self, k):
        basis, exp = k[1], k[2]
        if basis[0] == "name" and basis[1] == "e":
            return self.potenz(self.konst_e(), self.ohne_klammer(exp))
        if basis[0] == "ruf" and basis[1] in self.FUNKTIONSNAMEN_LISTE and len(basis[2]) == 1 and not basis[3]:
            # sin(x)^2 → sin²(x)
            return self.funktion_hoch(basis[1], self.ohne_klammer(exp), self.setze(basis[2][0]))
        b = self.setze(basis)
        if _rang(basis) < R_ATOM or basis[0] in ("fak", "div") or (basis[0] == "zahl" and basis[1].startswith("-")):
            b = self.klammer(b)
        return self.potenz(b, self.ohne_klammer(exp))

    def k_fak(self, k):
        return self.teil(k[1], R_ATOM) + "!"

    def k_rel(self, k):
        aus = self.setze(k[1][0])
        for op, t in zip(k[2], k[1][1:]):
            aus += self.relation(op) + self.setze(t)
        return aus

    def k_zuw(self, k):
        return self.setze(k[1]) + self.zuweisung() + self.setze(k[2])

    def k_strich(self, k):
        return self.name(k[1]) + self.striche(k[2])

    def k_liste(self, k):
        el = k[1]
        if el and all(e[0] == "liste" for e in el):
            return self.matrix([[self.setze(x) for x in zeile[1]] for zeile in el])
        return self.matrix([[self.setze(x)] for x in el])

    def k_menge(self, k):
        return self.menge([self.setze(e) for e in k[1]])

    def k_intervall(self, k):
        return self.intervall(self.setze(k[1]), self.setze(k[2]), k[3], k[4])

    def k_oder(self, k):
        return self.verknuepfe([self.setze(e) for e in k[1]], self.op_oder())

    def k_und(self, k):
        return self.verknuepfe([self.setze(e) for e in k[1]], self.op_und())

    def k_ungefaehr(self, k):
        return self.setze(k[1])

    def k_folgt(self, k):
        return self.setze(k[1]) + self.op_folgt() + self.setze(k[2])

    def k_tupel(self, k):
        return self.klammer(self.liste_trenner([self.setze(e) for e in k[1]]))

    def k_mengenname(self, k):
        return self.mengenname(k[1])

    def k_vereinigung(self, k):
        return self.verknuepfe([self.setze(e) for e in k[1]], self.op_vereinigt())

    def k_ohne(self, k):
        return self.setze(k[1]) + self.op_ohne() + self.setze(k[2])

    def k_folge(self, k):
        return self.liste_trenner([self.setze(e) for e in k[1]]) if k[1] else self.menge([])

    def k_folge_paar(self, k):
        return self.setze(k[1]) + self.op_doppelpunkt() + self.setze(k[2])

    def k_mit_text(self, k):
        return self.setze(k[1]) + self.text(" " + k[2])

    def k_roh(self, k):
        return self.roh(k[1], k[2])

    # ---- Funktionen und Befehle
    def k_ruf(self, k):
        name, args, striche = k[1], k[2], k[3]
        A = args
        S = [self.setze(a) for a in args]
        if striche:
            return self.name(name) + self.striche(striche) + self.klammer(self.liste_trenner(S))
        m = getattr(self, "f_" + name, None)
        if m:
            erg = m(A, S)
            if erg is not None:
                return erg
        if name in self.FUNKTIONSNAMEN_LISTE:
            return self.std_funktion(name, self.liste_trenner(S))
        if name in self.BEFEHLSNAMEN:
            return self.operatorname(self.BEFEHLSNAMEN[name]) + self.klammer(self.liste_trenner(S))
        return self.name(name) + self.klammer(self.liste_trenner(S))

    FUNKTIONSNAMEN_LISTE = ("sin", "cos", "tan", "cot", "arcsin", "arccos", "arctan", "sinh", "cosh", "tanh", "ln", "lg",
                            "log", "max", "min", "exp")
    # Befehle ohne eigene Schreibweise: Anzeige als Operatorname (deutsche Bezeichnungen, wo im Unterricht üblich)
    BEFEHLSNAMEN = {"simplify": "vereinfache", "expand": "ausmultiplizieren", "factor": "faktorisiere",
                    "apart": "partialbruch", "together": "hauptnenner", "cancel": "kürze", "trigsimp": "trigvereinfache",
                    "nsimplify": "exakt", "solve": "löse", "csolve": "löse", "dsolve": "DGL",
                    "rank": "rang", "trace": "spur", "eigenvals": "eigenwerte", "eigenvects": "eigenvektoren",
                    "rref": "stufenform", "linsolve": "LGS", "eye": "E", "zeros": "0",
                    "nsolve": "nlöse", "fsolve": "nlöse", "brentq": "nullstelle", "nroots": "nullstellen",
                    "minimize": "minimum", "maximize": "maximum", "mean": "mittelwert", "median": "median",
                    "var": "varianz", "std": "standardabw", "subs": "einsetzen", "Matrix": "Matrix",
                    "gcd": "ggT", "lcm": "kgV", "mod": "mod", "sign": "sgn", "sgn": "sgn", "re": "Re", "im": "Im",
                    "series": "taylor", "tangente": "tangente", "erwartungswert": "E", "N": "numerisch",
                    "Eq": "gleichung"}

    def f_csolve(self, A, S):
        return self.operatorname("löse") + self.index_menge("C") + self.klammer(self.liste_trenner(S))

    def f_sqrt(self, A, S):
        return self.wurzel(self.ohne_klammer(A[0]))

    def f_root(self, A, S):
        return self.nwurzel(self.ohne_klammer(A[1]), self.ohne_klammer(A[0]))

    def f_abs(self, A, S):
        return self.betrag(self.ohne_klammer(A[0]))

    def f_exp(self, A, S):
        return self.potenz(self.konst_e(), self.ohne_klammer(A[0]))

    def f_log(self, A, S):
        if len(A) == 2:
            return self.log_basis(self.setze(A[1]), self.ohne_klammer(A[0]), A[0])
        return None

    def f_lg(self, A, S):
        return self.log_basis(self.zahl("10"), self.ohne_klammer(A[0]), A[0])

    def f_asin(self, A, S):
        return self.std_funktion("arcsin", S[0])

    def f_acos(self, A, S):
        return self.std_funktion("arccos", S[0])

    def f_atan(self, A, S):
        return self.std_funktion("arctan", S[0])

    def f_factorial(self, A, S):
        return self.teil(A[0], R_ATOM) + "!"

    def f_binomial(self, A, S):
        return self.binom(S[0], S[1])

    f_binom = f_binomial

    def f_floor(self, A, S):
        return self.abrunden(self.ohne_klammer(A[0]))

    def f_ceil(self, A, S):
        return self.aufrunden(self.ohne_klammer(A[0]))

    def f_gamma(self, A, S):
        return self.name("Gamma") + self.klammer(S[0])

    def f_conjugate(self, A, S):
        return self.konjugiert(self.setze(A[0]))

    # Analysis
    def f_diff(self, A, S):
        f = A[0]
        n = A[2] if len(A) > 2 else None
        var = S[1] if len(A) > 1 else self.name("x")
        return self.ableitung(var, self.setze(n) if n else None, self.setze(f), f)

    def f_integrate(self, A, S):
        var = S[1] if len(A) > 1 else self.name("x")
        a = S[2] if len(A) > 2 else None
        b = S[3] if len(A) > 3 else None
        return self.integral(self.teil(A[0], R_MUL), var, a, b)

    def f_quad(self, A, S):
        return self.integral(self.teil(A[0], R_MUL), S[1], S[2], S[3])

    def f_limit(self, A, S):
        richtung = None
        if len(A) > 3 and A[3][0] == "text":
            richtung = A[3][1]
        return self.grenzwert(S[1], S[2], richtung, self.teil(A[0], R_ADD))

    def f_summation(self, A, S):
        return self.summe(S[1], S[2], S[3], self.teil(A[0], R_MUL))

    def f_product(self, A, S):
        return self.produkt(S[1], S[2], S[3], self.teil(A[0], R_MUL))

    # Lineare Algebra
    def f_det(self, A, S):
        m = A[0]
        if m[0] == "liste" and m[1] and all(e[0] == "liste" for e in m[1]):
            return self.determinante([[self.setze(x) for x in z[1]] for z in m[1]])
        return self.std_funktion("det", self.ohne_klammer(A[0]))

    def f_inv(self, A, S):
        return self.potenz(self.teil(A[0], R_ATOM), self.zahl("-1"))

    def f_transpose(self, A, S):
        return self.transponiert(self.teil(A[0], R_ATOM))

    def f_dot(self, A, S):
        return self.teil(A[0], R_MUL) + self.op_mal() + self.teil(A[1], R_MUL)

    def f_cross(self, A, S):
        return self.teil(A[0], R_MUL) + self.op_kreuz() + self.teil(A[1], R_MUL)

    def f_norm(self, A, S):
        return self.norm(self.ohne_klammer(A[0]))

    # Stochastik (Schulschreibweise)
    def f_binompdf(self, A, S):
        return self.index_funktion("B", [S[0], S[1]], [S[2]])

    def f_binomcdf(self, A, S):
        if len(A) == 4:
            return self.index_funktion("F", [S[0], S[1]], [S[2], S[3]])
        return self.index_funktion("F", [S[0], S[1]], [S[2]])

    def f_normpdf(self, A, S):
        return self.index_funktion("phi", [S[1], S[2]], [S[0]])

    def f_normcdf(self, A, S):
        return self.index_funktion("Phi", [S[2], S[3]], [S[0], S[1]])

    def f_invnorm(self, A, S):
        return self.potenz(self.index_name("Phi", [S[1], S[2]]), self.zahl("-1")) + self.klammer(S[0])

    def f_poissonpdf(self, A, S):
        return self.index_funktion("P", [S[0]], [S[1]])

    def f_poissoncdf(self, A, S):
        return self.index_funktion("F", [S[0]], [S[1]])


# ===================================================================== LaTeX (KaTeX)
class LatexSetzer(_Setzer):
    def platz(self):
        return r"\square "

    def zahl(self, s):
        neg = s.startswith("-")
        s = s.lstrip("-").replace(",", "{,}")
        if "e" in s:                                    # 1,2e-7 → 1,2·10^{−7}
            m, e = s.split("e")
            s = m + r"\cdot 10^{" + str(int(e)) + "}"
        return ("-" if neg else "") + s

    def text(self, s):
        return r"\text{" + s.replace("\\", "").replace("{", "").replace("}", "") + "}"

    def name(self, n):
        basis, _, index = n.partition("_")
        if basis == "pi":
            b = r"\pi "
        elif basis == "e":
            b = r"\mathrm{e}"
        elif basis == "i" and not index:
            b = r"\mathrm{i}"
        elif basis in ("oo", "inf"):
            b = r"\infty "
        elif basis in GRIECHISCH:
            b = "\\" + ("varepsilon" if basis == "epsilon" else "varphi" if basis == "phi" else basis) + " "
        elif basis in GRIECHISCH_GROSS:
            b = "\\" + basis + " "
        elif len(basis) == 1:
            b = basis
        else:
            b = r"\mathit{" + basis + "}"
        if index:
            b += "_{" + (self.name(index) if not index.isdigit() and len(index) > 1 and index in GRIECHISCH else index) + "}"
        return b

    def konst_e(self):
        return r"\mathrm{e}"

    HOHE = ("\\frac", "\\int", "\\sum", "\\prod", "\\begin", "\\sqrt", "\\lim", "\\binom", "\\left")

    def klammer(self, s):
        if any(h in s for h in self.HOHE):
            return r"\left(" + s + r"\right)"
        return "(" + s + ")"

    def betrag(self, s):
        return r"\left|" + s + r"\right|"

    def norm(self, s):
        return r"\left\|" + s + r"\right\|"

    def abrunden(self, s):
        return r"\left\lfloor " + s + r"\right\rfloor "

    def aufrunden(self, s):
        return r"\left\lceil " + s + r"\right\rceil "

    def op_plus(self):
        return "+"

    def op_minus(self):
        return "-"

    def op_vorzeichen_minus(self):
        return "-"

    def op_mal(self):
        return r"\cdot "

    def op_kreuz(self):
        return r"\times "

    def op_geteilt(self):
        return ":"

    def op_oder(self):
        return r"\;\vee\; "

    def op_und(self):
        return r"\;\wedge\; "

    def juxta(self, a, b, knoten_b):
        if knoten_b[0] in ("name", "ruf", "pot") and a and a[-1].isalpha() and (b[:1].isalpha()):
            return a + r"\," + b
        return a + " " + b

    def bruch(self, a, b):
        return r"\frac{" + a + "}{" + b + "}"

    def potenz(self, b, e):
        return "{" + b + "}^{" + e + "}"

    def funktion_hoch(self, name, e, arg):
        return "\\" + name + "^{" + e + "}" + self.klammer(arg)

    def wurzel(self, s):
        return r"\sqrt{" + s + "}"

    def nwurzel(self, n, s):
        return r"\sqrt[" + n + "]{" + s + "}"

    def log_basis(self, b, s, knoten):
        return r"\log_{" + b + "}" + self.klammer(s)

    def binom(self, n, k):
        return r"\binom{" + n + "}{" + k + "}"

    def konjugiert(self, s):
        return r"\overline{" + s + "}"

    def relation(self, op):
        return {"=": "=", "<": "<", ">": ">", "<=": r"\le ", ">=": r"\ge ", "!=": r"\ne ", "≈": r"\approx "}[op]

    def op_folgt(self):
        return r"\quad\Rightarrow\quad "

    def op_vereinigt(self):
        return r"\cup "

    def op_ohne(self):
        return r"\setminus "

    def op_doppelpunkt(self):
        return r":\ "

    def mengenname(self, n):
        return r"\mathbb{" + n + "}"

    def index_menge(self, n):
        return r"_{\mathbb{" + n + "}}"

    def roh(self, latex, text):
        return latex

    def zuweisung(self):
        return r"\coloneqq "

    def striche(self, n):
        return "'" * n

    def liste_trenner(self, teile):
        return r";\ ".join(teile)

    def std_funktion(self, name, arg):
        return "\\" + name + self.klammer(arg)

    def operatorname(self, name):
        return r"\operatorname{" + name.replace("_", r"\_") + "}"

    def matrix(self, zeilen):
        return r"\begin{pmatrix}" + r"\\".join("&".join(z) for z in zeilen) + r"\end{pmatrix}"

    def determinante(self, zeilen):
        return r"\begin{vmatrix}" + r"\\".join("&".join(z) for z in zeilen) + r"\end{vmatrix}"

    def menge(self, teile):
        return r"\left\{" + r";\ ".join(teile) + r"\right\}"

    def intervall(self, a, b, lo, ro):
        return (r"\left]" if lo else r"\left[") + a + r";\ " + b + (r"\right[" if ro else r"\right]")

    def verknuepfe(self, teile, op):
        return op.join(teile)

    def ableitung(self, var, n, f, knoten):
        d = r"\mathrm{d}"
        if n:
            return r"\frac{" + d + "^{" + n + "}}{" + d + var + "^{" + n + "}}" + self._abl_arg(f, knoten)
        return r"\frac{" + d + "}{" + d + var + "}" + self._abl_arg(f, knoten)

    def _abl_arg(self, f, knoten):
        return self.klammer(f) if knoten[0] not in ("name", "ruf", "klammer") else f

    def integral(self, f, var, a, b):
        grenzen = "_{" + a + "}^{" + b + "}" if a is not None else ""
        return r"\int" + grenzen + " " + f + r"\,\mathrm{d}" + var

    def grenzwert(self, var, ziel, richtung, f):
        r = ""
        if richtung in ("+", "-"):
            r = "^{" + richtung + "}"
        return r"\lim_{" + var + r"\to " + ziel + r + "} " + f

    def summe(self, var, a, b, f):
        return r"\sum_{" + var + "=" + a + "}^{" + b + "} " + f

    def produkt(self, var, a, b, f):
        return r"\prod_{" + var + "=" + a + "}^{" + b + "} " + f

    def transponiert(self, s):
        return "{" + s + r"}^{\mathsf{T}}"

    def index_name(self, n, index):
        return self.name(n) + "_{" + ";".join(index) + "}"

    def index_funktion(self, n, index, args):
        return self.index_name(n, index) + self.klammer(r";\ ".join(args))


# ===================================================================== StarMath (LibreOffice Math)
class StarMathSetzer(_Setzer):
    """Erzeugt reines ASCII-StarMath (Schlüsselwörter statt Sonderzeichen)."""

    def platz(self):
        return " <?> "

    def zahl(self, s):
        neg = s.startswith("-")
        s = s.lstrip("-")
        if "e" in s:
            m, e = s.split("e")
            s = '"' + m + '" cdot 10^{' + str(int(e)).replace("-", "-") + "}"
        elif "," in s:
            s = '"' + s + '"'                         # Dezimalkomma als ein Zeichen setzen
        return ("-" if neg else "") + s

    def text(self, s):
        return ' "' + s.replace('"', "'") + '" '

    def name(self, n):
        basis, _, index = n.partition("_")
        if basis == "pi":
            b = "%pi"
        elif basis == "e":
            b = "nitalic{e}"
        elif basis == "i" and not index:
            b = "nitalic{i}"
        elif basis in ("oo", "inf"):
            b = "infinity"
        elif basis in GRIECHISCH:
            b = "%i" + ("varepsilon" if basis == "epsilon" else "varphi" if basis == "phi" else basis)
        elif basis in GRIECHISCH_GROSS:
            b = "%" + basis.upper()
        else:
            b = basis
        if index:
            b += "_{" + index + "}"
        return " " + b + " "

    def konst_e(self):
        return " nitalic{e} "

    def klammer(self, s):
        return " left( " + s + " right) "

    def betrag(self, s):
        return " abs{ " + s + " } "

    def norm(self, s):
        return " left ldline " + s + " right rdline "

    def abrunden(self, s):
        return " left lfloor " + s + " right rfloor "

    def aufrunden(self, s):
        return " left lceil " + s + " right rceil "

    def op_plus(self):
        return " + "

    def op_minus(self):
        return " - "

    def op_vorzeichen_minus(self):
        return " -"

    def op_mal(self):
        return " cdot "

    def op_kreuz(self):
        return " times "

    def op_geteilt(self):
        return ' ":" '

    def op_oder(self):
        return " or "

    def op_und(self):
        return " and "

    def juxta(self, a, b, knoten_b):
        return a + " " + b

    def bruch(self, a, b):
        return " {" + a + "} over {" + b + "} "

    def potenz(self, b, e):
        return " {" + b + "}^{" + e + "} "

    def funktion_hoch(self, name, e, arg):
        return " " + name + "^{" + e + "} left( " + arg + " right) "

    def wurzel(self, s):
        return " sqrt{" + s + "} "

    def nwurzel(self, n, s):
        return " nroot{" + n + "}{" + s + "} "

    def log_basis(self, b, s, knoten):
        return " log_{" + b + "} left( " + s + " right) "

    def binom(self, n, k):
        return " left( binom{" + n + "}{" + k + "} right) "

    def konjugiert(self, s):
        return " overline{" + s + "} "

    def relation(self, op):
        return {"=": " = ", "<": " < ", ">": " > ", "<=": " <= ", ">=": " >= ", "!=": " <> ", "≈": " approx "}[op]

    def op_folgt(self):
        return " ~~ drarrow ~~ "

    def op_vereinigt(self):
        return " union "

    def op_ohne(self):
        return " setminus "

    def op_doppelpunkt(self):
        return ' ":" ~ '

    def mengenname(self, n):
        return " set" + n + " " if n in "NZQRC" else " " + n + " "

    def index_menge(self, n):
        return "_{set" + n + "}"

    def roh(self, latex, text):
        return ' "' + text.replace('"', "'") + '" '

    def zuweisung(self):
        return ' ":=" '

    def striche(self, n):
        return '"' + "′" * n + '" '

    def k_fak(self, k):
        return " fact{" + self.teil(k[1], R_ATOM) + "} "

    def f_factorial(self, A, S):
        return " fact{" + self.teil(A[0], R_ATOM) + "} "

    def liste_trenner(self, teile):
        return ' ";" '.join(teile)

    def std_funktion(self, name, arg):
        if name in ("det", "max", "min", "lg", "exp"):
            return " func " + name + " left( " + arg + " right) "
        return " " + name + " left( " + arg + " right) "

    def operatorname(self, name):
        if all(c.isascii() and (c.isalnum() or c == "_") for c in name):
            return " func " + name.replace("_", "") + " "
        return ' "' + name + '" '

    def matrix(self, zeilen):
        return " left( matrix{ " + " ## ".join(" # ".join(z) for z in zeilen) + " } right) "

    def determinante(self, zeilen):
        return " left lline matrix{ " + " ## ".join(" # ".join(z) for z in zeilen) + " } right rline "

    def menge(self, teile):
        return " left lbrace " + ' ";" '.join(teile) + " right rbrace "

    def intervall(self, a, b, lo, ro):
        links = " left ] " if lo else " left [ "            # offene Intervalle nach DIN: ]a; b[
        rechts = " right [ " if ro else " right ] "
        return links + a + ' ";" ' + b + rechts

    def verknuepfe(self, teile, op):
        return op.join(teile)

    def ableitung(self, var, n, f, knoten):
        if n:
            return " {nitalic{d}^{" + n + "}} over {nitalic{d}" + var + "^{" + n + "}} " + self._abl_arg(f, knoten)
        return " {nitalic{d}} over {nitalic{d}" + var + "} " + self._abl_arg(f, knoten)

    def _abl_arg(self, f, knoten):
        return " left( " + f + " right) " if knoten[0] not in ("name", "ruf", "klammer") else f

    def integral(self, f, var, a, b):
        grenzen = " from{" + a + "} to{" + b + "} " if a is not None else " "
        return " int" + grenzen + "{ " + f + " } ` nitalic{d}" + var + " "

    def grenzwert(self, var, ziel, richtung, f):
        z = ziel
        if richtung in ("+", "-"):
            z = " {" + ziel + "}^{\"" + richtung + "\"} "      # + / − als Zeichen, nicht als Rechenzeichen
        return " lim from{" + var + " toward " + z + "} { " + f + " } "

    def summe(self, var, a, b, f):
        return " sum from{" + var + " = " + a + "} to{" + b + "} { " + f + " } "

    def produkt(self, var, a, b, f):
        return " prod from{" + var + " = " + a + "} to{" + b + "} { " + f + " } "

    def transponiert(self, s):
        return " {" + s + "}^{nitalic{T}} "

    def index_name(self, n, index):
        return " " + self.name(n).strip() + "_{" + ' ";" '.join(index) + "} "

    def index_funktion(self, n, index, args):
        return self.index_name(n, index) + self.klammer(' ";" '.join(args))


_LATEX, _STARMATH = LatexSetzer(), StarMathSetzer()


def latex(knoten):
    return _LATEX.setze(knoten)


def starmath(knoten):
    s = _STARMATH.setze(knoten)
    return " ".join(s.split())
