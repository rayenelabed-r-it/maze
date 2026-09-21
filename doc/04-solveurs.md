# 04 — Solveurs

Ta partie. Trois algorithmes de recherche, trois stratégies, un même résultat.

| | Recursive Backtracking | A\* | Dijkstra |
|---|---|---|---|
| Type | exploration non informée | exploration informée | exploration non informée |
| Structure | pile (LIFO) | file de priorité (tas) | file de priorité (tas) |
| Heuristique | aucune | distance de Manhattan | aucune |
| Complexité temps | `O(n²)` | `O(n² log n)` | `O(n² log n)` |
| Complexité mémoire | `O(n²)` | `O(n²)` + le tas | `O(n²)` + le tas |
| Chemin trouvé | l'unique chemin | l'unique chemin | l'unique chemin |

## Le chemin est unique

Dans un labyrinthe parfait, il existe **exactement un chemin** entre l'entrée et la
sortie. Les trois solveurs renvoient donc nécessairement la même liste de cellules.

Ce qui les distingue n'est pas le **résultat**, mais le **coût** pour y parvenir :
combien de cellules ont été développées, combien de mémoire a été mobilisée, combien
de temps cela a pris.

C'est ce qui rend ces algorithmes faciles à vérifier : au lieu de démontrer une
propriété d'optimalité, on compare à un **parcours en largeur** (BFS) dont la
correction est établie. Toute divergence est un bug.

> **Nuance à écrire dans le rapport.** Le backtracking n'est *pas* optimal au sens général :
> sur un graphe avec plusieurs chemins, il peut trouver un long détour. S'il est
> correct ici, c'est uniquement parce que le problème n'admet qu'une réponse. A\*,
> lui, est optimal *par construction* — grâce à son heuristique admissible.

---

## Recursive Backtracking

### L'algorithme

```
empiler start, marquer start comme « sur le chemin »
tant que la pile n'est pas vide:
    (r, c) = sommet de la pile        # regarder, sans dépiler
    si (r, c) == sortie:              # la pile EST le chemin
        terminer
    suivant = un voisin accessible non visité
    si suivant existe:
        marquer suivant, l'empiler    # avancer
    sinon:
        dépiler (r, c)                # reculer
        marquer (r, c) comme « exploré, hors chemin »
```

### La pile est le chemin

C'est la propriété la plus utile de cet algorithme, et elle simplifie le marquage.

Dans un parcours en profondeur, **la pile contient exactement le chemin courant** :
la suite des cellules par lesquelles on est passé pour arriver où l'on est. Le
marquage en découle directement :

| Événement | État de la cellule | Caractère |
|---|---|---|
| on empile | provisoirement sur le chemin | `o` |
| on dépile | abandonnée, hors du chemin final | `*` |
| on atteint la sortie | la pile entière est le chemin | `o` |

**Conséquence directe : le backtracking n'a pas besoin de table de parents.** A\* en a une
obligatoirement, et elle coûte `4n²` octets. Le backtracking économise cette allocation —
c'est un avantage mémoire réel, à mentionner dans la comparaison.

### Le masque d'état

Le rendu `o` / `*` est piloté par un `bytearray` de `n²` octets :

```python
UNVISITED = 0    # -> '.'
EXPLORED  = 1    # -> '*'
ON_PATH   = 2    # -> 'o'

state = bytearray(n * n)     # tout à UNVISITED
```

```python
stack = [start]
state[start] = ON_PATH

while stack:
    idx = stack[-1]
    if idx == goal:
        return SolveResult(path=list(stack), state=state, ...)

    r, c = divmod(idx, n)
    suivant = -1
    for d in range(4):
        nr, nc = r + DR[d], c + DC[d]
        if 0 <= nr < n and 0 <= nc < n:
            nidx = nr * n + nc
            if state[nidx] == UNVISITED and passage_ouvert(idx, nidx, d):
                suivant = nidx
                break

    if suivant >= 0:
        state[suivant] = ON_PATH
        stack.append(suivant)        # AVANCER
    else:
        stack.pop()
        state[idx] = EXPLORED        # '*'
```

Une cellule n'est marquée `EXPLORED` qu'au moment où elle est **dépilée** : tant
qu'elle est sur la pile, elle fait partie du chemin courant. Quand on atteint la
sortie, les cellules restées sur la pile sont exactement le chemin.

