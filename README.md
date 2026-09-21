# Amazing-Mazes

Génération et résolution de **labyrinthes parfaits**, avec comparaison des
algorithmes.

Un labyrinthe *parfait* est un labyrinthe sans boucle : il existe exactement un
chemin entre deux cases libres quelconques. Mathématiquement, c'est un **arbre
couvrant** de la grille de cellules.

---

## La question du projet

> **Quel algorithme est le plus rapide, le plus efficace et le plus léger, pour
> chaque taille de labyrinthe ?**

Tout le reste est un moyen. La réponse est un tableau, et le protocole pour
l'obtenir est dans [`doc/README.md`](doc/README.md).

## Périmètre

| Rôle | Algorithmes | Qui |
|---|---|---|
| **Générateurs** | Recursive Backtracking | Angie |
| **Générateurs** | Kruskal, Prim | Rayene |
| **Solveurs** | Recursive Backtracking, A\* | Manon |
| **Solveurs** | Dijkstra | Rayene |
| **Lecture ASCII** | fichier texte → `WallGrid` | Manon |

Générateurs et solveurs passent par la même interface : ajouter un algorithme,
c'est créer une classe et l'enregistrer, sans toucher au reste.

## Cahier des charges

- Entrée : un entier naturel `n`, le **nombre de couloirs par côté**.
- Le labyrinthe est **carré**, de `n × n` couloirs.
- **Entrée** en haut à gauche, **sortie** en bas à droite.
- Représentation ASCII : `#` pour les murs, `.` pour les espaces libres.
- Résolution : `o` pour le chemin, `*` pour les cases explorées qui n'en font pas
  partie.
- Sortie : un fichier contenant le labyrinthe **et** son parcours, puis une image
  **JPEG**.

### Ce que « `n` couloirs par côté » implique

La grille ASCII fait `(2n+1) × (2n+1)` caractères :

| `n` | Grille ASCII | Fichier | Réalisable ? |
|---:|---:|---:|:---|
| 1 000 | 2 001 × 2 001 | ~3,8 Mio | oui |
| 10 000 | 20 001 × 20 001 | ~382 Mio | oui, lent |
| 100 000 | 200 001 × 200 001 | ~37 Gio | **non** |

Deux verrous à l'export : le disque, et le format JPEG (plafonné à 65 535 px de
côté). L'architecture y répond en **séparant le stockage du rendu** : le
labyrinthe vit en mémoire à 2 bits par cellule (`n²/4` octets, soit 2,5 Go à
`n = 100000`), et l'export est une projection décidée par une `ExportPolicy`.

**Mais la génération est le vrai verrou, et il est bien plus contraignant.** Le
stockage de la grille (2,5 Go) n'est qu'une pièce : les algorithmes de génération
ont besoin de structures bien plus grosses, proportionnelles au *nombre d'arêtes*
et non au nombre de cellules.

| Générateur | Modèle | `n = 1 000` | `n = 100 000` | Plafond sous 2 Gio |
|---|---|---:|---:|---:|
| `kruskal` | 230 o/cellule | 230 Mio | **~2,1 Tio** | `n ≈ 3 000` |
| `recursive_backtracking` | 30 o/cellule | 30 Mio | ~280 Gio | `n ≈ 8 500` |
| `prim` | 2,5 o/cellule + `O(n)` | 5,5 Mio | ~25 Gio | `n ≈ 28 700` |

Kruskal est de loin le plus gourmand : il construit la liste de **toutes** ses
arêtes avant d'en abattre une seule, et un tuple Python coûte ~110 octets là où
un entier `int32` en coûterait 4.

