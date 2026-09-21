# 03 — Générateurs

Comment construire un labyrinthe **parfait**, c'est-à-dire un labyrinthe où il existe
exactement un chemin entre deux cellules libres quelconques.

Mathématiquement, un labyrinthe parfait est un **arbre couvrant** de la grille de
cellules : toutes les cellules sont reliées, et aucune arête ne ferme de cycle. Pour
`n` couloirs par côté, cela fait `n²` sommets et `n² - 1` arêtes.

Les deux algorithmes ci-dessous construisent cet arbre de deux façons différentes.

## Vue d'ensemble

| | Recursive Backtracking | Kruskal |
|---|---|---|
| Famille | parcours en profondeur | arbre couvrant minimal |
| Structure auxiliaire | une pile | un Union-Find |
| Complexité temps | `O(n²)` | `O(n²·α(n))` |
| Complexité mémoire | `O(n²)` | `O(n²)` |
| Longueur du chemin entrée-sortie | `n^1,85` (mesuré) | `n^1,19` (mesuré) |
| Texture | longs couloirs sinueux | couloirs courts, nombreux culs-de-sac |

Les deux produisent un labyrinthe parfait. C'est leur **texture** qui diffère, et
c'est elle qui explique les écarts de performance des solveurs.

---

## Recursive Backtracking

### L'algorithme

1. Partir d'une cellule, la marquer visitée.
2. Choisir au hasard un voisin **non visité**, percer le mur, s'y déplacer.
3. Répéter depuis cette nouvelle cellule.
4. Si aucun voisin non visité n'existe, revenir en arrière jusqu'à en trouver une qui
   en a encore un.

### Pourquoi le résultat est un arbre

Chaque cellule est visitée **exactement une fois**, et on ne perce un mur que vers
une cellule non visitée. Chaque perçée relie donc deux cellules encore distinctes :
c'est la définition d'un arbre couvrant.

Le marquage `visited` suffit à garantir l'absence de cycle. Aucune structure de
détection n'est nécessaire — c'est ce qui rend cet algorithme simple.

### L'implémentation itérative

La profondeur de récursion atteint la longueur du chemin courant, qui croît comme
`n^1,8`. Elle dépasse la limite de 1000 appels de CPython **dès `n ≈ 45`**
(profondeur mesurée : 870 à `n = 40`, 1 346 à `n = 50`, 31 790 à `n = 300`).

On utilise donc une **pile explicite**, ce qui a l'avantage supplémentaire de rendre
la mémoire du parcours lisible et bornable.

```python
stack = [0]                      # index linéaire de (0, 0)
visited[0] = 1

while stack:
    idx = stack[-1]              # REGARDER le sommet, sans le dépiler
    r, c = divmod(idx, n)

    candidats = []               # (index du voisin, direction)
    for d in range(4):
        nr, nc = r + DR[d], c + DC[d]
        if 0 <= nr < n and 0 <= nc < n:
            nidx = nr * n + nc
            if not visited[nidx]:
                candidats.append((nidx, d))

    if candidats:
        nidx, d = candidats[rng.randrange(len(candidats))]
        percer(idx, nidx, d)
        visited[nidx] = 1
        stack.append(nidx)       # AVANCER
    else:
        stack.pop()              # RECULER
```

Trois points essentiels :

- **`stack[-1]` puis `pop()` conditionnel.** On ne dépile que lorsqu'il n'y a plus
  aucun voisin libre. C'est ce qui distingue « regarder » de « retirer ».
- **Le tirage se fait dans `candidats`**, jamais dans `range(4)`. `candidats` ne
  contient que des voisins valides et non visités : il y a donc exactement **un
  tirage par perçée**, soit `n² - 1` tirages au total.
- **On mémorise la direction `d`** avec l'index, ce qui évite de la recalculer au
  moment de percer.

### Percer le mur

Le mur à modifier dépend de la direction, et **ce n'est pas toujours celui de la
cellule courante** :

| Déplacement | Mur à percer |
|---|---|
| Est | mur **Est** de `(r, c)` |
| Sud | mur **Sud** de `(r, c)` |
| Ouest | mur **Est** de `(r, c-1)` |
| Nord | mur **Sud** de `(r-1, c)` |

Les deux dernières lignes découlent du codage : le mur Ouest de `(r, c)` *est* le mur
Est de sa voisine. Voir `02-grille.md`.

### Complexité