> `list(stack)` et non `stack` : sans la copie, vider la pile plus tard viderait
> aussi le chemin stocké dans le résultat.

### Complexité

Chaque cellule est empilée une fois et dépilée au plus une fois : la boucle
s'exécute au plus `2n²` fois, avec quatre voisins examinés à chaque tour. C'est
`O(n²)` en temps comme en mémoire.

En pratique, le backtracking développe **presque toutes** les cellules du labyrinthe. C'est
son point faible : à résultat identique, il ne fait pas mieux qu'un parcours
exhaustif.

---

## A\*

### L'algorithme

A\* développe en priorité la cellule qui minimise

```
f(n) = g(n) + h(n)
```

- `g(n)` : coût déjà payé depuis l'entrée, en nombre de déplacements ;
- `h(n)` : estimation du coût restant jusqu'à la sortie.

Tant que `h` est **admissible** — elle ne surestime jamais le coût réel — A\*
garantit de trouver un chemin de coût minimal.

### L'heuristique de Manhattan

```
h(n) = |r - goal_r| + |c - goal_c|
```

**Preuve d'admissibilité.** On ne se déplace qu'horizontalement ou verticalement, et
chaque déplacement change la distance de Manhattan d'**exactement 1**. Il faut donc
au moins `h(n)` déplacements pour atteindre la sortie, quel que soit le chemin. Donc
`h(n) ≤ coût réel` : l'heuristique ne surestime jamais.

Elle est aussi très rapide à calculer : deux soustractions, deux valeurs absolues,
une addition.

### Les trois heuristiques sont admissibles

Le code en fournit trois, pour l'analyse comparative. Une idée reçue mérite d'être
écartée tout de suite : **les trois sont admissibles** sur une grille à quatre
voisins. La chaîne d'inégalités le montre, avec `d` le nombre réel de déplacements :

```
max(|dr|, |dc|)  ≤  |dr| + |dc|  ≤  d
   Tchebychev        Manhattan
```

et l'arrondi vers le bas de la distance euclidienne minore lui aussi `d`. Vérifié
sur ce projet : **4 458 couples** (cellule, distance réelle) mesurés, aucune
surestimation pour aucune des trois.

Ce qui les sépare n'est donc pas la *correction* mais la **qualité** — autrement dit
à quel point elles sous-estiment :

| Entre `(0,0)` et `(10,10)` | Valeur | Distance réelle |
|---|---:|---:|
| Tchebychev | 10 | 20 |
| Euclidienne | 14 | 20 |
| **Manhattan** | **20** | 20 |

Plus `h` est grande sans dépasser `d`, plus elle informe la recherche. Manhattan est
la plus informative des trois, d'où son statut de défaut.

> **D'où vient la confusion.** L'affirmation classique « Manhattan n'est pas
> admissible » concerne les grilles à **huit** voisins : avec les diagonales, un
> déplacement change Manhattan de 2, et elle surestime alors le coût réel. Sur une
> grille à quatre voisins, c'est l'inverse : elle est la meilleure des trois.

C'est un bon point à mettre dans le rapport : à correction égale, la qualité de
l'heuristique se mesure directement en cellules développées.

### De quelle longueur de chemin parle-t-on ?

Avant de dire que `h` est faible, il faut savoir à quoi on la compare. **Le chemin
n'est pas en `O(n²)`**, contrairement à ce que la taille du labyrinthe suggère.

La longueur `L` du chemin entrée-sortie suit une loi de puissance `L ~ n^α`. Mesures
(pente ajustée en échelle log-log) :

| Générateur | `α` mesuré | Chemin à `n = 400` | `L / 2n` |
|---|---:|---:|---:|
| Kruskal | **1,19** | 3 017 | 3,8 |
| Recursive Backtracking | **1,85** | 43 541 | **54,4** |

Pour Kruskal, l'exposant mesuré est cohérent avec le `n^5/4 = n^1,25` **théorique**
de l'arbre couvrant uniforme. C'est un point de contrôle : l'implémentation reproduit
une loi connue.

**Mesurer cet exposant est un résultat à part entière du projet.** Il s'obtient en
traçant `L` en fonction de `n` en échelle log-log : la pente *est* `α`.

