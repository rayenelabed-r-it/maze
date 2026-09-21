# 02 — La grille

`WallGrid` est la structure pivot du projet : générateurs, solveurs et rendus ne
communiquent jamais directement, seulement à travers elle. C'est ce qui permet à ton
solveur d'accepter indifféremment une grille produite par ta collègue ou relue
depuis un fichier ASCII.

## Géométrie

`n` est le nombre de couloirs **par côté**. La grille de cellules est donc `n × n`,
et son affichage fait `(2n + 1) × (2n + 1)` caractères. Une cellule `(r, c)` occupe
la position `(2r + 1, 2c + 1)` de l'affichage ; les positions paires portent les murs.

Coordonnées : `(ligne, colonne)`, indices à partir de 0. **`(0, 0)` est en haut à
gauche**, la ligne croît vers le bas. Entrée en `(0, 0)`, sortie en `(n-1, n-1)`.

## Le codage : 2 bits par cellule

Ce qui définit un labyrinthe, ce sont ses **murs**. Et il n'y a que deux murs à
stocker par cellule :

- le mur **Est**, entre `(r, c)` et `(r, c+1)` ;
- le mur **Sud**, entre `(r, c)` et `(r+1, c)`.

Le mur Nord de `(r, c)` est le mur Sud de `(r-1, c)` ; son mur Ouest est le mur Est
de `(r, c-1)`. Les stocker deux fois serait redondant, et surtout deux sources de
vérité qui pourraient diverger.

Un mur tient sur **un bit** : `1` = mur présent, `0` = passage ouvert.

```
2 × n²  bits  =  n² / 4  octets
```

En Python, deux `bytearray` :

```python
n_bytes = (n * n + 7) // 8
east  = bytearray([0xFF]) * n_bytes   # n² bits, un par cellule
south = bytearray([0xFF]) * n_bytes   # n² bits, un par cellule
```

Valeurs initiales à `0xFF` : toutes les cellules sont séparées par des murs. C'est
l'état de départ des générateurs, qui percent ensuite des passages.

### Ce que cela économise

| `n` | Cellules | `WallGrid` | Matrice `uint8` | Liste de listes |
|---:|---:|---:|---:|---:|
| 1 000 | 1 000 000 | **250 Ko** | 4 Mo | 32 Mo |
| 10 000 | 100 000 000 | **25 Mo** | 400 Mo | 3,2 Go |
| 100 000 | 10 000 000 000 | **2,5 Go** | 40 Go | 320 Go |

Le facteur est **16** face à une matrice d'octets, et **128** face à une liste de
listes — parce qu'une liste Python stocke des pointeurs de 8 octets, pas des valeurs.

Cette différence est ce qui permet de résoudre un labyrinthe de `n = 100000` : la
grille tient en mémoire, la version dense non.

## Accéder à un bit

L'index linéaire d'une cellule `(r, c)` est `r * n + c`. Le bit correspondant :

```python
idx   = r * n + c
octet = idx >> 3        # idx // 8
bit   = idx & 7         # idx % 8

mur_present = (mask[octet] >> bit) & 1
```

Percer un mur :

```python
mask[octet] &= ~(1 << bit)
```

Ces opérations sont le cœur de tous les algorithmes du projet. Elles s'exécutent
`O(n²)` fois, d'où deux habitudes :

- **lier les tampons à des variables locales** avant une boucle chaude
  (`east, n_loc = grid.east, grid.n`) ;
- **utiliser l'index linéaire** `r * n + c` plutôt qu'un tuple `(r, c)` : un `int`
  au lieu d'un objet, et `divmod(idx, n)` redonne `(r, c)` en une opération.

`WallGrid` expose pour cela `east` et `south` comme attributs publics : les méthodes
(`has_wall`, `carve`) sont là pour la lisibilité hors des boucles chaudes.

## Lire un fichier ASCII

C'est le point d'entrée de ta partie. Un fichier produit par un générateur se relit
avec :

```python
from mazes.rendering import read_ascii

grille = read_ascii("outputs/kruskal_1000.txt")
```

La lecture reconstruit les deux tampons de murs à partir des caractères :

| Position dans le texte | Contenu | Ce qu'on en déduit |
|---|---|---|
| `(2r, 2c)` | coin, toujours `#` | rien — sert de contrôle |
| `(2r, 2c+1)` | mur horizontal | mur **Sud** de `(r-1, c)` |
| `(2r+1, 2c)` | mur vertical | mur **Est** de `(r, c-1)` |
| `(2r+1, 2c+1)` | la cellule | rien — un mur ne s'y trouve jamais |

Deux points de vigilance, qui sont la source d'erreur principale de cette étape :

- **Le décalage des bords.** Les murs du bord supérieur et du bord gauche
  n'appartiennent à aucune cellule : ce sont les ouvertures d'entrée et de sortie,
  stockées dans `entry_open` et `exit_open`. Il faut donc ignorer la première ligne
  et la première colonne, pas les décaler.
- **Les caractères `o` et `*`.** Un fichier de résolution contient un parcours. À la
  relecture, `o` et `*` sont traités comme des cellules libres — ils décrivent un
  parcours, pas la structure du labyrinthe.

### Écrire un fichier ASCII

```python
from mazes.rendering import write_ascii

write_ascii(grille, "sortie.txt", state=resultat.state)
```

Le paramètre `state` est le masque d'état produit par un solveur : les cellules du
chemin deviennent `o` et les cellules explorées deviennent `*`. C'est ainsi que le
fichier de sortie contient **le labyrinthe et son parcours**, comme demandé.

L'écriture se fait ligne par ligne, jamais en assemblant la grille entière : à
`n = 10 000`, une chaîne complète ferait 400 Mo.

## Format exact d'un rendu

Pour `n = 3`, avec l'entrée en haut à gauche et la sortie en bas à droite :

```
colonne     0  1  2  3  4  5  6
ligne 0     #  .  #  #  #  #  #    <- bord supérieur, entrée percée en (0,1)
ligne 1     #  .  .  .  .  .  #    <- cellules (0,0) (0,1) (0,2)
ligne 2     #  #  #  #  #  .  #    <- mur entre (0,2) et (1,2), ouvert
ligne 3     #  .  .  .  .  .  #    <- cellules (1,0) (1,1) (1,2)
ligne 4     #  .  #  #  #  #  #    <- mur entre (1,0) et (2,0), ouvert
ligne 5     #  .  .  .  .  .  #    <- cellules (2,0) (2,1) (2,2)
ligne 6     #  #  #  #  #  .  #    <- bord inférieur, sortie percée en (6,5)
```

Contrôles à faire sur tout labyrinthe de test :

- **8 passages** attendus (9 cellules, donc `n² - 1`). On compte les `.` en position
  de mur : 2 + 1 + 2 + 1 + 2 = **8**.
- **Connexité** : le chemin
  `(0,0) → (0,1) → (0,2) → (1,2) → (1,1) → (1,0) → (2,0) → (2,1) → (2,2)`
  traverse les 9 cellules.
- **Bords** : une seule ouverture en haut, une seule en bas, aucune sur les côtés.

## Vérifier une grille

```python
from mazes.core import is_perfect, count_open_passages

assert is_perfect(grille)                        # connexe et sans boucle
assert count_open_passages(grille) == n*n - 1    # exactement n²-1 passages
```

Ces deux assertions suffisent à valider n'importe quelle grille, d'où qu'elle
vienne.
