"""Rechenkern: Syntaxbaum → SymPy (symbolisch), NumPy/SciPy (numerisch) → Ergebnis als Syntaxbaum.

Ein Arbeitsblatt merkt sich Festlegungen (a := 3, f(x) := x^2) für alle folgenden Zeilen.
"""

import sympy as sp
from sympy.logic.boolalg import BooleanAtom

from .sprache import parse, platzhalter_in, definierte_namen
from . import satz


class RechenFehler(ValueError):
    pass


_KONST = {"pi": sp.pi, "e": sp.E, "i": sp.I, "oo": sp.oo, "inf": sp.oo}
_FUNK = {
    "sin": sp.sin, "cos": sp.cos, "tan": sp.tan, "cot": sp.cot,
    "arcsin": sp.asin, "arccos": sp.acos, "arctan": sp.atan, "asin": sp.asin, "acos": sp.acos, "atan": sp.atan,
    "sinh": sp.sinh, "cosh": sp.cosh, "tanh": sp.tanh, "exp": sp.exp, "ln": sp.log, "sqrt": sp.sqrt,
    "abs": sp.Abs, "floor": sp.floor, "ceil": sp.ceiling, "sign": sp.sign, "sgn": sp.sign,
    "factorial": sp.factorial, "gamma": sp.gamma, "re": sp.re, "im": sp.im, "conjugate": sp.conjugate,
}

NUMERISCH = {"nsolve", "fsolve", "brentq", "quad", "nroots", "minimize", "maximize", "binompdf", "binomcdf",
             "normpdf", "normcdf", "invnorm", "poissonpdf", "poissoncdf", "mean", "median", "var", "std", "N"}


def _float(x):
    return sp.Float(float(x), 10)                     # zehn gültige Ziffern für numerische Ergebnisse


