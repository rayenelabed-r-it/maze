"""Solveur A* (recherche informée) avec heuristique de distance de Manhattan.

``f = g + h`` ; ``h`` admissible donc A* trouve le plus court chemin. Trois
heuristiques admissibles sur grille à quatre voisins : Manhattan (défaut),
euclidienne et Tchebychev. Voir ``doc/04-solveurs.md``.
"""

from __future__ import annotations

from array import array
from collections.abc import Callable
from heapq import heappop, heappush
from math import isqrt
from time import perf_counter
from typing import TYPE_CHECKING

from mazes.core.grid import DELTA_COL, DELTA_ROW, DIRECTIONS, EAST, SOUTH, WEST
from mazes.solvers.base import EXPLORED, Solver, SolveResult, register_solver

if TYPE_CHECKING:  # pragma: no cover
    from mazes.core.grid import WallGrid

#: Type des tableaux d'indices : 4 octets par élément, sans objet ``int`` par entrée.
_INDEX_TYPECODE = "i"

Cell = tuple[int, int]


@register_solver
class AStarSolver(Solver):
    """A* avec heuristique configurable, départage d'ex æquo et pondération optionnelle."""

    name = "astar"
    description = "Recherche informee A* avec heuristique de distance de Manhattan."
    complexity = "O(n^2 log n) temps, O(n^2) memoire"
    optimal = True

    def __init__(
        self,
        heuristic: str = "manhattan",
        weight: float = 1.0,
        tie_break: str = "deeper",
    ) -> None:
        """Configure heuristique (``"manhattan"``/``"euclidean"``/``"chebyshev"``), poids et départage."""
        if heuristic not in ("manhattan", "euclidean", "chebyshev"):
            raise ValueError(f"heuristique inconnue : {heuristic!r}")
        if tie_break not in ("deeper", "shallower", "none"):
            raise ValueError(f"tie_break inconnu : {tie_break!r}")
        if weight < 1.0:
            raise ValueError("weight doit etre >= 1.0, sinon h n'est plus admissible")

        self.heuristic = heuristic
        self.weight = weight
        self.tie_break = tie_break
        # Signature : (row, col, goal_row, goal_col) -> cout estime.
        self._h: Callable[[int, int, int, int], int] = _HEURISTICS[heuristic]

    def solve(self, grid: WallGrid, start: Cell, goal: Cell) -> SolveResult:
        """Résout par A* : tas ``heapq``, ``g``/``parents`` en ``array("i")``, ``closed`` en ``bytearray``.

        ``-1`` sert de sentinelle « non atteint » dans ``g`` (``array("i")`` ne
        stocke pas l'infini) : le test doit donc être ``g_v < 0 or g_new < g_v``.
        La suppression paresseuse ignore les entrées obsolètes du tas via ``closed``.
        """
        self._require_endpoints(grid, start, goal)

        debut = perf_counter()
        n = grid.n
        total = n * n
        east = grid.east
        south = grid.south

        depart = start[0] * n + start[1]
        arrivee = goal[0] * n + goal[1]

        g = array(_INDEX_TYPECODE, [-1]) * total
        parents = array(_INDEX_TYPECODE, [-1]) * total
        closed = bytearray(total)
        state = bytearray(total)

        g[depart] = 0
        parents[depart] = depart  # le départ est son propre parent : arrête la remontée

        heuristique = build_heuristic(self.heuristic, goal[0], goal[1])
        poids = self.weight

        if self.tie_break == "deeper":
            signe = -1
        elif self.tie_break == "shallower":
            signe = 1
        else:
            signe = 0

        # (f, départage, compteur, index) : le compteur croissant évite toute égalité.
        tas = [(heuristique(start[0], start[1]), 0, 0, depart)]
        compteur = 1

        expanded = 0
        explored = 1
        max_frontier = 1

        while tas:
            _, _, _, index = heappop(tas)

            if closed[index]:  # entrée obsolète (suppression paresseuse)
                continue

            closed[index] = 1
            state[index] = EXPLORED
            expanded += 1

            if index == arrivee:
                break

            r, c = divmod(index, n)
            nouveau_g = g[index] + 1

            for d in DIRECTIONS:
                nr = r + DELTA_ROW[d]
                nc = c + DELTA_COL[d]
                if not (0 <= nr < n and 0 <= nc < n):
                    continue
                voisin = nr * n + nc
                if closed[voisin]:
                    continue

                # Le mur à lire dépend de la direction : Ouest -> mur Est du voisin,
                # Nord -> mur Sud du voisin.
                if d == EAST:
                    i = index
                    masque = east
                elif d == WEST:
                    i = voisin
                    masque = east
                elif d == SOUTH:
                    i = index
                    masque = south
                else:  # NORTH
                    i = voisin
                    masque = south
                if (masque[i >> 3] >> (i & 7)) & 1:
                    continue

                ancien = g[voisin]
                # `ancien < 0` est indispensable : sans lui la première amélioration
                # d'une cellule non atteinte serait rejetée.
                if ancien < 0 or nouveau_g < ancien:
                    if ancien < 0:
                        explored += 1
                    g[voisin] = nouveau_g
                    parents[voisin] = index
                    estime = heuristique(nr, nc)
                    f = nouveau_g + (estime if poids == 1.0 else int(estime * poids))
                    heappush(tas, (f, nouveau_g * signe, compteur, voisin))
                    compteur += 1

            if len(tas) > max_frontier:
                max_frontier = len(tas)

        chemin = self._reconstruct(parents, start, goal, n)
        self._mark_states(chemin, state, n)

        return SolveResult(
            path=chemin,
            state=state,
            expanded=expanded,
            explored=explored,
            max_frontier=max_frontier,
            elapsed_s=perf_counter() - debut,
            algorithm=self.name,
        )

    def heuristic_value(self, row: int, col: int, goal_row: int, goal_col: int) -> int:
        """Valeur pondérée de ``h`` entre ``(row, col)`` et la sortie."""
        valeur = self._h(row, col, goal_row, goal_col)
        if self.weight == 1.0:
            return valeur
        return int(valeur * self.weight)