### L'heuristique devient aveugle

La distance de Manhattan vaut au plus `2n`. Le rapport `L / 2n` mesure donc à quel
point `h` sous-estime le coût réel :

- **Kruskal** : de 2,1 (`n = 25`) à 3,8 (`n = 400`) — sous-estimation modérée ;
- **Recursive Backtracking** : de 5,4 à **54,4** — la sous-estimation explose.

**Conséquence mesurée :** A\* développe une **médiane de 57 % à 65 %** des cellules.

**Mais la dispersion est le vrai enseignement.** Sur 10 graines par taille :

| `n` | Médiane A\* | Étendue A\* | Médiane backtracking | Étendue backtracking |
|---:|---:|---|---:|---|
| 25 | 61,7 % | 22 % – 86 % | 62,1 % | 32 % – 97 % |
| 100 | 56,9 % | 39 % – 99 % | 61,7 % | 33 % – 91 % |
| 200 | 65,1 % | 38 % – 95 % | 53,5 % | 28 % – 82 % |
| 400 | 62,9 % | 26 % – 100 % | 66,3 % | 19 % – 87 % |

L'écart-type entre graines va de **19 à 31 points de pourcentage**. Selon le
labyrinthe tiré, A\* explore le quart des cellules ou la quasi-totalité.

**Conséquence méthodologique :** comparer A\* et le backtracking sur leurs médianes
(57-65 % contre 53-74 %) est à la limite du bruit. Les deux se valent — et c'est
précisément la conclusion à présenter, pas un défaut de mesure. Une conclusion
tirée d'une seule graine n'aurait aucun sens.

> **Une heuristique admissible n'est pas pour autant une bonne heuristique.**
>
> L'admissibilité garantit la *correction*, pas l'*efficacité*.

### Nuance importante

Sur les labyrinthes de Kruskal, la sous-estimation n'est que d'un facteur 2 à 4 — et
pourtant A\* y explore **autant** que sur ceux de Recursive Backtracking (62,7 %
contre 61,9 % à `n = 200`).

**La faiblesse de l'heuristique n'explique donc pas tout.** Ce qui contraint vraiment
la recherche, c'est la structure du labyrinthe : un chemin unique, aucune alternative
à évaluer, aucune occasion d'élaguer. A\* ne peut pas faire mieux qu'un parcours quasi
exhaustif parce que l'**information n'existe pas** dans le problème.

C'est une conclusion plus intéressante — et plus honnête — que « l'heuristique est
trop faible ».

### Structure de données

Un tas (`heapq`) d'éléments à trois composantes :

```python
heapq.heappush(open_set, (f, -g, idx))
```

- `f` est la clé de priorité ;
- `-g` départage les ex æquo en faveur des plus profonds ;
- `idx` en dernier permet à `heapq` de comparer sans tomber sur deux éléments égaux.

Les trois composantes doivent rester comparables : des `int` ici, donc aucun problème.

> **Sur le départage.** En pathfinding sur grille, il est réputé spectaculaire. Ici,
> la mesure dit l'inverse : moins d'**un point de pourcentage** d'écart entre
> `"deeper"`, `"shallower"` et `"none"`, à comparer à un écart-type entre graines de
> 37 %. L'option est conservée parce qu'elle ne coûte rien et reste déterministe —
> ce qui compte pour la reproductibilité des mesures.

### Absence de « decrease-key »

`heapq` ne permet pas de diminuer la priorité d'un élément déjà présent. On utilise la
**suppression paresseuse** : quand on trouve un meilleur chemin vers une cellule déjà
dans le tas, on empile une seconde entrée, et on ignore l'ancienne quand elle ressort.

```python
f, _, idx = heapq.heappop(open_set)
if closed[idx]:
    continue          # entrée obsolète
closed[idx] = 1
```

Conséquence : le tas peut contenir plus de `n²` entrées. C'est la principale faiblesse
mémoire d'A\*, et elle se mesure avec `max_frontier`.

### Tables auxiliaires

