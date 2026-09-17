# Documentation

## La question à laquelle ce projet répond

> **Quel algorithme est le plus rapide, le plus efficace et le plus léger, pour
> chaque taille de labyrinthe ?**

Tout le reste est un moyen. La réponse est un **tableau** :

| `n` | Solveur | Rapide (s) | Efficace (cellules développées) | Léger (mémoire) |
|---:|---|---:|---:|---:|
| 1 000 | Backtracking | ? | ? | ? |
| 1 000 | A\* | ? | ? | ? |
| 10 000 | Backtracking | ? | ? | ? |
| 10 000 | A\* | ? | ? | ? |

Plus deux courbes : temps et mémoire en fonction de `n`.

## Ce que « rapide », « efficace » et « léger » veulent dire ici

Les trois mots sont ambigus. Voici la traduction retenue, et elle doit être
rappelée dans le rapport.

| Mot du coach | Mesure | Champ | Pourquoi cette mesure |
|---|---|---|---|
| **rapide** | temps mural médian, sur N graines | `elapsed_s` | dépend de la machine, mais c'est ce que « rapide » veut dire |
| **efficace** | cellules développées | `expanded` | **indépendant de la machine** : la meilleure base de comparaison |
| **léger** | **pic mémoire réel** de tout le solveur | `memoire_pic_octets` | mesuré par `tracemalloc` : il compte *toutes* les structures |

> **Pourquoi pas la seule frontière.** `max_frontier` (le pic de la pile ou du tas)
> est trompeur : à `n = 500`, A\* plafonne à **27** entrées en attente contre
> **72 306** pour le backtracking, et pourtant A\* consomme **plus** de mémoire au
> total (4 329 Kio contre 3 079 Kio), à cause de ses tables `g`, `parents` et
> `closed`. Mesurer la frontière seule donnerait un verdict inversé.
>
> Les deux chiffres restent affichés : la frontière explique *pourquoi*, le pic
> mémoire tranche.

**`expanded` est la mesure la plus solide des trois.** Elle ne dépend ni de la
machine, ni de la version de Python, ni de la charge du système. Si l'on ne devait
retenir qu'un chiffre, ce serait celui-là.

Un quatrième indicateur, dérivé, résume bien la situation :

```
efficacité = longueur du chemin / cellules développées
```

Il vaut 1 pour un solveur qui ne développe que les cellules de son chemin, et tend
vers 0 pour un solveur qui explore tout le labyrinthe. C'est le chiffre à mettre en
avant dans la conclusion.

## Protocole de mesure

Sans ces quatre règles, les chiffres ne veulent rien dire.

**1. Plusieurs graines.** L'écart-type entre graines atteint **37 %** du nombre de
cellules développées à `n = 200`. C'est énorme : une conclusion tirée d'une seule
graine n'a aucune valeur. Prendre au moins 5 graines et rapporter la médiane.

**2. Échauffement.** Un passage non mesuré avant la campagne, pour que l'import des
modules et le remplissage des caches ne soient pas comptés dans la première mesure.

**3. Médiane, pas moyenne.** Un seul passage est trompé par le ramasse-miettes et par
les interruptions du système. La médiane ignore les valeurs aberrantes, la moyenne
non.

**4. Même labyrinthe pour les deux solveurs.** Comparer le backtracking et A\* sur des
labyrinthes différents ne mesure rien. La graine doit être fixée à l'intérieur de
chaque comparaison.

## Comment obtenir les labyrinthes

Les générateurs sont dans `mazes.generators` : Recursive Backtracking, Kruskal et
Prim. En ligne de commande :

```bash
mazes generate --n 100 --algorithm kruskal
```

puis le benchmark analyse les labyrinthes générés dans `outputs/` :

```bash
python benchmarks/scaling.py
```

C'est tout l'intérêt d'avoir `WallGrid` comme structure pivot : les solveurs ne
savent pas d'où vient la grille.

## Index

| Document | Contenu |
|---|---|
| [01 — Architecture](01-architecture.md) | organisation du code, où se trouve ta partie |
| [02 — La grille](02-grille.md) | le modèle 2 bits/cellule, et la lecture ASCII |
| [03 — Générateurs](03-generateurs.md) | la théorie de Recursive Backtracking et Kruskal |
| [04 — Solveurs](04-solveurs.md) | la théorie de backtracking et A\*, et le marquage `o` / `*` |
| [05 — Export](05-export.md) | écrire un labyrinthe en ASCII et en image |

## Ta partie

D'après le découpage que tu as donné :

1. **Lecture ASCII** — un fichier `.txt` → une `WallGrid`. Voir `02-grille.md`.
2. **Deux solveurs** — Recursive Backtracking et A\*. Voir `04-solveurs.md`.
3. **Reconstruction du chemin** et **marquage `o` / `*`** — voir `04-solveurs.md`.
4. **La comparaison** — le tableau et les courbes. Voir ce document.

Les points 1 à 3 se trouvent dans `src/mazes/rendering/ascii.py` et
`src/mazes/solvers/`. Le point 4 dans `benchmarks/scaling.py`.
