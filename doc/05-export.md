# 05 — Export

Écrire un labyrinthe dans un fichier, avec ou sans son parcours.

## ASCII

```python
from mazes.rendering import write_ascii, read_ascii

# labyrinthe seul
write_ascii(grille, "labyrinthe.txt")

# labyrinthe + parcours (o et *)
write_ascii(grille, "resolution.txt", state=resultat.state)

# relecture
grille = read_ascii("labyrinthe.txt")
```

L'écriture se fait **ligne par ligne**, jamais en assemblant la grille entière : à
`n = 10 000`, une chaîne complète ferait 400 Mo. Les fichiers sont écrits en binaire
avec des `\n` explicites, donc identiques octet pour octet sur toutes les plateformes.

Le format exact est décrit dans `02-grille.md`.

## Image

```python
from mazes.rendering import write_image

write_image(grille, "labyrinthe.jpg", state=resultat.state)
```

La chaîne de traitement :

```
WallGrid (bits)  ->  matrice dense uint8  ->  réduction  ->  Pillow
```

Le développement en matrice dense est **entièrement vectorisé** (quatre affectations
par tranches numpy), ce qui remplace `(2n+1)²` itérations de boucle Python.

## Couleur

L'image est **toujours en couleur** (mode `"RGB"`). Par défaut :

| Élément | Couleur |
|---|---|
| Murs | noir `(0, 0, 0)` |
| Cellules libres | blanc `(255, 255, 255)` |
| **Chemin** | **rouge `(220, 20, 60)`** |
| **Explorées** | **bleu clair `(173, 216, 230)`** |

**Pourquoi ces teintes.** Le rouge pour le chemin, parce que c'est le résultat —
la seule chose qui doive ressortir au premier coup d'œil. Le bleu clair pour les
cellules explorées puis abandonnées, une teinte froide qui se lit comme « travail
dépensé pour rien » sans concurrencer le rouge. Le contraste rouge / bleu reste
distinguable en cas de daltonisme rouge-vert, contrairement à un couple
rouge / vert.

### Personnaliser

`ImageStyle` accepte un **triplet RGB**, ou un **entier** par commodité (étalé sur
les trois canaux : `200` devient le gris `(200, 200, 200)`) :

```python
from mazes.rendering import ImageStyle, write_image

mon_style = ImageStyle(
    wall=(30, 30, 30),           # gris anthracite
    free=(255, 255, 255),
    path=(0, 160, 70),           # vert
    explored=200,                # un entier : gris clair
)
write_image(grille, "solution.jpg", state=resultat.state, style=mon_style)
```

Une couleur malformée est refusée **à la construction de la palette**, et non
silencieusement ignorée : une composante hors de `0..255` ou un triplet de deux
éléments lève une `ValueError` qui dit laquelle.

> **JPEG et couleur.** Par défaut le JPEG réduit de moitié la résolution des
> couleurs (sous-échantillonnage 4:2:0) : deux pixels voisins partagent leur
> chrominance. Sur un labyrinthe, où un chemin rouge touche un mur noir sur un
> seul pixel, cela fait baver un liseré coloré le long des murs. `write_image`
> impose donc 4:4:4 — le fichier est plus gros, mais net.

Le JPEG est **avec perte** : sur une image à fort contraste comme un labyrinthe,
il introduit un halo autour des murs qui peut rendre un couloir d'un pixel
difficile à lire. C'est le format demandé par l'énoncé, adapté à l'insertion dans
un rapport.

## La question de la taille

L'export 1:1 devient impossible au-delà d'un certain point, pour deux raisons
physiques :

| `n` | Grille ASCII | Fichier | Verdict |
|---:|---:|---:|---|
| 1 000 | 2 001 × 2 001 | ~4 Mo | confortable |
| 10 000 | 20 001 × 20 001 | ~400 Mo | pénible |
| 100 000 | 200 001 × 200 001 | **~40 Go** | impossible |

1. **Le disque** — 40 Go pour un seul fichier.
2. **Le format JPEG** — la norme plafonne chaque dimension à 65 535 pixels. Une image
   de 200 001 pixels de côté n'est pas représentable.

`ExportPolicy` décide donc, **avant** de lancer le calcul, ce qui peut être écrit :

```python
from mazes.rendering import ExportPolicy

plan = ExportPolicy().plan(n)
print(plan.describe())
```

Le facteur de réduction est le plus petit `k` tel que la grille réduite tienne sous la
limite : `k = ceil(côté / limite)`.

La réduction se fait par **minimum de bloc**, et non par moyenne : dans un labyrinthe,
un couloir d'un pixel entouré de murs disparaîtrait au moyennage. Le minimum signifie
« au moins un passage dans cette zone », ce qui préserve la structure.

Au-delà du seuil, un **fichier de statistiques** prend le relais pour qu'une sortie
existe toujours :

```
labyrinthe_statistiques
n: 100000
cellules: 10000000000
passages: 9999999999
chemin_longueur: 1780000
export_ascii: refuse
export_ascii_raison: ASCII 1:1 ferait 40.0 Gio (limite 64 Mio)
export_image: reduite x7 -> 28571x28571
```

## Rappel sur les limites de Pillow

Pillow applique une protection anti-« bombe de décompression » à deux seuils :

| Pixels | Comportement |
|---:|---|
| > 89 478 485 (~89,5 M) | `DecompressionBombWarning` |
| > 178 956 970 (~179 M) | `DecompressionBombError` |

Le seuil d'avertissement correspond à `n ≈ 4 700`, bien en dessous de ce que ce projet
produit légitimement : la protection doit être désactivée explicitement, avec un
commentaire qui le justifie.