Chaque cellule est empilée une fois et dépilée au plus une fois : la boucle
s'exécute au plus `2n²` fois. Avec les quatre voisins examinés à chaque tour, on
reste en **`O(n²)`**, avec une constante faible.

---

## Kruskal

### L'algorithme

1. Chaque cellule est un sommet ; chaque paire de cellules voisines est une arête.
2. Affecter un poids **aléatoire** à chaque arête.
3. Trier les arêtes par poids croissant.
4. Les parcourir dans cet ordre : percer un passage **si et seulement si** les deux
   cellules ne sont pas déjà connectées.
5. S'arrêter à `n² - 1` arêtes acceptées.

C'est l'étape 4 qui construit l'arbre : accepter une arête entre deux cellules déjà
connectées fermerait un cycle.

### Union-Find

La question « ces deux cellules sont-elles déjà connectées ? » est posée `O(n²)`
fois. La structure adaptée est un **Union-Find**, avec deux opérations :

```python
def find(x):
    while parent[x] != x:
        parent[x] = parent[parent[x]]     # compression de chemin
        x = parent[x]
    return x

def union(a, b):
    ra, rb = find(a), find(b)
    if ra == rb:
        return False          # déjà connectées : l'arête fermerait un cycle
    if rank[ra] < rank[rb]:
        ra, rb = rb, ra
    parent[rb] = ra
    if rank[ra] == rank[rb]:
        rank[ra] += 1
    return True
```

Deux optimisations, et c'est elles qui font la complexité :

- **Compression de chemin** dans `find` : tous les nœuds traversés pointent ensuite
  directement vers la racine, ce qui aplatit l'arbre.
- **Union par rang** dans `union` : l'arbre le moins haut est accroché sous le plus
  haut, ce qui borne la hauteur à `O(log N)`.

Ensemble, elles donnent une complexité amortie de **`O(α(N))`** par opération, où
`α` est l'inverse de la fonction d'Ackermann. Cette fonction croît si lentement
qu'elle vaut moins de 5 pour toute taille réaliste : on peut la considérer comme
**quasi constante**.

Sans ces deux optimisations, `find` serait en `O(N)` et l'algorithme entier en
`O(n⁴)`.

### Représentation des arêtes

Il y a `2·n·(n-1)` arêtes, soit environ `2n²`. Deux représentations possibles :

| Représentation | Coût par arête | À `n = 10 000` |
|---|---:|---:|
| tuple `(r, c, sens)` | ~110 octets | ~22 Go |
| entier `int32` encodé | 4 octets | 800 Mo |

**Le code livré utilise la liste de tuples**, telle qu'écrite dans
[`kruskal.py`](../src/mazes/generators/kruskal.py) : c'est la forme la plus
directe, et la plus lisible.

> **Les deux variantes décrites sur cette page ne sont pas implémentées.** Ce
> document les a longtemps présentées au présent, comme si elles étaient en
> place — jusqu'à citer un appel à `rng.permuted_indices`, méthode qui n'existe
> pas dans `core/rng.py`. Les algorithmes de génération sont figés par la
> consigne : ils ne sont ni réécrits, ni remplacés, ni complétés. La mémoire
> réelle de Kruskal est donc celle des tuples.

Le coût mesuré est de **~110 octets par arête**, et non 80 : aux 64 octets du
tuple et 8 du pointeur s'ajoutent les entiers `r` et `c`, que CPython ne met en
cache qu'en dessous de 257. C'est cette mesure qui alimente le modèle de
`budget.py`.

