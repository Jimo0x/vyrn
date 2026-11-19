<div align="center">

# 🜂 Vyrn

**La syntaxe de Python. La vitesse du C.**

Vyrn est un langage typé statiquement, à indentation, qui se compile en C puis en exécutable natif.

![tests](https://github.com/Jimo0x/vyrn/actions/workflows/tests.yml/badge.svg)

</div>

```python
struct Point:
    x: float
    y: float

fn dist(a: Point, b: Point) -> float:
    let dx = a.x - b.x
    let dy = a.y - b.y
    return sqrt(dx * dx + dy * dy)

fn main():
    var pts: list[Point] = []
    for i in 0..5:
        pts.push(Point(i, i * 2))
    print(pts[4], dist(pts[0], pts[4]))
```

## Pourquoi Vyrn ?

| | Python | C | **Vyrn** |
|---|---|---|---|
| Syntaxe lisible, indentation | ✅ | ❌ | ✅ |
| Types vérifiés avant l'exécution | ❌ | ✅ | ✅ (avec inférence) |
| Exécutable natif, sans runtime | ❌ | ✅ | ✅ |
| Appel direct de fonctions C | ❌ | ✅ | ✅ (`extern`) |
| Erreurs claires (ligne, colonne, contrôle des bornes) | ✅ | ❌ | ✅ |

**Performance** : `examples/bench.vy` calcule `fib(35)` et un crible de 10 millions d'entiers en **≈ 0,08 s**.
CPython met **≈ 0,9 s** pour `fib(35)` seul.

## Installation

Il faut Python ≥ 3.9 et un compilateur C (`gcc` ou `clang` ; sous Windows, [MinGW-w64](https://www.mingw-w64.org/)).

```bash
pip install git+https://github.com/Jimo0x/vyrn
```

## Utilisation

```bash
vyrn run programme.vy          # compile et exécute
vyrn build programme.vy -o app # exécutable natif
vyrn check programme.vy        # vérifie les types sans compiler
vyrn check programme.vy --json # diagnostics pour les éditeurs
vyrn emit-c programme.vy       # montre le C généré
```

Un éditeur dédié existe : **[Vyrn Studio](https://github.com/Jimo0x/vyrn-studio)**.

## Le langage en 2 minutes

Voir [docs/LANGAGE.md](docs/LANGAGE.md) pour la référence complète.

- **Types** : `int` (64 bits), `float`, `bool`, `str`, `list[T]`, et `struct`.
- **Variables** : `let` (immuable) et `var` (mutable). Le type est inféré, ou annoté : `let n: float = 3`.
- **Contrôle** : `if`, `elif` et `else` ; `while` ; `for i in 0..n` ; `for x in liste` ; `break` et `continue`.
- **Fonctions** : `fn nom(a: int, b: str) -> float:`.
- **Interop C** : `cinclude "stdlib.h"` puis `extern fn atoi(s: str) -> int`.
- **Intégrés** : `print`, `input`, `len`, `str`, `int`, `float`, `abs`, `min`, `max`, `pow`, `sqrt` et le reste de `<math.h>`, `rand_int`, `clock`, `assert`, `exit`.

## Architecture

```
source .vy ─► lexer ─► parser ─► vérificateur de types ─► générateur C ─► cc ─► binaire natif
             (indent)   (AST)     (inférence, erreurs)     (+ runtime)
```

Le compilateur est écrit en Python pur, sans dépendance. `python -m unittest discover -s tests` lance la suite de tests.

## Limites actuelles (v0.1)

- La mémoire n'est jamais libérée. Ça convient aux programmes courts, pas à un serveur qui tourne des jours.
- Il n'y a ni modules/imports, ni génériques, ni closures.
- L'ordre d'évaluation des arguments n'est pas garanti, comme en C.

## Licence

MIT