| Table | Type | Taille | Rôle |
|---|---|---|---|
| `g` | `array("i")` | `4n²` octets | coût depuis l'entrée |
| `parents` | `array("i")` | `4n²` octets | reconstruction du chemin |
| `closed` | `bytearray` | `n²` octets | cellules définitivement développées |
| `state` | `bytearray` | `n²` octets | le rendu `o` / `*` |

`g` et `parents` utilisent `-1` comme sentinelle « non atteint ». Le test devient
donc :

```python
if g[nidx] < 0 or g_new < g[nidx]:
    ...
```

### Reconstruction du chemin

Contrairement au backtracking, la structure d'attente ne contient pas le chemin. Il se
reconstruit en remontant les **parents** depuis la sortie :

```python
chemin = []
x = goal
while x != start:
    chemin.append(divmod(x, n))
    x = parents[x]
chemin.append(divmod(start, n))
chemin.reverse()
```

Puis on reporte les états sur le masque, **dans cet ordre** :

```python
# 1. les cellules fermées sont des '*'
for idx in range(n * n):
    if closed[idx]:
        state[idx] = EXPLORED

# 2. le chemin écrase, en 'o'
for idx in chemin_indices:
    state[idx] = ON_PATH
```

L'ordre compte : une cellule du chemin ne doit jamais être présentée comme un
cul-de-sac exploré, même si A\* y est passé avant d'y revenir.

---

## Dijkstra

Dijkstra trouve le plus court chemin dans un graphe **pondéré** : à chaque étape
il finalise la cellule la plus proche de l'entrée, puis propage les distances
depuis elle. Aucune heuristique n'oriente la recherche — c'est l'équivalent d'un
A\* dont `h` vaudrait toujours 0.

### À coût uniforme, c'est un BFS qui paie un tas

Ici tous les couloirs coûtent 1. La file de priorité sort donc les cellules par
distance croissante, soit exactement l'ordre d'un **parcours en largeur**. Le
résultat est identique, cellule pour cellule — la vérification le confirme sur
toutes les tailles.

| | BFS | Dijkstra |
|---|---|---|
| Ordre de sortie | distance croissante | distance croissante |
| Structure | file FIFO | tas binaire |
| Coût par insertion | `O(1)` | `O(log n²)` |
| Chemin trouvé | le plus court | le plus court |

La file de priorité est donc ici un **FIFO déguisé**, qui paie `log n²` à chaque
insertion pour un ordre qu'une simple file donnerait gratuitement. C'est ce que
le benchmark mesure : le surcoût du tas, à algorithme par ailleurs équivalent.

### Pourquoi le garder

Dijkstra est la **référence aveugle** du projet. Le backtracking explore en
profondeur, A\* est guidé par son heuristique, Dijkstra n'a aucune information :
il avance par cercles concentriques autour de l'entrée, sans jamais tenir compte
de la position de la sortie.

Comparer A\* à Dijkstra isole donc ce que **l'heuristique apporte** : même
structure de données (un tas), même mécanique, la seule différence est `h`. C'est
la mesure la plus directe de la valeur de l'information.

> **Nuance à écrire dans le rapport.** Dijkstra ne serait réellement distinct d'un
> BFS que si les couloirs avaient des **coûts différents** — une case piège à 5,
> un raccourci à 1. Le BFS donnerait alors le chemin le plus court en *étapes*, et
> Dijkstra le moins *coûteux*. Cette grille n'expose pas ce cas : les deux
> algorithmes y sont interchangeables, et le benchmark le montre.

### Structure de données

Mêmes conventions qu'A\* : `distances` et `parents` en `array("i")` (4 octets par
cellule), `closed` en `bytearray`. `-1` sert de sentinelle « non atteint », car un
`array("i")` ne stocke pas l'infini.

Comme A\*, Dijkstra n'a pas de « decrease-key » : quand une distance s'améliore,
on empile une **nouvelle** entrée et on laisse l'ancienne devenir obsolète. Le
`closed` la rattrape à la sortie du tas. Le tas contient donc des doublons, et
`max_frontier` compte ces entrées, pas les cellules distinctes.

### Complexité

`O(n² log n)` en temps — chaque cellule sort une fois, et le tas coûte `log n²` —
et `O(n²)` en mémoire, comme A\*.

---

## Le marquage `o` / `*`

C'est la sortie demandée par l'énoncé, et la dernière étape de ta partie.