`mazes` ne laisse donc pas le calcul partir : le budget est vérifié **avant toute
allocation**, et un dépassement est refusé proprement (voir
[« Refus avant calcul »](#refus-avant-calcul)). À `n = 100000`, aucun générateur
ne passe sous 2 Gio.

> **`n = 1000000` reste hors de portée**, même sur une machine généreuse : la
> seule grille y pèse 250 Go, et le plus sobre des générateurs (`prim`) réclame
> `n²` octets rien que pour marquer ses cellules visitées, soit **1 To**. Le
> problème n'est pas le code mais la taille du résultat.

---

## Installation

```bash
pip install -r requirements-dev.txt
pip install -e .
```

## Utilisation

La consigne décrit un **pipeline en trois temps** : générer le labyrinthe avec
l'algorithme choisi, **le résoudre** avec l'algorithme choisi, puis **l'exporter
en JPEG**.

### Lister les algorithmes disponibles

```bash
mazes list
```

Affiche les **générateurs** (`kruskal`, `prim`, `recursive_backtracking`) et les
**solveurs** (`astar`, `dijkstra`, `recursive_backtracking`), avec leur description
et leur complexité.

### 1. Générer un labyrinthe

Générer un labyrinthe de 30 × 30 couloirs avec l'algorithme **Kruskal** :

```bash
mazes generate --n 30 --algorithm kruskal
```

Générer un labyrinthe avec l'algorithme **Recursive Backtracking** :

```bash
mazes generate --n 30 --algorithm recursive_backtracking
```

Générer un labyrinthe avec l'algorithme **Prim** :

```bash
mazes generate --n 30 --algorithm prim
```

Le labyrinthe est écrit en ASCII dans `outputs/maze_<algorithme>_<n>.txt`
(par exemple `outputs/maze_kruskal_30.txt`).

Options de `generate` :

| Option | Effet |
|---|---|
| `--output fichier.txt` | choisir le fichier de sortie |
| `--print` | afficher le labyrinthe dans le terminal |
| `--check` | vérifier que le labyrinthe est parfait avant de l'écrire |
| `--seed 42` | graine reproductible (génère toujours le même labyrinthe) |
| `--yes`, `-y` | enregistrer sans demander confirmation |
| `--stats-only` | n'écrire que le fichier de statistiques |

### 2. Résoudre un labyrinthe (généré au préalable)

Résoudre le labyrinthe généré ci-dessus avec l'algorithme **A\*** :

```bash
mazes solve --input outputs/maze_kruskal_30.txt --algorithm astar
```

Résoudre avec l'algorithme **Recursive Backtracking** :

```bash
mazes solve --input outputs/maze_kruskal_30.txt --algorithm recursive_backtracking
```

Cette commande écrit **deux fichiers** :

- le labyrinthe **et** son parcours en ASCII (`o` = chemin, `*` = cases
  explorées) : `outputs/solved_<solveur>_<n>.txt` ;
- l'image **JPEG** du parcours : `outputs/solved_<solveur>_<n>.jpg`.

Options de `solve` :

| Option | Effet |
|---|---|
| `--input labyrinthe.txt` | labyrinthe ASCII à résoudre |
| `--algorithm astar` | algorithme de résolution |
| `--output fichier` | choisir le nom de sortie (sans extension) |
| `--yes`, `-y` | enregistrer sans demander confirmation |
| `--stats-only` | n'écrire que le fichier de statistiques |

### 3. Pipeline complet en une commande

Générer avec **Kruskal** puis résoudre avec **A\*** en une seule commande :

```bash
mazes run --n 30 --generator kruskal --solver astar
```

Les **deux** algorithmes sont explicites ici : `--generator` choisit l'algorithme
de génération, `--solver` l'algorithme de résolution. La commande produit les
mêmes deux fichiers (ASCII + JPEG), nommés `outputs/<générateur>_<solveur>_<n>`.

Au-delà d'un côté de 2 000 caractères (`n ≈ 1000`), un fichier de statistiques
`<nom>_statistiques.txt` **s'ajoute** à ces deux sorties. Voir
[« Gros fichiers »](#gros-fichiers--confirmation) ci-dessous.

### Convertir un labyrinthe ASCII en image

Convertir un fichier ASCII en image **JPEG** :

```bash
mazes convert --input outputs/maze_kruskal_30.txt --output outputs/maze_kruskal_30.jpg
```

### Refus avant calcul

Un calcul hors budget n'est **pas lancé**. Le budget est vérifié avant la moindre
allocation, à partir du seul `n` :

```
$ mazes run --n 100000 --generator kruskal
Génération refusée : kruskal demanderait 2.1 Tio pour n=100000, au-delà du budget de 2.0 Gio.
Aucun générateur ne passe a cette taille. Relever MAZES_MEMORY_BUDGET, ou reduire --n.
statistiques : outputs/kruskal_astar_100000_statistiques.txt
```

À une taille où un générateur moins gourmand suffit, le message le nomme :

```
$ mazes run --n 5000 --generator kruskal
Génération refusée : kruskal demanderait 5.4 Gio pour n=5000, au-delà du budget de 2.0 Gio.
Essayer un générateur plus sobre : prim, recursive_backtracking. Relever MAZES_MEMORY_BUDGET, ou reduire --n.
```

La commande sort en **code 1** et écrit un fichier de statistiques à la place —
sans traceback, et en une fraction de seconde :

```
labyrinthe_statistiques
n: 100000
cellules: 10000000000
passages: inconnu
chemin_longueur: inconnu
generation: refusee
generation_raison: kruskal demanderait 2.1 Tio pour 10000000000 cellules (budget 2.0 Gio)
```

`MAZES_MEMORY_BUDGET` relève le plafond, en octets. C'est ce qui permet
d'exploiter une machine plus large sans toucher au code :

```bash
MAZES_MEMORY_BUDGET=34359738368 mazes run --n 100000 --generator prim
```

Ce que chaque générateur atteint, selon le budget :

| Générateur | 2 Gio (défaut) | 32 Gio | 256 Gio |
|---|---:|---:|---:|
| `kruskal` | `n ≈ 3 055` | `n ≈ 12 222` | `n ≈ 34 570` |
| `recursive_backtracking` | `n ≈ 8 460` | `n ≈ 33 842` | `n ≈ 95 721` |
| `prim` | `n ≈ 28 714` | `n ≈ 116 635` | `n ≈ 330 989` |

Même à 256 Go de budget, `prim` plafonne vers `n ≈ 331 000`. **`n = 1000000`
demanderait ~2,5 To** : ce n'est pas une limite de code, c'est la taille du
résultat.

### Résoudre coûte aussi

La génération n'est pas la seule phase à vérifier. Sous 2 Gio, `prim` génère
jusqu'à `n ≈ 28 714` mais `astar` ne résout que jusqu'à `n ≈ 13 377` : entre les
deux, la commande générerait pendant des heures pour mourir ensuite dans le
solveur.

| Solveur | 2 Gio (défaut) | 32 Gio | 256 Gio |
|---|---:|---:|---:|
| `astar` | `n ≈ 13 377` | `n ≈ 53 509` | `n ≈ 151 348` |
| `dijkstra` | `n ≈ 13 377` | `n ≈ 53 509` | `n ≈ 151 348` |
| `recursive_backtracking` | `n ≈ 37 670` | `n ≈ 151 182` | `n ≈ 427 912` |

`mazes run` vérifie donc **les deux phases avant la moindre allocation** :

```
$ mazes run --n 20000 --generator prim --solver astar
Résolution refusée : astar demanderait 4.5 Gio pour n=20000, au-delà du budget de 2.0 Gio.
Essayer un solveur plus sobre : recursive_backtracking. Relever MAZES_MEMORY_BUDGET, ou reduire --n.
```

Le message ne propose que des solveurs qui passent réellement : conseiller
« essayez un autre solveur » quand aucun ne tient serait une impasse de plus.

Le refus de génération sort en **code 1**, contrairement au refus d'export qui
sort en `0` : dans le second cas le labyrinthe existe et c'est un fichier qui
manque, dans le premier il n'y a aucun labyrinthe du tout.

### Gros fichiers : confirmation

Un labyrinthe de `n = 100000` produirait un ASCII de **~37 Gio**. `mazes` ne
l'écrit pas : au-delà de **8 000 caractères de côté**, l'ASCII 1:1 est refusé et
l'image est réduite pour rester sous la limite JPEG. Et au-delà de **256 Mio**
estimés, la commande demande son accord :

```
Le fichier image kruskal_astar_100000.jpg pèsera 350.3 Mio. Souhaites-tu l'enregistrer ? [o/N]
```

Le défaut est **non** : une touche Entrée accidentelle ne doit pas déclencher
l'écriture de plusieurs gigaoctets.

La question est posée sur le **terminal de contrôle**, donc `mazes run > log.txt`
l'affiche quand même ; `echo o | mazes run ...` fonctionne aussi. Sans aucun
terminal — CI, tâche planifiée, service — la politique s'applique seule : la
commande ne bloque jamais et ne remplit jamais le disque en silence.
`MAZES_NO_PROMPT=1` fait taire la question sans changer le reste.

Quand un fichier n'est pas écrit — refus de la politique ou réponse « non » — un
**fichier de statistiques** `_statistiques.txt` prend le relais, pour que la
génération laisse une trace :

```
labyrinthe_statistiques
n: 100000
cellules: 10000000000
passages: 9999999999
chemin_longueur: 1780000
export_ascii: refuse
export_ascii_raison: ASCII 1:1 impossible : la grille ferait 200001 x 200001 caracteres, soit 37.3 Gio (limite 8000 de cote) -- ASCII refuse plutot que reduit
export_image: reduite x7 -> 28571x28571
```

Répondre « non » n'est **pas** une erreur : le code de retour reste `0`. Le
détail du format et de la politique est dans [`doc/05-export.md`](doc/05-export.md).

### Comparer et analyser les solveurs

Le benchmark analyse tout ce que `outputs/` contient : les labyrinthes, qui sont
résolus et mesurés, et les fichiers de statistiques, qui sont listés avec le coût
estimé des tailles refusées. Il écrit `outputs/benchmark.md` et cinq figures.

```bash
python benchmarks/scaling.py                     # environ 8 min
python benchmarks/scaling.py --sizes 100 1000    # restreindre les tailles
python benchmarks/scaling.py --sans-courbes      # rapport seul
```

| Figure | Contenu |
|---|---|
| `courbes_kruskal.png` | les trois solveurs sur les labyrinthes Kruskal |
| `courbes_prim.png` | idem, Prim |
| `courbes_recursive_backtracking.png` | idem, Recursive Backtracking |
| `courbes_meilleurs.png` | le solveur le plus efficace de chaque générateur |

Chaque figure porte quatre panneaux : le temps et la mémoire, en échelle linéaire
et en log-log. L'échelle log-log sert à lire les exposants, une loi de puissance
y devenant une droite.

Le temps et la mémoire sont relevés dans deux passes séparées, parce que
`tracemalloc` ralentit le code mesuré. « Léger » désigne le pic mémoire réel et
non `max_frontier` : sur les 11 cas mesurés, les deux critères désignent deux
solveurs différents. Le détail est dans `outputs/benchmark.md`, section « Écart
entre la frontière et le pic mémoire ».

---

## Tests

```bash
pytest                    # suite complète
pytest -k masque          # un seul groupe
pytest -k solveur -x      # s'arrêter au premier échec
pytest --cov=mazes        # avec couverture
```

---

## Structure

```
Amazing-Mazes/
├── src/mazes/
│   ├── core/                 WallGrid, Union-Find, aléatoire, validation
│   ├── generators/           Recursive Backtracking, Kruskal, Prim
│   ├── solvers/              Recursive Backtracking, A*
│   ├── rendering/            ASCII, image, politique d'export, statistiques
│   ├── budget.py             budget mémoire des algorithmes, génération et résolution
│   ├── interaction.py        confirmation avant d'écrire un gros fichier
│   ├── metrics.py            chronométrage, mesure mémoire
│   └── cli.py                ligne de commande
├── tests/                    test_solvers.py, test_generators.py, test_cli.py,
│                             test_lecture_ascii.py, test_rendering.py,
│                             test_policy.py, test_stats.py, test_interaction.py,
│                             test_budget.py, test_metrics.py
├── benchmarks/scaling.py     le tableau comparatif
├── doc/
└── outputs/                  fichiers produits (non versionnés)
```

## Documentation

| Document | Contenu |
|---|---|
| [README](doc/README.md) | la question du projet, le protocole de mesure |
| [01 — Architecture](doc/01-architecture.md) | organisation du code, interfaces |
| [02 — La grille](doc/02-grille.md) | modèle 2 bits/cellule, lecture ASCII |
| [03 — Générateurs](doc/03-generateurs.md) | théorie de Recursive Backtracking et Kruskal |
| [04 — Solveurs](doc/04-solveurs.md) | théorie de backtracking, A\* et Dijkstra, marquage `o` / `*` |
| [05 — Export](doc/05-export.md) | écrire en ASCII et en image |
