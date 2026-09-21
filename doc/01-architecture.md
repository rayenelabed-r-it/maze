# 01 — Architecture

## Arborescence

```
Amazing-Mazes/
├── src/mazes/
│   ├── core/
│   │   ├── grid.py           WallGrid : la grille compacte, 2 bits/cellule
│   │   ├── unionfind.py      Union-Find, pour Kruskal
│   │   ├── rng.py            RandomSource : aléatoire reproductible
│   │   └── validation.py     is_perfect, BFS de référence, validate_path
│   ├── generators/
│   │   ├── base.py           interface Generator + registre
│   │   ├── recursive_backtracking.py
│   │   ├── kruskal.py
│   │   └── prim.py
│   ├── solvers/              <-- TA PARTIE
│   │   ├── base.py           interface Solver + SolveResult + registre
│   │   ├── recursive_backtracking.py
│   │   ├── astar.py
│   │   └── dijkstra.py
│   ├── rendering/
│   │   ├── ascii.py          <-- TA PARTIE : WallGrid <-> texte
│   │   ├── image.py          WallGrid <-> image (Pillow)
│   │   ├── policy.py         ExportPolicy : que peut-on écrire, à quelle taille
│   │   └── stats.py          fichier de statistiques (n, cellules, passages…)
│   ├── budget.py             budget memoire : peut-on seulement lancer ce calcul ?
│   ├── interaction.py        confirmation avant d'écrire un gros fichier
│   ├── metrics.py            chronométrage et mesure mémoire
│   └── cli.py                interface en ligne de commande
├── tests/                    tests de ta partie
├── benchmarks/scaling.py     <-- TA PARTIE : le benchmark, compare les solveurs
├── doc/                      cette documentation
└── outputs/                  fichiers produits (non versionnés)
```

## Le principe de dépendance

Une seule règle, et elle explique toute l'organisation :

> Les dépendances vont dans un seul sens, de la périphérie vers le cœur.

```
        cli.py
          │
    ┌─────┼───────┬────────┬────────┬─────────┐
    ▼     ▼       ▼        ▼        ▼         ▼
rendering benchmarks metrics budget interaction
    │          │        │        │    (feuilles : ne dépendent
    └──────────┼────────┴────────┘     d'aucun module)
               ▼
        generators / solvers
               │
               ▼
             core/            (ne dépend de rien)
```

Conséquences concrètes :

- **`core/` n'importe rien du projet.** `grid.py`, `unionfind.py`, `rng.py` et
  `validation.py` ne connaissent ni les générateurs, ni les solveurs, ni le rendu.
- **`generators/` et `solvers/` ne se connaissent pas** et ne connaissent pas le
  rendu. Ils manipulent seulement `WallGrid`.
- **`rendering/` ne connaît aucun algorithme.** Il affiche une grille et un masque
  d'état, rien de plus.
- **`interaction.py` n'importe rien du projet.** Poser une question ne doit
  dépendre ni du rendu ni des algorithmes -- et ce module touche à `stdin`, donc
  c'est aussi le plus facile à tester isolément.
- **`budget.py` n'importe rien du projet.** Il prédit l'empreinte des
  algorithmes sans les instancier -- générateurs comme solveurs -- ce qui lui
  permet de rester une feuille. C'est le seul module que `cli.py` consulte
  *avant* de construire une grille.
  Il vit à côté de `metrics.py`, et non dans `generators/` : il couvre les deux
  registres, et `recursive_backtracking` figure dans l'un **et** l'autre avec
  des empreintes distinctes (30 contre 1,5 o/cellule). Une table unique rangée
  chez l'un des deux écraserait le modèle de l'autre.

### Une convention qui rend le CLI testable

Les constantes de seuil (`CONFIRM_THRESHOLD_BYTES`, `STATS_ALWAYS_ABOVE`,
`MAX_ASCII_SIDE`…) sont lues **dans le corps des fonctions**, jamais en valeur par
défaut d'argument. Une constante en défaut serait liée à l'import : la patcher
après coup n'aurait plus aucun effet, et vérifier qu'un refus se produit
demanderait d'écrire des fichiers de plusieurs gigaoctets. Les tests s'appuient
donc sur `monkeypatch.setattr(module, "CONSTANTE", valeur)`.

`WallGrid` est donc le **carrefour unique** : tous les modules se parlent à travers
elle, jamais directement. C'est ce qui permet à ton solveur d'accepter indifféremment
une grille de ta collègue ou un fichier ASCII relu.

## Les interfaces

### `Generator`

```python
class Generator(ABC):
    name: str          # identifiant court, ex. "kruskal"
    description: str   # phrase lisible, affichée par « mazes list »
    complexity: str    # complexité théorique, reportée dans le rapport

    @abstractmethod
    def generate(self, n: int, rng: RandomSource) -> WallGrid: ...
```

### `Solver`

```python
class Solver(ABC):
    name: str
    description: str
    complexity: str
    optimal: bool

    @abstractmethod
    def solve(self, grid: WallGrid, start: Cell, goal: Cell) -> SolveResult: ...
```

### `SolveResult`

```python
@dataclass
class SolveResult:
    path: list[Cell]      # le chemin, de l'entrée à la sortie
    state: bytearray      # n² octets : 0 = non visité, 1 = exploré (*), 2 = chemin (o)
    expanded: int         # cellules développées  -> efficacité
    explored: int         # cellules atteintes
    max_frontier: int     # pic de la structure d'attente -> mémoire
    elapsed_s: float
    algorithm: str
```

`state` est **directement** ce que réclame l'énoncé : `2` devient `o`, `1` devient
`*`. Aucun re-encodage n'est nécessaire entre le solveur et le rendu.

## Le registre

Chaque module d'algorithme s'enregistre par décorateur :

```python
from mazes.solvers.base import Solver, register_solver

@register_solver
class MonSolveur(Solver):
    name = "mon_algo"
    description = "..."
    complexity = "O(...)"

    def solve(self, grid, start, goal):
        ...
```

Il devient **immédiatement** disponible dans `--algorithm`, dans la CLI et dans les
benchmarks, sans qu'aucun de ces fichiers ne soit modifié — parce que ni la CLI ni
les tests ne codent en dur la liste des algorithmes.

Deux garde-fous : un nom vide ou déjà pris lève une `ValueError` à l'import, et un nom
inconnu lève une `KeyError` dont le message **liste les noms valides**.

## Pourquoi un layout `src/`

Le code vit dans `src/mazes/` et non à la racine, pour trois raisons :

1. **Imports non ambigus.** Depuis la racine, `import mazes` pourrait charger le
   dossier `mazes/` du répertoire courant au lieu du paquet installé.
2. **Tests représentatifs.** Les tests s'exécutent contre le paquet installé
   (`pip install -e .`), donc une erreur de packaging est détectée.
3. **Configuration explicite.** `pyproject.toml` déclare où chercher les paquets. Le
   comportement ne dépend pas du répertoire depuis lequel on lance `pytest`.

## Commandes

```bash
pip install -r requirements-dev.txt
pip install -e .

mazes list                     # algorithmes disponibles
mazes generate --n 100 --algorithm kruskal
mazes solve --input maze.txt --algorithm astar
mazes convert --input maze.txt --output maze.jpg

pytest                         # tests
python benchmarks/scaling.py --sizes 100 500 1000
```
