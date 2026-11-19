# Référence du langage Vyrn

## Structure d'un programme

Un fichier `.vy` contient des déclarations de haut niveau : `fn`, `struct`, `extern fn` et `cinclude`.
Le point d'entrée est `fn main()` ou `fn main() -> int`. Dans le second cas, la valeur renvoyée devient le code de sortie.
Les commentaires commencent par `#`. Les blocs sont délimités par l'indentation, comme en Python.

## Types

| Type | C sous-jacent | Exemple |
|---|---|---|
| `int` | `int64_t` | `42`, `1_000_000` |
| `float` | `double` | `3.14`, `1e-9` |
| `bool` | `bool` | `true`, `false` |
| `str` | `const char*` (UTF-8) | `"salut\n"`, `'ok'` |
| `list[T]` | tableau dynamique | `[1, 2, 3]` |
| `struct` | structure allouée | `Point(1.0, 2.0)` |

Un `int` est converti automatiquement en `float` quand un `float` est attendu. Aucune autre conversion n'est implicite : utilise `int()`, `float()` ou `str()`.

Les structs et les listes sont des **références**, comme en Python : les passer à une fonction permet de les modifier.

## Variables

```python
let x = 10            # immuable
var total = 0.0       # mutable
let xs: list[int] = []  # annotation obligatoire pour une liste vide
total += x
```

## Opérateurs

- Arithmétique : `+ - * / %`. `/` entre deux `int` donne une division entière. La division par zéro provoque une erreur claire.
- Comparaison : `== != < <= > >=`. Fonctionne aussi sur les `str`, par ordre lexicographique.
- Logique : `and or not`.
- Chaînes : `"a" + "b"` concatène, `"ab" * 3` répète.

## Contrôle

```python
if x > 0:
    print("positif")
elif x == 0:
    print("nul")
else:
    print("négatif")

while n > 0:
    n -= 1

for i in 0..10:        # 0 à 9
    pass
for item in liste:
    pass
for c in "texte":      # caractères
    pass
```

Un bloc d'une seule instruction peut tenir sur une ligne : `if n < 2: return n`.

## Fonctions

```python
fn moyenne(xs: list[float]) -> float:
    var s = 0.0
    for x in xs:
        s += x
    return s / len(xs)
```

## Structs

```python
struct Joueur:
    nom: str
    score: int

let j = Joueur("Ada", 0)
j.score += 10
print(j)   # Joueur(nom="Ada", score=10)
```

## Listes

Indexation : `xs[0]`, `xs[-1]`. Un accès hors limites provoque une erreur indiquant la ligne.

Méthodes : `push(v)`, `pop()`, `insert(i, v)`, `remove_at(i)`, `clear()`, `copy()`, `reverse()`.
Les listes de types simples ont aussi `contains(v)` et `index_of(v)`.

## Chaînes

`len(s)`, `s[i]`, `upper()`, `lower()`, `trim()`, `contains(t)`, `starts_with(t)`, `ends_with(t)`,
`find(t)`, `slice(a, b)`, `split(sep)` (renvoie `list[str]`), `replace(a, b)`, `repeat(n)`.

## Fonctions intégrées

`print(...)`, `input(msg)`, `len`, `str`, `int`, `float`, `abs`, `min`, `max`, `pow`,
`sqrt sin cos tan floor ceil exp log fabs`, `rand_int(min, max)`, `clock()`, `assert(cond, msg)`, `exit(code)`.

## Interopérabilité C

```python
cinclude "stdlib.h"
extern fn atoi(s: str) -> int

fn main():
    print(atoi("41") + 1)
```

`extern fn` déclare une fonction C existante. L'en-tête doit être inclus avec `cinclude`.
Correspondances : `int` ↔ `int64_t`, `float` ↔ `double`, `str` ↔ `const char*`.
