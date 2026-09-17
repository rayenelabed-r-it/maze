"""Solveur par Recursive Backtracking (exploration en profondeur, pile explicite).

La pile **est** le chemin courant : empiler = avancer, dépiler = reculer (et
marquer ``*``). Pas de table de parents, donc moins de mémoire qu'A*. Pile
explicite pour éviter la limite de récursion de CPython. Voir ``doc/04-solveurs.md``.
"""

from __future__ import annotations

from time import perf_counter
from typing import TYPE_CHECKING

from mazes.core.grid import DELTA_COL, DELTA_ROW, DIRECTIONS, EAST, SOUTH, WEST
from mazes.core.rng import RandomSource
from mazes.solvers.base import (
    EXPLORED,
    ON_PATH,
    UNVISITED,
    Solver,
    SolveResult,
    register_solver,
)

if TYPE_CHECKING:  # pragma: no cover
    from mazes.core.grid import WallGrid

Cell = tuple[int, int]


@register_solver
class RecursiveBacktrackingSolver(Solver):
    """Exploration en profondeur avec pile explicite (la pile est le chemin)."""

    name = "recursive_backtracking"
    description = "Exploration en profondeur avec pile explicite (la pile est le chemin)."
    complexity = "O(n^2) temps, O(n^2) memoire"
    optimal = True

    def __init__(self, neighbor_order: str = "fixed", seed: int | None = None) -> None:
        """Configure l'ordre d'examen des voisins (``"fixed"`` ou ``"shuffled"``)."""
        if neighbor_order not in ("fixed", "shuffled"):
            raise ValueError(f"neighbor_order inconnu : {neighbor_order!r}")
        self.neighbor_order = neighbor_order
        # La source aléatoire n'existe qu'en mode mélangé.
        self._rng = RandomSource(seed) if neighbor_order == "shuffled" else None

    def solve(self, grid: WallGrid, start: Cell, goal: Cell) -> SolveResult:
        """Résout par backtracking : ``state`` sert aussi de marque de visite.

        La pile contient exactement le chemin quand on atteint la sortie. Chaque
        cellule est empilée puis dépilée au plus une fois : complexité ``O(n²)``.
        """
        self._require_endpoints(grid, start, goal)

        debut = perf_counter()
        n = grid.n

        # Le masque sert AUSSI de marque de visite : UNVISITED -> non empilé.
        state = bytearray(n * n)

        depart = start[0] * n + start[1]
        arrivee = goal[0] * n + goal[1]

        stack = [depart]
        state[depart] = ON_PATH

        expanded = 1
        max_frontier = 1

        while stack:
            # Regarder le sommet sans le retirer : distinguer avancer/reculer.
            index = stack[-1]
            if index == arrivee:
                break

            r, c = divmod(index, n)
            suivant = self._next_unvisited(grid, state, r, c, index)

            if suivant >= 0:
                state[suivant] = ON_PATH
                stack.append(suivant)
                expanded += 1
                if len(stack) > max_frontier:
                    max_frontier = len(stack)
            else:
                stack.pop()
                state[index] = EXPLORED

        if not stack:
            # Sortie jamais atteinte (grille invalide) : résultat vide.
            return SolveResult(
                path=[],
                state=state,
                expanded=expanded,
                explored=expanded,
                max_frontier=max_frontier,
                elapsed_s=perf_counter() - debut,
                algorithm=self.name,
            )

        # La pile contient exactement le chemin, du départ vers l'arrivée.
        chemin = [divmod(i, n) for i in stack]

        return SolveResult(
            path=chemin,
            state=state,
            expanded=expanded,
            explored=expanded,  # le backtracking ne revoit jamais une cellule
            max_frontier=max_frontier,
            elapsed_s=perf_counter() - debut,
            algorithm=self.name,
        )

    def _next_unvisited(
        self, grid: WallGrid, state: bytearray, r: int, c: int, index: int
    ) -> int:
        """Index linéaire d'un voisin accessible non visité, ou ``-1``.

        Le test de bornes précède la lecture du mur. Le mur à lire dépend de la
        direction : Ouest -> mur Est du voisin, Nord -> mur Sud du voisin.
        """
        n = grid.n
        east = grid.east
        south = grid.south

        if self._rng is None:
            ordre = DIRECTIONS
        else:
            ordre = list(DIRECTIONS)
            self._rng.python.shuffle(ordre)

        for d in ordre:
            nr = r + DELTA_ROW[d]
            nc = c + DELTA_COL[d]
            if not (0 <= nr < n and 0 <= nc < n):
                continue

            voisin = nr * n + nc
            if state[voisin] != UNVISITED:
                continue

            if d == EAST:
                i = index
                masque = east
            elif d == WEST:
                i = voisin  # le mur Ouest de (r, c) est le mur Est de (r, c-1)
                masque = east
            elif d == SOUTH:
                i = index
                masque = south
            else:  # NORTH : le mur Nord de (r, c) est le mur Sud de (r-1, c)
                i = voisin
                masque = south

            if not (masque[i >> 3] >> (i & 7)) & 1:
                return voisin

        return -1
