"""Budget mémoire : peut-on lancer ce calcul ?

Estime l'empreinte d'une génération ou d'une résolution à partir du seul ``n``,
avant toute allocation. Au-delà de :data:`MEMORY_BUDGET`, le calcul est refusé
plutôt que lancé. Les modèles sont calés sur des mesures ``tracemalloc``, que
les tests recoupent.
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

#: Budget mémoire par défaut d'une phase, en octets (2 Gio). Une machine qui
#: n'a pas cette réserve disponible partirait en swap avant de finir. Sur un
#: poste plus large, ``MAZES_MEMORY_BUDGET`` relève le plafond.
MEMORY_BUDGET = 2 * 1024**3

#: Variable d'environnement qui remplace le budget, en octets.
BUDGET_ENV_VAR = "MAZES_MEMORY_BUDGET"

#: Modèles ``a·n² + b·n + c`` des générateurs, en octets.
#:
#: Mesures, à ``n = 1000`` : kruskal 217 o/cellule, prim 3,2, backtracking 26.
#: Kruskal paie ses ``2n²`` tuples ; le coût par arête croît même avec ``n``,
#: les entiers ``(r, c)`` sortant du cache de CPython au-delà de 256.
#: Prim paie un ``bytearray(n²)`` plus une frontière ``O(n)``.
#:
#: Ces modèles majorent les mesures. Surestimer refuse un calcul qui aurait
#: tenu, ce que l'utilisateur peut corriger en relevant le budget ; sous-estimer
#: tue le processus sans rien produire.
_MODELES_GENERATION: dict[str, tuple[float, float, float]] = {
    "kruskal": (230.0, 0.0, 0.0),
    "prim": (2.5, 3_000.0, 0.0),
    "recursive_backtracking": (30.0, 0.0, 0.0),
}

#: Modèles ``a·n² + b·n + c`` des solveurs, en octets.
#:
#: Mesures, à ``n = 1000`` : A* et Dijkstra 10,2 o/cellule, backtracking 1,1.
#: Les deux premiers paient deux ``array("i")`` et deux ``bytearray`` ; le
#: troisième un seul ``bytearray`` et une pile courte.
#:
#: Deux tables séparées, et non une seule : ``recursive_backtracking`` figure
#: dans les deux registres, avec des empreintes qui n'ont rien à voir.
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
    """Coefficients ``(a, b, c)`` de ``nom``."""
    try:
        return table[nom]
    except KeyError:
        connus = ", ".join(sorted(table))
        raise ValueError(
            f"aucun modele de memoire pour {phase} {nom!r}. Connus : {connus}"
        ) from None


def estimate_generation(generateur: str, n: int) -> int:
    """Empreinte estimée d'une génération, en octets."""
    return _evaluer(_modele(_MODELES_GENERATION, generateur, "le generateur"), n)


def estimate_solving(solveur: str, n: int) -> int:
    """Empreinte estimée d'une résolution, en octets."""
    return _evaluer(_modele(_MODELES_RESOLUTION, solveur, "le solveur"), n)


def memory_budget() -> int:
    """Budget courant, en octets.

    La variable d'environnement est relue à chaque appel, et non liée à
    l'import, pour que les tests puissent la ramener à zéro.
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
