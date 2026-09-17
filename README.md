# Amazing-Mazes

Génération et résolution de labyrinthes **parfaits** (connexes, sans cycle),
en Python, avec rendu ASCII et image, une CLI et un banc de mesure.

## Installation

```bash
python -m venv .venv && source .venv/bin/activate   # Windows : .venv\Scripts\activate
pip install -r requirements-dev.txt
pip install -e .
```

Python 3.10 minimum. Pillow n'est nécessaire que pour le rendu image ;
tout le reste fonctionne sans.

## Utilisation

```bash
mazes list                                   # algorithmes disponibles
mazes generate --n 20 --algorithm kruskal --seed 42 --check
mazes generate --n 500 --algorithm prim --image
mazes solve --n 20 --algorithm astar --seed 42
mazes solve --input outputs/maze_kruskal_20.txt --algorithm dijkstra --image
mazes convert --input outputs/maze_kruskal_20.txt --output outputs/maze.png
```

- `--seed` rend la génération **reproductible** : même graine, même labyrinthe.
- `--check` vérifie que le labyrinthe produit est bien parfait.
- Au-delà de n = 60, l'affichage terminal est remplacé par l'écriture d'un
  fichier dans `outputs/` (voir `rendering/policy.py`).

## Format ASCII

Grille de `2n+1` x `2n+1` caractères :

| caractère | sens |
|---|---|
| `#` | mur |
| (espace) | couloir |
| `*` | cellule explorée par le solveur |
| `o` | cellule du chemin solution |

L'entrée est percée au-dessus de la cellule `(0,0)`, la sortie sous
`(n-1, n-1)`. Un fichier écrit par `generate` peut être relu tel quel par
`solve --input`, marques `*` / `o` comprises (elles sont ignorées à la relecture).

## Algorithmes

### Générateurs

| nom | principe | complexité |
|---|---|---|
| `kruskal` | mélange de tous les murs, Union-Find pour éviter les cycles | ~O(n²) |
| `prim` | croissance depuis une cellule, tirage dans la frontière | O(n²) |
| `recursive_backtracking` | parcours en profondeur avec retour sur trace | O(n²) |

### Solveurs

| nom | principe | optimal |
|---|---|---|
| `astar` | A* + heuristique de Manhattan | oui |
| `dijkstra` | file de priorité, coût uniforme | oui |
| `recursive_backtracking` | profondeur avec retour sur trace | non garanti |

Dans un labyrinthe parfait il n'existe qu'**un seul** chemin simple entre deux
cellules : les trois solveurs renvoient donc la même longueur. La différence se
joue sur le nombre de cellules développées et sur la mémoire — c'est ce que
mesure le banc.

## Tests et mesures

```bash
pytest
python benchmarks/scaling.py --sizes 100 500 --repeat 3 --csv outputs/scaling.csv
```

Le banc produit, pour chaque couple générateur/solveur : temps, pic mémoire,
longueur du chemin, cellules développées et atteintes, pic de la frontière.
Chaque chemin est revalidé contre un BFS de référence (`core/validation.py`)
qui ne partage aucun code avec les solveurs.

## Organisation

Voir `doc/01-architecture.md`. En résumé : les dépendances vont de la
périphérie vers le cœur, `core/` n'importe rien du projet, et tous les modules
communiquent via `WallGrid`. Un algorithme s'ajoute en créant un fichier dans
`generators/` ou `solvers/` avec le décorateur `@register_generator` /
`@register_solver` : il apparaît aussitôt dans la CLI, les tests et le banc,
sans modifier aucun autre fichier.

## Ce qui a changé depuis les prototypes

Le code d'origine (Kruskal, Prim, Dijkstra, rendu Pillow) a été repris et
corrigé sur les points suivants :

- **Mémoire.** Les passages étaient stockés dans un `set` de tuples et le
  graphe d'adjacence reconstruit à chaque résolution. `WallGrid` utilise
  2 bits par cellule (250 Ko à n = 1000) et les voisins sont calculés à la volée.
- **Reproductibilité.** `random` global remplacé par `RandomSource(seed)`.
- **Robustesse de Dijkstra.** La reconstruction du chemin plantait par
  `KeyError` si l'arrivée était inatteignable ; elle renvoie maintenant un
  chemin vide, signalé proprement par la CLI.
- **Union-Find.** Ajout de l'union par rang en plus de la compression de chemin.
- **Prim.** `pop(index)` en O(k) remplacé par un échange-puis-pop en O(1).
- **Rendu image.** Un trait Pillow par mur (~2n² appels) remplacé par un
  remplissage par cellule, avec une politique d'export qui borne la taille.
- **Effets de bord.** Les scripts s'exécutaient au moment de l'import
  (génération et affichage d'un 100x100 en fin de fichier) ; tout passe
  désormais par la CLI.