# --------------------------------------------------------------------------- #
# Heuristiques
# --------------------------------------------------------------------------- #


def manhattan(row: int, col: int, goal_row: int, goal_col: int) -> int:
    """Distance de Manhattan : ``|row - goal_row| + |col - goal_col|`` (admissible, défaut)."""
    return abs(row - goal_row) + abs(col - goal_col)


def euclidean(row: int, col: int, goal_row: int, goal_col: int) -> int:
    """Distance euclidienne arrondie à l'entier inférieur (admissible, via ``isqrt``)."""
    dr = row - goal_row
    dc = col - goal_col
    return isqrt(dr * dr + dc * dc)


def chebyshev(row: int, col: int, goal_row: int, goal_col: int) -> int:
    """Distance de Tchebychev : ``max(|dr|, |dc|)`` (admissible, la moins informative)."""
    return max(abs(row - goal_row), abs(col - goal_col))


#: Table ``nom -> fonction`` d'heuristique.
_HEURISTICS: dict[str, Callable[[int, int, int, int], int]] = {
    "manhattan": manhattan,
    "euclidean": euclidean,
    "chebyshev": chebyshev,
}


def build_heuristic(name: str, goal_row: int, goal_col: int) -> Callable[[int, int], int]:
    """Construit ``h`` pour une sortie donnée : un callable ``(row, col) -> int``.

    Capturer la sortie dans une fermeture supprime deux arguments par appel.
    """
    if name not in _HEURISTICS:
        available = ", ".join(sorted(_HEURISTICS))
        raise ValueError(f"heuristique inconnue : {name!r}. Disponibles : {available}")
    fn = _HEURISTICS[name]
    return lambda row, col: fn(row, col, goal_row, goal_col)
