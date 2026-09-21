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
| 1 000 | 2 001 × 2 001 | ~3,8 Mio | confortable |
| 10 000 | 20 001 × 20 001 | ~382 Mio | pénible |
| 100 000 | 200 001 × 200 001 | **~37 Gio** | impossible |

> **Unités binaires.** Tout le projet compte en `Kio`/`Mio`/`Gio` (1 Gio = 1 024 Mio),
> y compris `format_bytes`, qui produit les messages affichés à l'utilisateur.
> Annoncer « 40 Go » pour un fichier de 37,3 Gio serait deux nombres différents
> pour la même grandeur, dans le même programme.

1. **Le disque** — 37 Gio pour un seul fichier.
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

> **`ascii_subsample` n'est pas branché.** La politique sait calculer une
> réduction ASCII (`ascii_scale`), mais `write_ascii` n'a **pas** de paramètre
> d'échelle : aucun écrivain ne sait produire ce fichier réduit. L'option reste
> donc à `False`, et l'ASCII est *refusé* plutôt que réduit. La levée de cette
> limite demanderait `write_ascii(..., scale=k)`, un flux qui sous-échantillonne
> ligne par ligne.

### Le fichier de statistiques

Pour qu'une sortie existe toujours, `write_stats` produit un résumé texte :

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

Il est écrit dans trois cas :

1. **en complément** des sorties normales, dès que le côté dépasse
   `STATS_ALWAYS_ABOVE` (2 000, soit `n ≈ 1000`). Pour `n` entre 1 000 et 4 000,
   le `.txt`, le `.jpg` **et** le `_statistiques.txt` sont donc tous écrits — le
   fichier de statistiques *s'ajoute*, il ne remplace rien :
2. **à la place** d'une sortie qui n'a pas été produite, refusée par la
   politique ou par l'utilisateur ;
3. **à la place** d'un labyrinthe que le budget mémoire a empêché de générer
   (voir [`03-generateurs.md`](03-generateurs.md#budget-mémoire)).

`passages` compte les murs abattus, soit `n² - 1` pour un labyrinthe parfait. Le
comptage est vectorisé -- à `n = 100000` une boucle par cellule demanderait `10¹⁰`
itérations -- et il **corrige les bits de remplissage** du dernier octet de chaque
tampon. Ces bits valent toujours 1 (voir `02-grille.md`) : les compter comme des
murs ferait dériver le total de 7 à 15 unités, invisible à l'œil sur une grande
grille et donc jamais détecté sans test dédié.

### Quand la génération a été refusée

Si le budget mémoire a bloqué la génération, il n'existe **aucune grille** :
`passages` et `chemin_longueur` ne peuvent pas être calculés.

```
labyrinthe_statistiques
n: 100000
cellules: 10000000000
passages: inconnu
chemin_longueur: inconnu
generation: refusee
generation_raison: kruskal demanderait 2.1 Tio pour 10000000000 cellules (budget 2.0 Gio)
```

Deux choix de format méritent d'être explicités :

* **`inconnu`, et non `0`** : un zéro se lirait comme « labyrinthe sans
  passage », ce qui est faux -- il n'y a pas de labyrinthe du tout ;
* **aucune ligne `export_*`** : rien n'a été produit, donc rien n'a été refusé à
  l'export. Annoncer un refus d'export décrirait une décision qui n'a jamais eu
  lieu.

## Confirmation avant d'écrire

Écrire 37 Gio sans rien demander est une façon efficace de remplir un disque.
Au-delà de `CONFIRM_THRESHOLD_BYTES` (256 Mio, estimés), `mazes` demande l'accord
de l'utilisateur :

```
Le fichier image kruskal_astar_100000.jpg pèsera 350.3 Mio. Souhaites-tu l'enregistrer ? [o/N]
```

Le défaut est **non** : une touche Entrée accidentelle ne doit pas déclencher
l'écriture de plusieurs gigaoctets.

### Où la question est posée

`mazes.interaction.sources()` essaie les sources dans cet ordre :

| Ordre | Source | Cas couvert |
|---:|---|---|
| 1 | `stdin` | `echo o \| mazes run …` — un tube porte la réponse |
| 2 | Console du système (`CONIN$`/`CONOUT$`, `/dev/tty`) | `mazes run … > log.txt`, ou `stdin` épuisé |
| 3 | Aucune | CI, tâche planifiée, service |

**L'ordre compte.** Chercher la console avant d'écouter `stdin` perdrait une
réponse envoyée par tube : l'utilisateur aurait répondu « non » et le fichier
serait écrit quand même.

Quand aucune source n'existe, la politique s'applique seule : on ne peut pas
demander, mais on sait réduire ou refuser. La commande ne bloque jamais et ne
remplit jamais le disque en silence.

`MAZES_NO_PROMPT=1` fait taire la question sans changer le reste.

### Deux drapeaux

| Drapeau | Effet |
|---|---|
| `--yes`, `-y` | enregistrer sans demander |
| `--stats-only` | n'écrire que le fichier de statistiques |

Répondre « non » n'est pas une erreur : le code de retour reste `0`, et le
fichier de statistiques est écrit à la place.

## Estimation de la taille du JPEG

Le seuil d'alerte a besoin d'une taille **avant** d'écrire. `estimate_ascii_bytes`
donne l'ASCII exactement (une cellule = un caractère). Le JPEG, lui, est estimé,
et le modèle a **deux régimes** séparés par un facteur 12 :

| Régime | Constante | Mesuré |
|---|---:|---|
| Pleine résolution (`image_scale == 1`) | 1,35 o/px | 1,25 – 1,34 |
| Réduite (`image_scale > 1`) | 0,45 o/px | 0,05 – 0,39 |

Passer de `n = 16383` à `n = 16384` fait chuter l'estimation d'un facteur 12 :
`image_scale` passe de 1 à 2, et la plus grande partie de l'image devient
uniforme. Contre-intuitif — un labyrinthe deux fois plus grand donne une image
bien plus légère — mais c'est le comportement réel de `subsample_dense`.

Deux pièges de calibrage, tous deux vérifiés :

* **Il faut inclure l'état du solveur.** Une grille nue donne 1,13 o/px ; avec le
  chemin rouge et les cellules explorées bleu clair, 1,25 – 1,34. L'écart de 15 %
  vient des zones explorées, qu'un calibrage sur grille nue oublierait.
* **Le régime réduit ne « blanchit » pas.** `subsample_dense` préserve le chemin,
  si bien que le chemin et les zones explorées occupent une part croissante d'une
  image de plus en plus petite. L'image ne se réduit donc pas à de vastes plages
  uniformes.

Les deux constantes **majorent** les mesures. C'est délibéré : surestimer fait
prévenir un peu tôt, sous-estimer laisserait remplir le disque sans rien dire.
L'écart va de +4 % en pleine résolution à un facteur ~8 aux forts facteurs de
réduction — acceptable pour une alerte, pas pour une prévision au mégaoctet près.

## Rappel sur les limites de Pillow

Pillow applique une protection anti-« bombe de décompression » à deux seuils :

| Pixels | Comportement |
|---:|---|
| > 89 478 485 (~89,5 M) | `DecompressionBombWarning` |
| > 178 956 970 (~179 M) | `DecompressionBombError` |

Le seuil d'avertissement correspond à `n ≈ 4 700`, bien en dessous de ce que ce projet
produit légitimement : la protection doit être désactivée explicitement, avec un
commentaire qui le justifie.
