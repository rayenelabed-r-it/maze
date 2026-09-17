"""A* avec heuristique de Manhattan.

Dans une grille à déplacements orthogonaux de coût 1, la distance de
Manhattan ne surestime jamais la distance réelle : l'heuristique est
admissible et cohérente, donc le chemin trouvé est bien le plus court.
"""

from __future__ import annotations

import heapq
import time

from mazes.core.grid import Cell, WallGrid
from mazes.solvers.base import EXPLORED, SolveResult, Solver, register_solver


def manhattan(a: Cell, b: Cell) -> int:
    return abs(a[0] - b[0]) + abs(a[1] - b[1])


@register_solver
class AStarSolver(Solver):
    name = "astar"
    description = "A* avec heuristique de Manhattan"
    complexity = "O(n² log n) au pire, guidé en pratique"
    optimal = True

    def solve(self, grid: WallGrid, start: Cell, goal: Cell) -> SolveResult:
        debut = time.perf_counter()
        n2 = grid.n * grid.n

        state = bytearray(n2)
        g_score = [-1] * n2
        fermees = bytearray(n2)
        predecesseurs: dict[Cell, Cell] = {}

        g_score[grid.index(start)] = 0
        state[grid.index(start)] = EXPLORED
        file: list[tuple[int, int, Cell]] = [(manhattan(start, goal), 0, start)]
        expanded = 0
        explored = 1
        max_frontier = 1

        trouve = False
        while file:
            max_frontier = max(max_frontier, len(file))
            _, g, cellule = heapq.heappop(file)
            i = grid.index(cellule)
            if fermees[i]:
                continue
            fermees[i] = 1
            expanded += 1

            if cellule == goal:
                trouve = True
                break

            for voisine in grid.accessible(cellule):
                j = grid.index(voisine)
                candidate = g + 1
                if g_score[j] == -1 or candidate < g_score[j]:
                    if g_score[j] == -1:
                        explored += 1
                        state[j] = EXPLORED
                    g_score[j] = candidate
                    predecesseurs[voisine] = cellule
                    heapq.heappush(
                        file, (candidate + manhattan(voisine, goal), candidate, voisine)
                    )

        chemin: list[Cell] = []
        if trouve:
            cellule = goal
            while cellule != start:
                chemin.append(cellule)
                cellule = predecesseurs[cellule]
            chemin.append(start)
            chemin.reverse()
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
