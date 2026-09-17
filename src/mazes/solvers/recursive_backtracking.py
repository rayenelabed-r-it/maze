"""Résolution par retour sur trace (DFS itératif).

Non optimal : dans un labyrinthe parfait il n'existe qu'un seul chemin
simple entre deux cellules, donc le chemin trouvé est le bon — mais
l'algorithme peut explorer une grande partie de la grille avant de le
trouver. C'est le point de comparaison avec A*.
"""

from __future__ import annotations

import time

from mazes.core.grid import Cell, WallGrid
from mazes.solvers.base import EXPLORED, SolveResult, Solver, register_solver


@register_solver
class RecursiveBacktrackingSolver(Solver):
    name = "recursive_backtracking"
    description = "Retour sur trace en profondeur (pile explicite)"
    complexity = "O(n²)"
    optimal = False

    def solve(self, grid: WallGrid, start: Cell, goal: Cell) -> SolveResult:
        debut = time.perf_counter()
        n2 = grid.n * grid.n

        state = bytearray(n2)
        visitees = bytearray(n2)
        visitees[grid.index(start)] = 1
        state[grid.index(start)] = EXPLORED

        pile: list[Cell] = [start]
        expanded = 0
        explored = 1
        max_frontier = 1
        trouve = start == goal

        while pile and not trouve:
            max_frontier = max(max_frontier, len(pile))
            cellule = pile[-1]
            suivante = None
            for voisine in grid.accessible(cellule):
                if not visitees[grid.index(voisine)]:
                    suivante = voisine
                    break

            if suivante is None:
                pile.pop()  # cul-de-sac
                continue

            expanded += 1
            explored += 1
            visitees[grid.index(suivante)] = 1
            state[grid.index(suivante)] = EXPLORED
            pile.append(suivante)
            if suivante == goal:
                trouve = True

        chemin = list(pile) if trouve else []
        if chemin:
            self._mark(grid, state, chemin)

        return SolveResult(
            path=chemin,
            state=state,
            expanded=expanded,
            explored=explored,
            max_frontier=max_frontier,
            elapsed_s=time.perf_counter() - debut,
            algorithm=self.name,
        )
