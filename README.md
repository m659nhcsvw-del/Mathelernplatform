# Mathelernplatform – Analysis, Jahrgang 11

Ein erster Prototyp mit **echtem Python und SymPy im Browser**.

## Was funktioniert?
- Grafische mathematische Eingabe mit MathLive
- Prüfung der Ableitung von `f(x) = 3x³ - 2x² + 5x - 1`
- Symbolischer Vergleich mathematisch gleichwertiger Terme durch SymPy
- Hinweis und durch SymPy berechnete, kommentierte Musterlösung
- Keine Installation bei Lehrkraft oder Lernenden

## Ohne Konsole veröffentlichen
1. GitHub-Repository `m659nhcsvw-del/Mathelernplatform` öffnen.
2. **Add file → Upload files** wählen.
3. **index.html** und **math_engine.py** (optional README.md) hochladen.
4. **Commit changes** anklicken.
5. **Settings → Pages → Build and deployment → Deploy from a branch → main / (root) → Save**.
6. Auf die Veröffentlichung warten und die Adresse öffnen:
   https://m659nhcsvw-del.github.io/Mathelernplatform/

## Technik und Grenzen
Pyodide 0.27.7 lädt Python und SymPy aus dem Internet; MathLive und MathJax werden ebenfalls über CDNs geladen. Beim ersten Aufruf können einige Sekunden vergehen. Alle eigentlichen Rechnungen und die Lösungsprüfung finden in Python statt. Der Python-Parser unterstützt für diesen Prototyp Zahlen, x, Klammern, +, -, *, / und ganzzahlige Potenzen; allgemeine Funktionen wie sin oder exp folgen später. Die Aufgabe speichert keine personenbezogenen Daten und benötigt kein Nutzerkonto.

**Hinweis:** Der Browser-End-to-End-Test auf GitHub Pages ist noch nicht durchgeführt. Die genaue ASCII-Math-Ausgabe verschiedener MathLive-Eingaben sollte im ersten Praxistest geprüft werden.
