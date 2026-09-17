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
| **Générateurs** | Kruskal, Prim, dijkstra | Rayene |
| **Solveurs** | Recursive Backtracking, A\* | Manon |
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
| 1 000 | 2 001 × 2 001 | ~4 Mo | oui |
| 10 000 | 20 001 × 20 001 | ~400 Mo | oui, lent |
| 100 000 | 200 001 × 200 001 | ~40 Go | **non** |

Deux verrous : le disque, et le format JPEG (plafonné à 65 535 px de côté).

L'architecture répond en **séparant le stockage du rendu** : le labyrinthe vit en
mémoire à 2 bits par cellule (`n²/4` octets, soit 2,5 Go à `n = 100000`), et
l'export est une projection décidée par une `ExportPolicy`.

> Deux axes à ne pas confondre. `n = 100000` **passe l'échelle en mémoire** (2,5 Go),
> mais **pas en temps** : environ `10¹⁰` cellules à parcourir, soit des heures de
> calcul en Python pur. Voir [`doc/README.md`](doc/README.md).

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
**solveurs** (`astar`, `recursive_backtracking`), avec leur description et leur
complexité.

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

### 3. Pipeline complet en une commande

Générer avec **Kruskal** puis résoudre avec **A\*** en une seule commande :

```bash
mazes run --n 30 --generator kruskal --solver astar
```

Les **deux** algorithmes sont explicites ici : `--generator` choisit l'algorithme
de génération, `--solver` l'algorithme de résolution. La commande produit les
mêmes deux fichiers (ASCII + JPEG), nommés `outputs/<générateur>_<solveur>_<n>`.

### Convertir un labyrinthe ASCII en image

Convertir un fichier ASCII en image **JPEG** :

```bash
mazes convert --input outputs/maze_kruskal_30.txt --output outputs/maze_kruskal_30.jpg
```

### Comparer et analyser les solveurs

Le benchmark résout tous les labyrinthes déjà générés dans `outputs/` et écrit un
compte rendu lisible dans `outputs/benchmark.md` :

```bash
python benchmarks/scaling.py
```

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
│   ├── rendering/            ASCII, image, politique d'export
│   ├── metrics.py            chronométrage, mesure mémoire
│   └── cli.py                ligne de commande
├── tests/                    test_solvers.py, test_generators.py, test_cli.py,
│                             test_lecture_ascii.py, test_rendering.py
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
| [04 — Solveurs](doc/04-solveurs.md) | théorie de backtracking et A\*, marquage `o` / `*` |
| [05 — Export](doc/05-export.md) | écrire en ASCII et en image |
