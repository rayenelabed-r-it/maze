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
| tuple `(r, c, r2, c2)` | 72 octets + 8 de pointeur | ~16 Go |
| entier `int32` encodé | 4 octets | 800 Mo |

Le tuple Python est un objet : 40 octets d'en-tête plus 8 par élément. Le tableau
d'entiers est la seule option viable au-delà de `n ≈ 3 000`.

On numérote donc les arêtes et on les décode à la demande :

```python
m = n * (n - 1)                        # arêtes horizontales
aretes = rng.permuted_indices(2 * m)   # permutation numpy, int32

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

### Le mode par tirage

Au-delà d'une certaine taille, même le tableau d'`int32` devient trop gros
(80 Go à `n = 100 000`). On peut alors supprimer complètement le tableau et tirer
les arêtes une par une :

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