class Arbeitsblatt:
    def __init__(self):
        self.variablen = {}       # name → SymPy-Wert
        self.funktionen = {}      # name → (Parameter-Symbole, SymPy-Ausdruck)
        self._symbole = {}

    # ------------------------------------------------------------ Hilfen
    def sym(self, name):
        if name not in self._symbole:
            self._symbole[name] = sp.Symbol(name, real=True)
        return self._symbole[name]

    def namen(self):
        return set(self.variablen), set(self.funktionen)

    def parse(self, text):
        v, f = self.namen()
        return parse(text, v, f)

    # ------------------------------------------------------------ öffentliche Schnittstelle
    def setze(self, text):
        """Nur Formelsatz (keine Auswertung)."""
        k = self.parse(text)
        return {"latex": satz.latex(k), "starmath": satz.starmath(k)}

    def berechne(self, text):
        k = self.parse(text)
        if platzhalter_in(k):
            raise RechenFehler("Bitte zuerst alle Platzhalter □ ausfüllen")
        d = definierte_namen(k)
        if d:
            return self._zuweisung(k, d)
        befehl = k[1] if k[0] == "ruf" else None
        if k[0] == "rel":
            # Gleichung/Ungleichung: mit Variablen → lösen, ohne → wahr/falsch
            wert = self.ausdruck(k)
            if getattr(wert, "free_symbols", None):
                return self._ausgabe(k, self.b_solve([k], {}), "solve")
            return self._ausgabe(k, bool(sp.simplify(wert)), None)
        wert = self.ausdruck(k)
        return self._ausgabe(k, wert, befehl)

    # ------------------------------------------------------------ Zuweisungen
    def _zuweisung(self, k, d):
        if d[0] == "variable":
            wert = self.ausdruck(k[2])
            self.variablen[d[1]] = wert
            self.funktionen.pop(d[1], None)
            ergebnis = ast_aus_sympy(wert)
            gesamt = ("zuw", k[1], k[2]) if _gleich_dargestellt(k[2], ergebnis) else ("zuw", k[1], ("rel", [k[2], ergebnis], ["="]))
            return self._paket(k, ergebnis, gesamt)
        name, params = d[1], d[2]
        symbole = [self.sym(p) for p in params]
        alt = {p: self.variablen.pop(p) for p in params if p in self.variablen}   # Parameter sind keine festen Werte
        try:
            wert = self.ausdruck(k[2])
        finally:
            self.variablen.update(alt)
        self.funktionen[name] = (symbole, wert)
        self.variablen.pop(name, None)
        ergebnis = ast_aus_sympy(wert)
        gesamt = k if _gleich_dargestellt(k[2], ergebnis) else ("zuw", k[1], ("rel", [k[2], ergebnis], ["="]))
        return self._paket(k, ergebnis, gesamt)

    # ------------------------------------------------------------ Ausgabe zusammenstellen
    def _ausgabe(self, k, wert, befehl):
        if isinstance(wert, _Loesung):                  # solve, csolve, nroots
            gesamt = ("folgt", k, ("rel", [("mengenname", "L"), wert.ast], ["="]))
            return self._paket(k, wert.ast, gesamt)
        if isinstance(wert, _Fertig):
            return self._paket(k, wert.ast, ("rel", [k, wert.ast], [wert.zeichen]) if wert.zeichen else ("folgt", k, wert.ast))
        if isinstance(wert, (bool, BooleanAtom)):
            erg = ("bool", bool(wert))
            return self._paket(k, erg, ("folgt", k, erg))
        if isinstance(wert, (sp.core.relational.Relational, sp.And, sp.Or)):
            erg = ast_aus_sympy(wert)                   # z. B. Lösung einer Differentialgleichung y(x) = …
            return self._paket(k, erg, ("folgt", k, erg))
        ergebnis = ast_aus_sympy(wert)
        numerisch = befehl in NUMERISCH or _hat_float(wert)
        zeichen = "≈" if numerisch else "="
        teile = [k, ergebnis]
        ops = [zeichen]
        # exakte Zahl, die keine ganze Zahl ist → zusätzlich Näherungswert
        if not numerisch and isinstance(wert, sp.Expr) and wert.is_number and not wert.is_Integer and wert.is_finite:
            try:
                n = sp.N(wert, 10)
                if n.is_real or n.is_complex:
                    teile.append(ast_aus_sympy(n))
                    ops.append("≈")
            except Exception:
                pass
        if _gleich_dargestellt(k, ergebnis) and len(teile) == 2:
            gesamt = k
        else:
            gesamt = ("rel", teile, ops)
        return self._paket(k, ergebnis, gesamt)

    def _paket(self, eingabe, ergebnis, gesamt):
        return {"eingabe_latex": satz.latex(eingabe), "eingabe_starmath": satz.starmath(eingabe),
                "ergebnis_latex": satz.latex(ergebnis), "ergebnis_starmath": satz.starmath(ergebnis),
                "latex": satz.latex(gesamt), "starmath": satz.starmath(gesamt)}

    # ------------------------------------------------------------ Übersetzung Syntaxbaum → SymPy
    def ausdruck(self, k, ctx=None):
        ctx = ctx or {}
        t = k[0]
        f = getattr(self, "u_" + t, None)
        if not f:
            raise RechenFehler(f"Kann „{t}“ nicht berechnen")
        return f(k, ctx)

    def a(self, k, ctx):
        return self.ausdruck(k, ctx)

    def u_zahl(self, k, ctx):
        return sp.Rational(k[1].replace(",", "."))

    def u_text(self, k, ctx):
        return k[1]

    def u_name(self, k, ctx):
        n = k[1]
        if n in ctx.get("funktionen_als", {}):
            return ctx["funktionen_als"][n]
        if n in self.variablen:
            return self.variablen[n]
        if n in _KONST:
            return _KONST[n]
        return self.sym(n)

    def u_klammer(self, k, ctx):
        return self.a(k[1], ctx)

    def u_betrag(self, k, ctx):
        w = self.a(k[1], ctx)
        if isinstance(w, sp.MatrixBase):
            return w.norm()
        return sp.Abs(w)

    def u_add(self, k, ctx):
        return self.a(k[1], ctx) + self.a(k[2], ctx)

    def u_sub(self, k, ctx):
        return self.a(k[1], ctx) - self.a(k[2], ctx)

    def u_mul(self, k, ctx):
        a, b = self.a(k[1], ctx), self.a(k[2], ctx)
        if isinstance(a, sp.MatrixBase) and isinstance(b, sp.MatrixBase) and a.shape == b.shape and a.shape[1] == 1:
            return a.dot(b)                            # Vektor · Vektor = Skalarprodukt
        return a * b

    def u_div(self, k, ctx):
        return self.a(k[1], ctx) / self.a(k[2], ctx)

    def u_neg(self, k, ctx):
        return -self.a(k[1], ctx)

    def u_pos(self, k, ctx):
        return self.a(k[1], ctx)

    def u_pot(self, k, ctx):
        b, e = self.a(k[1], ctx), self.a(k[2], ctx)
        if isinstance(b, sp.MatrixBase):
            return b ** e
        return sp.Pow(b, e)

    def u_fak(self, k, ctx):
        return sp.factorial(self.a(k[1], ctx))

    def u_liste(self, k, ctx):
        el = [self.a(e, ctx) for e in k[1]]
        if el and all(isinstance(e, sp.MatrixBase) and e.shape[1] == 1 for e in el) and len({e.shape for e in el}) == 1 \
                and all(x[0] == "liste" for x in k[1]):
            return sp.Matrix([list(e) for e in el])  # [[1;2];[3;4]] → Zeilen
        if el and all(isinstance(e, sp.Expr) for e in el):
            return sp.Matrix(el)
        return list(el)

    def u_rel(self, k, ctx):
        werte = [self.a(t, ctx) for t in k[1]]
        teile = []
        for op, a, b in zip(k[2], werte, werte[1:]):
            teile.append({"=": sp.Eq, "<": sp.Lt, ">": sp.Gt, "<=": sp.Le, ">=": sp.Ge, "!=": sp.Ne}[op](a, b, evaluate=False))
        return teile[0] if len(teile) == 1 else sp.And(*teile)

    def u_strich(self, k, ctx):
        name, n = k[1], k[2]
        if name in self.funktionen:
            params, ausdr = self.funktionen[name]
            return sp.diff(ausdr, params[0], n)
        var = ctx.get("dgl_var") or self.sym("x")
        return sp.Function(name)(var).diff(var, n)

    def u_ruf(self, k, ctx):
        name, args, striche = k[1], k[2], k[3]
        # Benutzerfunktion
        if name in self.funktionen:
            params, ausdr = self.funktionen[name]
            if len(args) != len(params):
                raise RechenFehler(f"{name} hat {len(params)} Argument(e)")
            if striche:
                ausdr = sp.diff(ausdr, params[0], striche)
            werte = [self.a(x, ctx) for x in args]
            return ausdr.subs(dict(zip(params, werte)), simultaneous=True)
        m = getattr(self, "b_" + name, None)
        if m:
            return m(args, ctx)
        if name in _FUNK:
            if len(args) != 1:
                raise RechenFehler(f"{name} erwartet ein Argument")
            return _FUNK[name](self.a(args[0], ctx))
        # unbekannte Funktion: f(x) als SymPy-Funktion (z. B. für Differentialgleichungen)
        werte = [self.a(x, ctx) for x in args]
        f = sp.Function(name)(*werte)
        if striche:
            f = f.diff(werte[0], striche)
        return f

    # ------------------------------------------------------------ einfache Funktionen
    def var(self, k, ctx):
        """Variable eines Befehls (integrate(…; x) …) – auch wenn x festgelegt ist, bleibt es das Symbol."""
        if k[0] != "name":
            raise RechenFehler("Hier wird eine Variable erwartet, z. B. x")
        return self.sym(k[1])

    def b_log(self, A, c):
        if len(A) == 2:
            return sp.log(self.a(A[0], c), self.a(A[1], c))
        return sp.log(self.a(A[0], c))

    def b_lg(self, A, c):
        return sp.log(self.a(A[0], c), 10)

    def b_root(self, A, c):
        x, n = self.a(A[0], c), self.a(A[1], c)
        return sp.real_root(x, n) if x.is_real is not False else sp.root(x, n)

    def b_binomial(self, A, c):
        return sp.binomial(self.a(A[0], c), self.a(A[1], c))

    b_binom = b_binomial

    def b_max(self, A, c):
        return sp.Max(*[self.a(x, c) for x in A])

    def b_min(self, A, c):
        return sp.Min(*[self.a(x, c) for x in A])

    def b_gcd(self, A, c):
        w = [self.a(x, c) for x in A]
        r = w[0]
        for x in w[1:]:
            r = sp.gcd(r, x)
        return r

    def b_lcm(self, A, c):
        w = [self.a(x, c) for x in A]
        r = w[0]
        for x in w[1:]:
            r = sp.lcm(r, x)
        return r

    def b_mod(self, A, c):
        return sp.Mod(self.a(A[0], c), self.a(A[1], c))

    def b_Eq(self, A, c):
        return sp.Eq(self.a(A[0], c), self.a(A[1], c), evaluate=False)

    # ------------------------------------------------------------ Analysis
    def b_diff(self, A, c):
        f = self.a(A[0], c)
        x = self.var(A[1], c) if len(A) > 1 else self._eine_variable(f)
        n = int(self.a(A[2], c)) if len(A) > 2 else 1
        return sp.diff(f, x, n)

    def b_integrate(self, A, c):
        f = self.a(A[0], c)
        x = self.var(A[1], c) if len(A) > 1 else self._eine_variable(f)
        if len(A) == 4:
            return sp.integrate(f, (x, self.a(A[2], c), self.a(A[3], c)))
        if len(A) == 3:
            raise RechenFehler("Bestimmtes Integral: integrate(Term; x; untere Grenze; obere Grenze)")
        return sp.integrate(f, x)

    def b_limit(self, A, c):
        f, x, a = self.a(A[0], c), self.var(A[1], c), self.a(A[2], c)
        if len(A) == 4:
            r = A[3][1] if A[3][0] == "text" else None
            if r not in ("+", "-"):
                raise RechenFehler('Richtung als "+" (von rechts) oder "-" (von links) angeben')
            return sp.limit(f, x, a, r)
        if a in (sp.oo, -sp.oo):
            return sp.limit(f, x, a)
        return sp.limit(f, x, a, "+-")

    def b_summation(self, A, c):
        return sp.summation(self.a(A[0], c), (self.var(A[1], c), self.a(A[2], c), self.a(A[3], c)))

    def b_product(self, A, c):
        return sp.product(self.a(A[0], c), (self.var(A[1], c), self.a(A[2], c), self.a(A[3], c)))

    def b_series(self, A, c):
        f = self.a(A[0], c)
        x = self.var(A[1], c) if len(A) > 1 else self._eine_variable(f)
        a = self.a(A[2], c) if len(A) > 2 else 0
        n = int(self.a(A[3], c)) if len(A) > 3 else 5
        return sp.series(f, x, a, n + 1).removeO()      # Taylorpolynom n-ten Grades

    def b_tangente(self, A, c):
        f, x, a = self.a(A[0], c), self.var(A[1], c), self.a(A[2], c)
        fa, m = f.subs(x, a), sp.diff(f, x).subs(x, a)
        return sp.expand(fa + m * (x - a))

    def b_dsolve(self, A, c):
        if len(A) < 2 or A[1][0] != "name":
            raise RechenFehler("dsolve(Gleichung; y) bzw. dsolve(Gleichung; y; y(0) = 1)")
        fname = A[1][1]
        x = self.sym("x")
        y = sp.Function(fname)(x)
        c2 = dict(c, funktionen_als={fname: y}, dgl_var=x)
        eq = self.a(A[0], c2)
        if not isinstance(eq, sp.Eq):
            eq = sp.Eq(eq, 0)
        ics = None
        if len(A) == 3:
            bed = A[2]
            if bed[0] != "rel" or bed[2] != ["="]:
                raise RechenFehler("Anfangsbedingung als Gleichung, z. B. y(0) = 1")
            links = bed[1][0]
            if links[0] == "ruf" and links[1] == fname:
                st = self.a(links[2][0], c)
                lk = y.diff(x, links[3]).subs(x, st) if links[3] else sp.Function(fname)(st)
            else:
                raise RechenFehler("Anfangsbedingung links wie y(0) oder y'(0)")
            ics = {lk: self.a(bed[1][1], c)}
        return sp.dsolve(eq, y, ics=ics)

    # ------------------------------------------------------------ Algebra
    def _ein(self, A, c, f):
        return f(self.a(A[0], c))

    def b_simplify(self, A, c):
        return self._ein(A, c, sp.simplify)

    def b_expand(self, A, c):
        return self._ein(A, c, sp.expand)

    def b_factor(self, A, c):
        return self._ein(A, c, sp.factor)

    def b_apart(self, A, c):
        f = self.a(A[0], c)
        return sp.apart(f, self.var(A[1], c)) if len(A) > 1 else sp.apart(f)

    def b_together(self, A, c):
        return self._ein(A, c, sp.together)

    def b_cancel(self, A, c):
        return self._ein(A, c, sp.cancel)

    def b_trigsimp(self, A, c):
        return self._ein(A, c, sp.trigsimp)

    def b_nsimplify(self, A, c):
        return self._ein(A, c, lambda w: sp.nsimplify(w, [sp.pi, sp.E], rational=False))

    def b_N(self, A, c):
        n = int(self.a(A[1], c)) if len(A) > 1 else 10
        return sp.N(self.a(A[0], c), n)

    def b_subs(self, A, c):
        return self.a(A[0], c).subs(self.var(A[1], c), self.a(A[2], c))

    def b_solve(self, A, c, bereich=None):
        bereich = bereich or sp.S.Reals
        ziel = self.a(A[0], c)
        if len(A) > 1:
            vars_ = [self.var(v, c) for v in A[1][1]] if A[1][0] == "liste" else [self.var(A[1], c)]
        else:
            vars_ = None
        gleichungen = ziel if isinstance(ziel, (list, sp.MatrixBase)) else [ziel]
        gleichungen = [g if isinstance(g, sp.core.relational.Relational) else sp.Eq(g, 0) for g in gleichungen]
        if vars_ is None:
            frei = set().union(*[g.free_symbols for g in gleichungen])
            vars_ = sorted(frei, key=lambda s: s.name)
        if len(gleichungen) == 1 and len(vars_) == 1:
            g = gleichungen[0]
            if isinstance(g, sp.Eq):
                menge = sp.solveset(g, vars_[0], domain=bereich)
            else:
                menge = sp.solveset(g, vars_[0], domain=sp.S.Reals)
            return _Loesung(ast_aus_menge(menge))
        # Gleichungssystem
        loes = sp.solve(gleichungen, vars_, dict=True)
        if not loes:
            return _Loesung(("menge", []))
        teile = []
        for d in loes:
            paar = [ast_aus_sympy(d.get(v, v)) for v in vars_]
            teile.append(("tupel", paar))
        return _Loesung(("menge", teile))

    def b_csolve(self, A, c):
        return self.b_solve(A, c, sp.S.Complexes)

    # ------------------------------------------------------------ Lineare Algebra
    def _matrix(self, A, c, i=0):
        m = self.a(A[i], c)
        if not isinstance(m, sp.MatrixBase):
            raise RechenFehler("Hier wird eine Matrix oder ein Vektor erwartet, z. B. [[1; 2]; [3; 4]]")
        return m

    def b_Matrix(self, A, c):
        return self._matrix(A, c)

    def b_det(self, A, c):
        return self._matrix(A, c).det()

    def b_inv(self, A, c):
        m = self._matrix(A, c)
        if m.det() == 0:
            raise RechenFehler("Die Matrix ist nicht invertierbar (Determinante 0)")
        return m.inv()

    def b_transpose(self, A, c):
        return self._matrix(A, c).T

    def b_rank(self, A, c):
        return sp.Integer(self._matrix(A, c).rank())

    def b_trace(self, A, c):
        return self._matrix(A, c).trace()

    def b_eigenvals(self, A, c):
        ew = self._matrix(A, c).eigenvals()
        teile = []
        for i, (w, vf) in enumerate(sorted(ew.items(), key=lambda p: sp.default_sort_key(p[0]))):
            eintrag = ("rel", [("name", "lambda_" + str(i + 1)), ast_aus_sympy(w)], ["="])
            if vf > 1:
                eintrag = ("mit_text", eintrag, f"({vf}-fach)")
            teile.append(eintrag)
        return _Fertig(("folge", teile), None)

    def b_eigenvects(self, A, c):
        teile = []
        for i, (w, vf, vekt) in enumerate(self._matrix(A, c).eigenvects()):
            for v in vekt:
                teile.append(("folge_paar", ("rel", [("name", "lambda_" + str(i + 1)), ast_aus_sympy(w)], ["="]),
                              ast_aus_sympy(v)))
        return _Fertig(("folge", teile), None)

    def b_rref(self, A, c):
        return self._matrix(A, c).rref()[0]

    def b_dot(self, A, c):
        return self._matrix(A, c, 0).dot(self._matrix(A, c, 1))

    def b_cross(self, A, c):
        return self._matrix(A, c, 0).cross(self._matrix(A, c, 1))

    def b_norm(self, A, c):
        return self._matrix(A, c).norm()

    def b_eye(self, A, c):
        return sp.eye(int(self.a(A[0], c)))

    def b_zeros(self, A, c):
        n = int(self.a(A[0], c))
        return sp.zeros(n, int(self.a(A[1], c)) if len(A) > 1 else n)

    def b_linsolve(self, A, c):
        M, b = self._matrix(A, c, 0), self._matrix(A, c, 1)
        xs = sp.symbols("x_1:%d" % (M.shape[1] + 1), real=True)
        menge = sp.linsolve((M, b), *xs)
        if menge == sp.S.EmptySet:
            return _Fertig(("rel", [("mengenname", "L"), ("menge", [])], ["="]), None)
        tupel = list(menge)[0]
        return sp.Matrix(list(tupel))

    # ------------------------------------------------------------ Numerik
    def _lambda(self, f, x):
        import numpy as np
        g = sp.lambdify(x, f, modules=["numpy"])
        return lambda t: float(np.real(g(t)))

    def _nullform(self, f):
        if isinstance(f, sp.Eq):
            return f.lhs - f.rhs
        return f

    def b_nsolve(self, A, c):
        f, x, x0 = self._nullform(self.a(A[0], c)), self.var(A[1], c), self.a(A[2], c)
        return _als_loesung(x, sp.nsolve(f, x, float(x0)))

    def b_fsolve(self, A, c):
        from scipy.optimize import fsolve
        f, x, x0 = self._nullform(self.a(A[0], c)), self.var(A[1], c), self.a(A[2], c)
        g = self._lambda(f, x)
        w = fsolve(lambda t: g(t[0]), [float(x0)])[0]
        return _als_loesung(x, _float(w))

    def b_brentq(self, A, c):
        from scipy.optimize import brentq
        f, x = self._nullform(self.a(A[0], c)), self.var(A[1], c)
        a, b = float(self.a(A[2], c)), float(self.a(A[3], c))
        g = self._lambda(f, x)
        if g(a) * g(b) > 0:
            raise RechenFehler("Kein Vorzeichenwechsel zwischen den Grenzen")
        return _als_loesung(x, _float(brentq(g, a, b)))

    def b_quad(self, A, c):
        from scipy.integrate import quad
        f, x = self.a(A[0], c), self.var(A[1], c)
        a, b = self.a(A[2], c), self.a(A[3], c)
        g = self._lambda(f, x)
        w, fehler = quad(g, float(a), float(b))
        return _float(w)

    def b_nroots(self, A, c):
        import numpy as np
        f = self._nullform(self.a(A[0], c))
        frei = sorted(f.free_symbols, key=lambda s: s.name)
        if len(frei) != 1:
            raise RechenFehler("nroots erwartet ein Polynom in einer Variablen")
        x = frei[0]
        koeff = [complex(k) for k in sp.Poly(f, x).all_coeffs()]
        wurzeln = np.roots(koeff)
        werte = []
        for w in sorted(wurzeln, key=lambda z: (abs(z.imag) > 1e-12, z.real, z.imag)):
            re, im = float(w.real), float(w.imag)
            werte.append(_float(re) if abs(im) < 1e-12 else _float(re) + sp.I * _float(im))
        return _Loesung(("menge", [ast_aus_sympy(w) for w in werte]), name=x.name)

    def _extremum(self, A, c, vorzeichen):
        from scipy.optimize import minimize
        f, x, x0 = self.a(A[0], c), self.var(A[1], c), self.a(A[2], c)
        g = self._lambda(f, x)
        r = minimize(lambda t: vorzeichen * g(t[0]), [float(x0)], tol=1e-14)
        xs = float(r.x[0])
        try:                                            # nachschärfen: Nullstelle der Ableitung nahe xs
            xn = float(sp.nsolve(sp.diff(f, x), x, xs))
            if abs(xn - xs) < 1e-4 * (1 + abs(xs)):
                xs = xn
        except Exception:
            pass
        return _Fertig(("folge", [("rel", [("name", x.name), ast_aus_sympy(_float(xs))], ["≈"]),
                                  ("rel", [("name", "y"),
                                           ast_aus_sympy(_float(g(xs)))], ["≈"])]), None)

    def b_minimize(self, A, c):
        return self._extremum(A, c, 1)

    def b_maximize(self, A, c):
        return self._extremum(A, c, -1)

    # ------------------------------------------------------------ Stochastik
    def _zahlen(self, A, c):
        return [float(self.a(x, c)) for x in A]

    def b_binompdf(self, A, c):
        from scipy.stats import binom
        n, p, k = self._zahlen(A, c)
        return _float(binom.pmf(round(k), round(n), p))

    def b_binomcdf(self, A, c):
        from scipy.stats import binom
        w = self._zahlen(A, c)
        n, p = round(w[0]), w[1]
        if len(w) == 4:
            a, b = round(w[2]), round(w[3])
            return _float(binom.cdf(b, n, p) - binom.cdf(a - 1, n, p))
        return _float(binom.cdf(round(w[2]), n, p))

    def b_normpdf(self, A, c):
        from scipy.stats import norm
        x, mu, s = self._zahlen(A, c)
        return _float(norm.pdf(x, mu, s))

    def b_normcdf(self, A, c):
        from scipy.stats import norm
        a, b, mu, s = self._zahlen(A, c)
        return _float(norm.cdf(b, mu, s) - norm.cdf(a, mu, s))

    def b_invnorm(self, A, c):
        from scipy.stats import norm
        p, mu, s = self._zahlen(A, c)
        return _float(norm.ppf(p, mu, s))

    def b_poissonpdf(self, A, c):
        from scipy.stats import poisson
        lam, k = self._zahlen(A, c)
        return _float(poisson.pmf(round(k), lam))

    def b_poissoncdf(self, A, c):
        from scipy.stats import poisson
        lam, k = self._zahlen(A, c)
        return _float(poisson.cdf(round(k), lam))

    def _daten(self, A, c):
        m = self.a(A[0], c)
        werte = list(m) if isinstance(m, (sp.MatrixBase, list)) else [m]
        return [float(w) for w in werte]

    def b_mean(self, A, c):
        import numpy as np
        return _float(np.mean(self._daten(A, c)))

    def b_median(self, A, c):
        import numpy as np
        return _float(np.median(self._daten(A, c)))

    def b_var(self, A, c):
        import numpy as np
        return _float(np.var(self._daten(A, c)))

    def b_std(self, A, c):
        import numpy as np
        return _float(np.std(self._daten(A, c)))

    def b_erwartungswert(self, A, c):
        xs, ps = self.a(A[0], c), self.a(A[1], c)
        xs, ps = list(xs), list(ps)
        if len(xs) != len(ps):
            raise RechenFehler("Gleich viele Werte und Wahrscheinlichkeiten angeben")
        return sp.nsimplify(sum(x * p for x, p in zip(xs, ps)))

    # ------------------------------------------------------------
    def _eine_variable(self, f):
        frei = sorted(getattr(f, "free_symbols", set()), key=lambda s: s.name)
        if len(frei) == 1:
            return frei[0]
        if self.sym("x") in frei or not frei:
            return self.sym("x")
        raise RechenFehler("Bitte die Variable angeben, z. B. diff(…; x)")


