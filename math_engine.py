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