**Conséquence directe :** Kruskal plafonne vers `n = 3 055` sous le budget par
défaut de 2 Gio, quand Prim monte à `n ≈ 28 714`. Le calcul est refusé **avant**
toute allocation, et un fichier de statistiques est écrit à la place —
voir [`README`](../README.md#refus-avant-calcul).

#### La variante par tableau d'entiers (non implémentée)

Si les algorithmes devaient être rouverts, voici la piste :

```python
m = n * (n - 1)                        # arêtes horizontales
aretes = permutation_aleatoire(2 * m)  # tableau numpy, int32

for e in aretes:
    if e < m:                          # arête horizontale
        r, c = divmod(e, n - 1)
        a, b, sens = r * n + c, r * n + c + 1, EAST
    else:                              # arête verticale
        r, c = divmod(e - m, n)
        a, b, sens = r * n + c, (r + 1) * n + c, SOUTH
    ...
```

`divmod` produit des entiers, qui sont des valeurs et non des références : la boucle
n'alloue aucun objet.

**Le gain est réel, mais bien plus modeste qu'il n'y paraît.** Les arêtes ne sont
pas le seul poste de dépense. Décomposition mesurée à `n = 1000` :

| Poste | Aujourd'hui | Arêtes en `int32` |
|---|---:|---:|
| Arêtes | 169 Mo (85 o/arête) | 8 Mo |
| Union-Find | 48 Mo | 48 Mo |
| Grille | 0,25 Mo | 0,25 Mo |
| **Total** | **217 Mo** | **56 Mo** |
| **Plafond sous 2 Gio** | **`n ≈ 3 055`** | **`n ≈ 6 200`** |

Le Union-Find coûte **48 octets par cellule** — `list(range(n²))`, donc un objet
entier par cellule, plus la liste de rangs. Dès que les arêtes deviennent
compactes, il pèse 85 % du total et prend le relais comme goulot d'étranglement :
**le plafond double, il ne décuple pas.** C'est le genre d'estimation qu'on ne
peut faire sérieusement qu'en mesurant poste par poste.

Le compacter lui aussi (`array("i")` au lieu d'une liste) ramènerait le total à
~16 o/cellule, soit `n ≈ 11 500` — mais il faudrait alors toucher à
`core/unionfind.py`, une structure partagée avec le reste du projet.

**Décision : ne pas le faire.** Les algorithmes sont figés par la consigne, et
leurs structures de données en font partie. Un gain de ×2 sur le plafond ne
justifie pas de sortir du périmètre autorisé — d'autant que `prim`, avec la même
interface et le même algorithme figé, atteint déjà `n ≈ 28 714`.

### Le mode par tirage (non implémenté)

Au-delà d'une certaine taille, même le tableau d'`int32` deviendrait trop gros
(80 Go à `n = 100 000`). On pourrait alors supprimer complètement le tableau et
tirer les arêtes une par une :

```python
acceptees = 0
while acceptees < n * n - 1:
    a, b, sens = tirer_une_arete_aleatoire()
    if union(a, b):
        percer(a, sens)
        acceptees += 1
```

**Distribution identique.** Kruskal avec des poids i.i.d. uniformes est équivalent à
parcourir les arêtes dans un ordre aléatoire uniforme. Tirer avec remise et rejeter
une arête dont l'union échoue revient au même, car une arête rejetée le reste pour
toujours : si deux cellules sont dans la même composante, elles y restent — les
composantes ne se scindent jamais.

**Coût en tirages.** Il n'est pas de `n² - 1`, mais de `Θ(n²·log n²)`. Pour que le
labyrinthe soit connexe, il faut que **chaque cellule** ait été touchée par au moins
une arête tirée, sans quoi elle resterait isolée. C'est un problème de collecteur de
vignettes : avec `n²` vignettes couvertes deux par deux à chaque tirage, il faut
`n²·ln(n²)` tirages.

Mesures (le rapport à `n²·ln(n²)` décroît vers 0,5, la constante attendue) :

| `n` | Tirages | Ratio / cellules | / `n²·ln(n²)` |
|---:|---:|---:|---:|
| 25 | 2 943 | 4,7 | 0,73 |
| 100 | 56 868 | 5,7 | 0,62 |
| 200 | 207 661 | 5,2 | 0,49 |

**Bilan :** ce mode économise la mémoire, pas le temps. Il est même plus lent que le
mode trié sur les tailles où les deux sont possibles.

### Complexité

| Mode | Temps | Mémoire |
|---|---|---|
| tri par poids des arêtes | `O(n² log n)` | `O(n²)` |
| permutation aléatoire | `O(n²·α(n))` | `O(n²)` |
| tirage avec rejet | `O(n² log n)` | `O(n²)` |

La distinction entre les deux premières lignes compte : `O(n²·α(n))` suppose que
l'ordre des arêtes est une **permutation aléatoire**, qu'obtenir par un tri par poids
coûte un facteur `log` supplémentaire.

---

## Budget mémoire

Les trois générateurs n'ont pas le même appétit. `kruskal.py` construit la liste
de toutes ses arêtes avant d'en abattre une seule : à `n = 100000` cela fait
20 milliards de tuples, soit ~2 Tio, et le processus meurt en `MemoryError` après
plusieurs minutes.

`budget.py` estime l'empreinte à partir du seul `n`, avant toute allocation.
Chaque générateur a son modèle `a·n² + b·n + c`, calé sur des mesures
`tracemalloc` :

| Générateur | Modèle | Mesures | `n = 1 000` | `n = 100 000` |
|---|---|---:|---:|---:|
| `kruskal` | `230·n²` | 208 → 218 o/cellule de `n`=500 à 1200 | 230 Mio | **~2,1 Tio** |
| `recursive_backtracking` | `30·n²` | 23 → 28 o/cellule | 30 Mio | ~280 Gio |
| `prim` | `2,5·n² + 3000·n` | 4,4 → 1,9 o/cellule de `n`=500 à 3000 | 5,5 Mio | ~25 Gio |

Trois choses expliquent ces écarts :

* Kruskal paie ses arêtes, et le coût par arête croît même avec `n` : les
  entiers `(r, c)` sortent du cache de CPython au-delà de 257.
* Prim et recursive_backtracking ne paient qu'un `bytearray(n*n)`, soit 1 octet
  par cellule. Prim y ajoute une frontière en `O(n)`, qui se dilue quand `n`
  grandit, d'où un coût par cellule qui décroît.
* recursive_backtracking garde en plus sa pile, c'est-à-dire le chemin courant :
  des tuples de deux entiers, donc ~25 octets par cellule.

Les modèles majorent les mesures, volontairement. Surestimer refuse un calcul qui
aurait tenu, ce que l'utilisateur peut corriger en relevant le budget ;
sous-estimer tue le processus sans rien produire. Le test
`test_budget.py::TestLeModeleMajoreLaMesure` recoupe chaque prédiction contre un
pic réellement mesuré : si un générateur changeait de structure de données, il
échouerait.

### Le budget, et comment le relever

`MEMORY_BUDGET` vaut 2 Gio par défaut. `MAZES_MEMORY_BUDGET` le
remplace, en octets, et il est relu à chaque appel :

```bash
MAZES_MEMORY_BUDGET=34359738368 mazes run --n 100000 --generator prim
```

Ce que chaque générateur atteint, selon le budget :

| Générateur | 2 Gio (défaut) | 32 Gio | 256 Gio |
|---|---:|---:|---:|
| `kruskal` | `n ≈ 3 055` | `n ≈ 12 222` | `n ≈ 34 570` |
| `recursive_backtracking` | `n ≈ 8 460` | `n ≈ 33 842` | `n ≈ 95 721` |
| `prim` | `n ≈ 28 714` | `n ≈ 116 635` | `n ≈ 330 989` |

### Ce qui se passe en cas de dépassement

Le calcul n'est pas lancé. Le CLI refuse, explique, et écrit un fichier de
statistiques à la place :

```
Génération refusée : kruskal demanderait 2.1 Tio pour n=100000, au-delà du budget de 2.0 Gio.
Aucun générateur ne passe a cette taille. Relever MAZES_MEMORY_BUDGET, ou reduire --n.
```

À une taille où un générateur moins gourmand suffit, le message le nomme :

```
Génération refusée : kruskal demanderait 5.4 Gio pour n=5000, au-delà du budget de 2.0 Gio.
Essayer un générateur plus sobre : prim, recursive_backtracking. Relever MAZES_MEMORY_BUDGET, ou reduire --n.
```

Le code de retour est `1`, et il n'y a **pas de traceback**. Voir
[`README`](../README.md#refus-avant-calcul) pour le format du fichier écrit.

> **Ce que ce garde-fou ne fait pas.** Il ne rend pas `n = 1000000` possible.
> Même à 256 Go de budget, `prim` plafonne vers `n ≈ 331 000` : au-delà, c'est la
> taille du résultat qui dépasse, pas le générateur. La grille seule pèse `n²/4`
> octets, soit 250 Go à `n = 1000000`.

## Vérifier un générateur

Quel que soit l'algorithme, le contrôle est le même :

```python
from mazes.core import is_perfect, count_open_passages, UnionFind

grille = generateur.generate(n, rng)
assert is_perfect(grille)                        # connexe et sans boucle
assert count_open_passages(grille) == n*n - 1    # exactement n²-1 passages
```

Et pour Kruskal, un invariant interne encore plus direct :

```python
assert uf.n_merges == n*n - 1    # n²-1 fusions réussies, ni plus ni moins
```

Vérifier ces deux assertions sur les **petites tailles** (1, 2, 3, 5, 8) est le
meilleur investissement : c'est là que les cas limites se manifestent, et le
résultat y est assez petit pour être dessiné à la main.