| Valeur | Constante | Caractère | Signification |
|---|---|---|---|
| 0 | `UNVISITED` | `.` ou `#` | jamais atteinte |
| 1 | `EXPLORED` | `*` | atteinte, puis abandonnée |
| 2 | `ON_PATH` | `o` | sur le chemin final |

Le masque fait exactement `n²` octets, indexé par `r * n + c` — le même index que la
grille de murs.

**Contrôle à faire sur toute résolution :** le fichier produit doit contenir **les
deux marqueurs**. Un rendu qui ne contient que des `o` signifie que rien n'a été
exploré en vain — ce qui est très suspect sur un labyrinthe parfait.

```python
from mazes.rendering import write_ascii
write_ascii(grille, "resolution.txt", state=resultat.state)
```

---

## Mesurer et comparer

Trois métriques, toutes dans `SolveResult` :

| Métrique | Champ | Ce qu'elle mesure |
|---|---|---|
| Cellules développées | `expanded` | **l'efficacité** de la recherche |
| Pic de la structure d'attente | `max_frontier` | **la mémoire** mobilisée |
| Durée | `elapsed_s` | le temps |

Et un indicateur dérivé qui résume la situation :

```python
efficacite = path_cost / expanded        # entre 0 et 1
```

Il vaut 1 pour un solveur qui ne développe que les cellules de son chemin, et tend
vers 0 pour un solveur qui explore tout.

**Reproductibilité.** Deux exécutions sur le même labyrinthe doivent donner le même
`expanded`. Pour A\*, cela vérifie indirectement que le départage est déterministe —
un ordre d'insertion non maîtrisé ferait varier la mesure d'un run à l'autre et
rendrait toute comparaison impossible.

**Plusieurs graines.** L'écart-type entre graines atteint 37 % à `n = 200`. Comparer
deux solveurs sur une seule graine ne mesure rien.

## Budget mémoire

`max_frontier` mesure la mémoire de la **structure d'attente**, mais il ne dit rien
de l'empreinte totale : les tables auxiliaires pèsent bien plus lourd. À `n = 100000`,
A\* demande ~112 Gio rien qu'en `array("i")` et `bytearray` -- de quoi tuer le
processus après plusieurs heures de génération.

Comme pour les générateurs, `budget.py` répond **avant** la moindre allocation.

| Solveur | Modèle | Mesures | `n = 1 000` | `n = 100 000` |
|---|---|---:|---:|---:|
| `astar` | `12·n²` | 11,05 → 10,16 o/cellule | 12 Mio | **~112 Gio** |
| `dijkstra` | `12·n²` | 10,51 → 10,12 o/cellule | 12 Mio | ~112 Gio |
| `recursive_backtracking` | `1,5·n² + 500·n` | 1,66 → 1,13 o/cellule | 2 Mio | ~15 Gio |

**Pourquoi A\* est dix fois plus gourmand** : il paie deux `array("i")` de `n²`
éléments (`g` et `parents`, 4 octets chacun) plus deux `bytearray` (`closed` et
`state`), soit 10 octets par cellule. Le backtracking, lui, se contente d'un
`bytearray` d'état et d'une pile qui reste courte devant `n²`.

### Générer ne suffit pas à résoudre

C'est le piège que le garde-fou de génération seul laissait passer. Sous 2 Gio :

| | Plafond |
|---|---:|
| Génération avec `prim` | `n ≈ 28 714` |
| Résolution avec `astar` | `n ≈ 13 377` |

Entre les deux, la commande générerait pendant des heures pour mourir ensuite dans
le solveur. `mazes run` vérifie donc **les deux phases avant la moindre
allocation**, et refuse en nommant la phase fautive :

```
$ mazes run --n 20000 --generator prim --solver astar
Résolution refusée : astar demanderait 4.5 Gio pour n=20000, au-delà du budget de 2.0 Gio.
Essayer un solveur plus sobre : recursive_backtracking. Relever MAZES_MEMORY_BUDGET, ou reduire --n.
```

Le message ne propose que des solveurs qui **passent réellement** : conseiller
« essayez un autre solveur » quand aucun ne tient serait une impasse de plus.

`MAZES_MEMORY_BUDGET` relève le plafond, en octets, pour les deux phases.