class _Fertig:
    """Bereits als Syntaxbaum aufbereitetes Ergebnis; zeichen: „=“, „≈“ oder None (dann ⇒)."""
    def __init__(self, ast, zeichen):
        self.ast, self.zeichen = ast, zeichen


class _Loesung:
    def __init__(self, ast, name=None):
        self.ast = ast


def _als_loesung(x, wert):
    return _Fertig(("rel", [("name", x.name), ast_aus_sympy(wert)], ["≈"]), None)


def _hat_float(w):
    try:
        if isinstance(w, sp.MatrixBase):
            return any(e.has(sp.Float) for e in w)
        return isinstance(w, sp.Basic) and w.has(sp.Float)
    except Exception:
        return False


def _gleich_dargestellt(a, b):
    try:
        return satz.latex(a) == satz.latex(b)
    except Exception:
        return False


# ===================================================================== SymPy → Syntaxbaum
def _zahl_text(f):
    """Gleitkommazahl mit Dezimalkomma; so viele gültige Ziffern, wie die Zahl trägt (N(x; 30) → 30)."""
    f = sp.Float(f)
    if f == 0:
        return "0"
    stellen = max(1, int(round(int(f._prec) / 3.3219280948873626) - 1))
    stellen = min(stellen, 60)
    s = str(sp.Float(f, stellen))
    if "e" in s:
        m, e = s.split("e")
        if "." in m:
            m = m.rstrip("0").rstrip(".")
        s = m + "e" + str(int(e))
    elif "." in s:
        s = s.rstrip("0").rstrip(".")
    return s.replace(".", ",")


