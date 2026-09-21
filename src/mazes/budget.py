"""Budget mémoire : peut-on seulement lancer ce calcul ?

Kruskal construit la liste de **toutes** ses arêtes avant d'en abattre une seule.
À ``n = 100000`` cela fait 20 milliards de tuples, soit ~2 Tio. Le processus meurt
en ``MemoryError`` -- sans message utile, et sans avoir rien produit.

Ce module répond **avant** la moindre allocation, à partir du seul ``n`` : le
calcul demandé tient-il dans le budget ? Quand ce n'est pas le cas, le CLI
applique la même règle que pour l'export -- refus, et fichier de statistiques.

Aucun algorithme n'est modifié ni remplacé : ce module ne fait que **prédire**
l'empreinte des algorithmes existants. Les modèles sont calés sur des mesures
(voir ``doc/03-generateurs.md`` et ``doc/04-solveurs.md``) et recoupés par les
tests, qui comparent chaque prédiction à un pic réellement mesuré par
``tracemalloc``.

Deux phases, deux tables
------------------------
La génération et la résolution ne se chevauchent pas : les structures du
générateur sont libérées avant que le solveur ne commence. Chacune est donc
vérifiée contre le même budget, et le pic du processus est le plus gros des deux.

**Deux tables séparées, et non une seule.** ``recursive_backtracking`` existe
dans les deux registres -- c'est un générateur *et* un solveur, avec des
empreintes qui n'ont rien à voir (30 contre 2 o/cellule). Une table unique
écraserait silencieusement l'un des deux modèles.

Ce module n'importe rien du projet : il reste une feuille du graphe, au même
titre que ``interaction.py``.
"""

from __future__ import annotations

import math
import os

__all__ = [
    "BUDGET_ENV_VAR",
    "MEMORY_BUDGET",
    "estimate_generation",
    "estimate_solving",
    "fits_generation",
    "fits_solving",
    "memory_budget",
]

#: Budget mémoire par défaut d'une phase, en octets (2 Gio).
#:
#: Volontairement modeste : une machine qui n'a pas cette réserve disponible
#: partirait en swap avant de finir. Sur un poste plus large,
#: ``MAZES_MEMORY_BUDGET`` relève le plafond sans toucher au code.
MEMORY_BUDGET = 2 * 1024**3

#: Variable d'environnement qui remplace le budget, en octets.
BUDGET_ENV_VAR = "MAZES_MEMORY_BUDGET"

#: Modèles d'empreinte ``a·n² + b·n + c`` des **générateurs**, en octets.
#:
#: * ``kruskal`` -- 208 o/cellule à ``n = 500``, 218 à ``n = 1200``, et la pente
#:   reste positive : le coût par arête croît avec ``n`` parce que les entiers
#:   ``(r, c)`` sortent du cache de CPython au-delà de 256. 230 majore le plateau
#:   vers lequel la mesure converge.
#: * ``prim`` -- 4,4 o/cellule à ``n = 500`` mais 1,9 à ``n = 3000`` : le
#:   ``bytearray`` des cellules visitées (1 o/cellule) domine, et la frontière
#:   ``O(n)`` se dilue. Le terme linéaire couvre cette frontière, et le terme en
#:   ``n²`` majore l'asymptote de 1,25 o/cellule.
#: * ``recursive_backtracking`` -- 23 à 28 o/cellule, assez stable : la pile
#:   contient le chemin courant, donc des tuples de deux entiers.
_MODELES_GENERATION: dict[str, tuple[float, float, float]] = {
    "kruskal": (230.0, 0.0, 0.0),
    "prim": (2.5, 3_000.0, 0.0),
    "recursive_backtracking": (30.0, 0.0, 0.0),
}

#: Modèles d'empreinte ``a·n² + b·n + c`` des **solveurs**, en octets.
#:
#: * ``astar`` et ``dijkstra`` -- 10 à 11 o/cellule, convergeant vers 10,1 : les
#:   deux tableaux ``array("i")`` (``g``/``distances`` et ``parents``) font
#:   4 octets, et les deux ``bytearray`` (``closed`` et ``state``) un seul.
#:   12 majore cette asymptote et absorbe la croissance du tas.
#: * ``recursive_backtracking`` -- 1,7 o/cellule à ``n = 500`` mais 1,1 à
#:   ``n = 3000`` : le ``bytearray`` d'état (1 o/cellule) domine, et la pile
#:   reste courte devant ``n²``. Le terme linéaire couvre cette pile -- dont le
#:   poids relatif s'efface quand ``n`` grandit -- et le quadratique majore
#:   l'asymptote.
#:
#: L'écart entre les deux familles est d'un facteur 10 : à ``n = 100000``,
#: résoudre avec A* demande ~112 Gio quand le backtracking en demande ~15.
_MODELES_RESOLUTION: dict[str, tuple[float, float, float]] = {
    "astar": (12.0, 0.0, 0.0),
    "dijkstra": (12.0, 0.0, 0.0),
    "recursive_backtracking": (1.5, 500.0, 0.0),
}


def _evaluer(modele: tuple[float, float, float], n: int) -> int:
    """``a·n² + b·n + c``, arrondi à l'octet supérieur."""
    if not isinstance(n, int) or isinstance(n, bool):
        raise TypeError(f"n doit etre un entier, recu {type(n).__name__}")
    if n < 1:
        raise ValueError(f"n doit etre >= 1, recu {n}")
    a, b, c = modele
    return math.ceil(a * n * n + b * n + c)


def _modele(
    table: dict[str, tuple[float, float, float]], nom: str, phase: str
) -> tuple[float, float, float]:
    """Coefficients ``(a, b, c)`` de ``nom``, ou ``ValueError`` s'il est inconnu."""
    try:
        return table[nom]
    except KeyError:
        connus = ", ".join(sorted(table))
        raise ValueError(
            f"aucun modele de memoire pour {phase} {nom!r}. Connus : {connus}"
        ) from None


def estimate_generation(generateur: str, n: int) -> int:
    """Empreinte mémoire estimée d'une génération, en octets.

    Lève ``ValueError`` si le générateur n'a pas de modèle : mieux vaut un échec
    explicite qu'une estimation silencieusement fausse.
    """
    return _evaluer(_modele(_MODELES_GENERATION, generateur, "le generateur"), n)


def estimate_solving(solveur: str, n: int) -> int:
    """Empreinte mémoire estimée d'une résolution, en octets."""
    return _evaluer(_modele(_MODELES_RESOLUTION, solveur, "le solveur"), n)


def memory_budget() -> int:
    """Budget courant, en octets.

    La variable d'environnement est relue à **chaque appel**, comme les seuils
    d'export : une constante figée à l'import ne serait pas patchable, et les
    tests ne pourraient pas déclencher un refus sans allouer des gigaoctets.
    """
    brut = os.environ.get(BUDGET_ENV_VAR)
    if brut is None:
        return MEMORY_BUDGET
    try:
        valeur = int(brut)
    except ValueError:
        raise ValueError(
            f"{BUDGET_ENV_VAR} doit etre un nombre d'octets, recu {brut!r}"
        ) from None
    if valeur < 1:
        raise ValueError(f"{BUDGET_ENV_VAR} doit etre >= 1, recu {valeur}")
    return valeur


def fits_generation(generateur: str, n: int) -> bool:
    """La génération tient-elle dans le budget ?"""
    return estimate_generation(generateur, n) <= memory_budget()


def fits_solving(solveur: str, n: int) -> bool:
    """La résolution tient-elle dans le budget ?"""
    return estimate_solving(solveur, n) <= memory_budget()
