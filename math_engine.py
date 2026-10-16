"""Echter Python/SymPy-Rechenkern für die Analysis-Aufgabe.
Der Parser akzeptiert absichtlich nur eine begrenzte arithmetische Grammatik.
Insbesondere wird keine Nutzereingabe an eval(), exec() oder sympify() übergeben.
"""
import json
import re
import sympy as sp

x = sp.Symbol("x")
f = 3*x**3 - 2*x**2 + 5*x - 1
correct = sp.diff(f, x)

class ParseError(Exception):
    pass

def parse_student(s):
    if not isinstance(s, str) or len(s) > 200:
        raise ParseError("Eingabe zu lang oder ungültig.")
    s = s.replace(" ", "").replace("−", "-").replace("×", "*").replace("·", "*")
    s = s.replace("**", "^")
    # ASCII-Math: x^(2) und (x)/(2) werden unterstützt.
    raw = re.findall(r"(?:\d+(?:\.\d+)?)|x|[+\-*/^()]", s)
    if "".join(raw) != s or not raw:
        raise ParseError("Bitte einen Term mit x, Zahlen und Grundrechenarten eingeben.")
    tokens = []
    for token in raw:
        if tokens and ((tokens[-1] == "x" or tokens[-1] == ")" or
                        re.fullmatch(r"\d+(?:\.\d+)?", tokens[-1])) and
                       (token == "x" or token == "(" or
                        re.fullmatch(r"\d+(?:\.\d+)?", token))):
            tokens.append("*")
        tokens.append(token)
    pos = 0
    def peek():
        return tokens[pos] if pos < len(tokens) else None
    def take(t=None):
        nonlocal pos
        if pos >= len(tokens) or (t is not None and tokens[pos] != t):
            raise ParseError("Ungültiger mathematischer Ausdruck.")
        val = tokens[pos]
        pos += 1
        return val
    def atom():
        t = peek()
        if t == "(":
            take("(")
            v = expr()
            take(")")
            return v
        if t == "x":
            take()
            return x
        if t is not None and re.fullmatch(r"\d+(?:\.\d+)?", t):
            take()
            return sp.Rational(t)
        raise ParseError("Bitte die Formel überprüfen.")
    def power():
        base = atom()
        if peek() == "^":
            take("^")
            exponent = unary()
            if not exponent.is_number or not exponent.is_integer or abs(int(exponent)) > 20:
                raise ParseError("Es werden nur ganzzahlige Exponenten bis 20 unterstützt.")
            return base**int(exponent)
        return base
    def unary():
        if peek() == "+":
            take("+")
            return unary()
        if peek() == "-":
            take("-")
            return -unary()
        return power()
    def product():
        v = unary()
        while peek() in ("*", "/"):
            op = take()
            rhs = unary()
            if op == "/" and rhs == 0:
                raise ParseError("Division durch null.")
            v = v * rhs if op == "*" else v / rhs
        return v
    def expr():
        v = product()
        while peek() in ("+", "-"):
            op = take()
            rhs = product()
            v = v + rhs if op == "+" else v - rhs
        return v
    result = expr()
    if pos != len(tokens):
        raise ParseError("Die Eingabe konnte nicht vollständig gelesen werden.")
    return result

def check_answer(s):
    try:
        proposed = parse_student(s)
        difference = sp.cancel(proposed - correct)
        if difference == 0:
            return json.dumps({"status":"correct","message":"Richtig! Deine Eingabe ist mathematisch gleichwertig mit der Ableitung."})
        if difference.is_zero is False or difference.equals(0) is False:
            return json.dumps({"status":"incorrect","message":"Noch nicht richtig. Prüfe Potenzregel, Vorzeichen und den linearen Term."})
        return json.dumps({"status":"uncertain","message":"SymPy konnte die Gleichwertigkeit nicht sicher entscheiden."})
    except (ParseError, ValueError, TypeError, OverflowError) as e:
        return json.dumps({"status":"error","message":str(e)})

def worked_solution():
    terms = [3*x**3, -2*x**2, 5*x, -1]
    return json.dumps({
        "steps":[{"source":sp.latex(t),"derivative":sp.latex(sp.diff(t,x))} for t in terms],
        "answer":sp.latex(correct)
    })

# Version 0.2: Rechenschritte, Fehlerdiagnose und gestufte Hilfen.
STEP_TERMS = [3*x**3, -2*x**2, 5*x, -1]
STEP_LABELS = ["3x³", "−2x²", "5x", "−1"]

def check_step(index, student):
    try:
        index = int(index)
        if index not in range(4):
            raise ParseError("Unbekannter Rechenschritt.")
        proposed = parse_student(student)
        term = STEP_TERMS[index]
        target = sp.diff(term, x)
        if sp.cancel(proposed - target) == 0:
            return json.dumps({"status": "correct", "message": "Richtig. Dieser Summand wurde korrekt abgeleitet."})
        # Diagnose auf Grundlage symbolischer Gleichwertigkeit mit typischen Fehlertermen.
        if sp.cancel(proposed - term) == 0:
            msg = "Du hast den ursprünglichen Summanden übernommen, statt ihn abzuleiten."
        elif index in (0, 1) and sp.cancel(proposed - sp.diff(abs(term), x)) == 0:
            msg = "Prüfe das Vorzeichen des ursprünglichen Summanden."
        elif index in (0, 1) and sp.cancel(proposed - (term/x)) == 0:
            msg = "Der Exponent wurde vermindert, aber der alte Exponent noch nicht mit dem Vorfaktor multipliziert."
        elif index == 2 and proposed == 0:
            msg = "Die Ableitung von 5x ist 5, nicht 0. Nur reine Konstanten fallen weg."
        elif index == 3 and proposed == -1:
            msg = "Die Ableitung einer Konstanten ist 0."
        elif proposed == 0 and index in (0, 1):
            msg = "Bei Potenzen von x ist die Ableitung im Allgemeinen nicht 0."
        else:
            msg = "Noch nicht richtig. Kontrolliere Faktor, Exponent und Vorzeichen."
        return json.dumps({"status": "incorrect", "message": msg})
    except (ParseError, ValueError, TypeError, OverflowError) as e:
        return json.dumps({"status": "error", "message": str(e)})

def step_hint(index, level):
    index, level = int(index), int(level)
    if index not in range(4):
        raise ParseError("Unbekannter Rechenschritt.")
    level = max(1, min(3, level))
    t = STEP_TERMS[index]
    derivative = sp.diff(t, x)
    if level == 1:
        message = ("Dieser Summand ist eine Konstante. Was ist die Ableitung einer Konstanten?"
                   if index == 3 else
                   "Nutze die Faktor- und Potenzregel: (a·x^n)' = a·n·x^(n−1).")
    elif level == 2:
        message = (["Multipliziere 3 mit 3 und reduziere den Exponenten von 3 auf 2.",
                    "Beachte das Minuszeichen: Multipliziere −2 mit 2 und reduziere den Exponenten auf 1.",
                    "Hier ist der Exponent 1. Der Vorfaktor bleibt erhalten und x fällt weg.",
                    "Eine Konstante verändert sich nicht, wenn x sich ändert."][index])
    else:
        message = "Für diesen Summanden ergibt SymPy: (" + sp.latex(t) + ")' = " + sp.latex(derivative)
    return json.dumps({"level": level, "message": message})