def _name(s):
    n = s.name if hasattr(s, "name") else str(s)
    return n


def ast_aus_menge(m):
    if m == sp.S.EmptySet:
        return ("menge", [])
    if isinstance(m, sp.FiniteSet):
        el = sorted(m.args, key=lambda z: (sp.re(z).evalf() if z.is_number else 0, sp.default_sort_key(z)))
        return ("menge", [ast_aus_sympy(z) for z in el])
    if m == sp.S.Reals:
        return ("mengenname", "R")
    if m == sp.S.Complexes:
        return ("mengenname", "C")
    if isinstance(m, sp.Interval):
        return ("intervall", ast_aus_sympy(m.start), ast_aus_sympy(m.end), bool(m.left_open), bool(m.right_open))
    if isinstance(m, sp.Union):
        return ("vereinigung", [ast_aus_menge(t) for t in m.args])
    if isinstance(m, sp.Complement) and m.args[0] == sp.S.Reals and isinstance(m.args[1], sp.FiniteSet):
        return ("ohne", ("mengenname", "R"), ast_aus_menge(m.args[1]))
    return ("roh", sp.latex(m), str(m))


def ast_aus_sympy(e):
    """SymPy-Objekt → Syntaxbaum (für den Formelsatz)."""
    if isinstance(e, bool):
        return ("bool", e)
    if isinstance(e, (int,)):
        return ("zahl", str(e)) if e >= 0 else ("neg", ("zahl", str(-e)))
    if isinstance(e, float):
        e = sp.Float(e)
    if isinstance(e, (list, tuple)):
        return ("folge", [ast_aus_sympy(x) for x in e])
    if isinstance(e, sp.MatrixBase):
        if e.shape[1] == 1:
            return ("liste", [ast_aus_sympy(x) for x in e])
        return ("liste", [("liste", [ast_aus_sympy(x) for x in e.row(i)]) for i in range(e.shape[0])])
    if isinstance(e, BooleanAtom):
        return ("bool", bool(e))
    if isinstance(e, sp.Set):
        return ast_aus_menge(e)
    if isinstance(e, sp.core.relational.Relational):
        op = {sp.Eq: "=", sp.Ne: "!=", sp.Lt: "<", sp.Le: "<=", sp.Gt: ">", sp.Ge: ">="}.get(type(e), "=")
        return ("rel", [ast_aus_sympy(e.lhs), ast_aus_sympy(e.rhs)], [op])
    if isinstance(e, sp.And):
        return ("und", [ast_aus_sympy(a) for a in e.args])
    if isinstance(e, sp.Or):
        return ("oder", [ast_aus_sympy(a) for a in e.args])
    if not isinstance(e, sp.Basic):
        return ("textzeile", str(e))

    # Zahlen
    if e is sp.S.Infinity:
        return ("name", "oo")
    if e is sp.S.NegativeInfinity:
        return ("neg", ("name", "oo"))
    if e is sp.S.ComplexInfinity:
        return ("name", "oo")
    if e is sp.S.NaN:
        return ("textzeile", "nicht definiert")
    if e is sp.S.Pi:
        return ("name", "pi")
    if e is sp.S.Exp1:
        return ("name", "e")
    if e is sp.S.ImaginaryUnit:
        return ("name", "i")
    if isinstance(e, sp.Integer):
        return ("zahl", str(e)) if e >= 0 else ("neg", ("zahl", str(-e)))
    if isinstance(e, sp.Rational):
        b = ("div", ("zahl", str(abs(e.p))), ("zahl", str(e.q)), "/")
        return ("neg", b) if e < 0 else b
    if isinstance(e, sp.Float):
        s = _zahl_text(e)
        return ("neg", ("zahl", s[1:])) if s.startswith("-") else ("zahl", s)
    if isinstance(e, sp.Symbol):
        return ("name", _name(e))

    # Summe
    if isinstance(e, sp.Add):
        terme = e.as_ordered_terms()
        erg = ast_aus_sympy(terme[0])
        for t in terme[1:]:
            if t.could_extract_minus_sign():
                erg = ("sub", erg, ast_aus_sympy(-t))
            else:
                erg = ("add", erg, ast_aus_sympy(t))
        return erg

    # Produkt
    if isinstance(e, sp.Mul):
        if e.could_extract_minus_sign():
            return ("neg", ast_aus_sympy(-e))
        zaehler, nenner = sp.fraction(e)
        if nenner != 1:
            return ("div", ast_aus_sympy(zaehler), ast_aus_sympy(nenner), "/")
        faktoren = e.as_ordered_factors()
        erg = ast_aus_sympy(faktoren[0])
        if isinstance(faktoren[0], sp.Add):
            erg = ("klammer", erg)
        for f in faktoren[1:]:
            fk = ast_aus_sympy(f)
            if isinstance(f, sp.Add):
                fk = ("klammer", fk)
            implizit = not f.is_Number                 # 2√2, 3x, x·sin(x) ohne Malpunkt; 2·3 mit
            erg = ("mul", erg, fk, implizit)
        return erg

    # Potenz
    if isinstance(e, sp.Pow):
        b, x = e.base, e.exp
        if x == sp.S.Half:
            return ("ruf", "sqrt", [ast_aus_sympy(b)], 0)
        if x.is_Rational and x.p == 1 and x.q > 2:
            return ("ruf", "root", [ast_aus_sympy(b), ("zahl", str(x.q))], 0)
        if x.is_number and x.could_extract_minus_sign():
            return ("div", ("zahl", "1"), ast_aus_sympy(sp.Pow(b, -x)), "/")
        if b is sp.S.Exp1:
            return ("pot", ("name", "e"), ast_aus_sympy(x))
        return ("pot", ast_aus_sympy(b), ast_aus_sympy(x))

    if isinstance(e, sp.exp):
        return ("pot", ("name", "e"), ast_aus_sympy(e.args[0]))
    if isinstance(e, sp.log):
        return ("ruf", "ln", [ast_aus_sympy(e.args[0])], 0)
    if isinstance(e, sp.Abs):
        return ("betrag", ast_aus_sympy(e.args[0]))
    if isinstance(e, sp.factorial):
        return ("fak", ast_aus_sympy(e.args[0]))
    if isinstance(e, sp.binomial):
        return ("ruf", "binomial", [ast_aus_sympy(a) for a in e.args], 0)
    namen = {sp.sin: "sin", sp.cos: "cos", sp.tan: "tan", sp.cot: "cot", sp.asin: "arcsin", sp.acos: "arccos",
             sp.atan: "arctan", sp.sinh: "sinh", sp.cosh: "cosh", sp.tanh: "tanh", sp.floor: "floor",
             sp.ceiling: "ceil", sp.sign: "sgn", sp.gamma: "gamma", sp.re: "re", sp.im: "im",
             sp.conjugate: "conjugate", sp.Max: "max", sp.Min: "min"}
    for klasse, n in namen.items():
        if isinstance(e, klasse):
            return ("ruf", n, [ast_aus_sympy(a) for a in e.args], 0)
    if isinstance(e, sp.Derivative):
        f = e.expr
        var, n = e.variable_count[0]
        if isinstance(f, sp.core.function.AppliedUndef) and len(f.args) == 1:
            return ("ruf", f.func.__name__, [ast_aus_sympy(a) for a in f.args], int(n))
        args = [ast_aus_sympy(f), ast_aus_sympy(var)] + ([ast_aus_sympy(n)] if n != 1 else [])
        return ("ruf", "diff", args, 0)
    if isinstance(e, sp.Integral):
        f = e.function
        lim = e.limits[0]
        args = [ast_aus_sympy(f), ast_aus_sympy(lim[0])] + ([ast_aus_sympy(lim[1]), ast_aus_sympy(lim[2])] if len(lim) == 3 else [])
        return ("ruf", "integrate", args, 0)
    if isinstance(e, sp.Limit):
        f, x, a, d = e.args
        return ("ruf", "limit", [ast_aus_sympy(f), ast_aus_sympy(x), ast_aus_sympy(a)], 0)
    if isinstance(e, sp.Sum):
        f = e.function
        x, a, b = e.limits[0]
        return ("ruf", "summation", [ast_aus_sympy(f), ast_aus_sympy(x), ast_aus_sympy(a), ast_aus_sympy(b)], 0)
    if isinstance(e, sp.core.function.AppliedUndef):
        return ("ruf", e.func.__name__, [ast_aus_sympy(a) for a in e.args], 0)
    if isinstance(e, sp.Piecewise):
        return ("roh", sp.latex(e), str(e))
    # Rückfall: SymPy-LaTeX und Text
    return ("roh", sp.latex(e), str(e))
