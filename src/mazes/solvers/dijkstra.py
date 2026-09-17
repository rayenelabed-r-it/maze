"""Dijkstra avec file de priorité.

Trois corrections par rapport au prototype :
  - plus de construction préalable du dictionnaire d'adjacence (O(n²)
    mémoire inutile) : les voisins sont demandés à la grille à la volée ;
  - `distances` est un tableau plat indexé par cellule, pas un dict de tuples ;
  - si l'arrivée n'est pas atteignable, on renvoie un chemin vide au lieu
    de planter sur un KeyError dans la reconstruction.

Tous les couloirs coûtent 1, donc Dijkstra fait ici le même travail qu'un
BFS, avec le surcoût du tas : c'est précisément ce que le benchmark montre.
"""

from __future__ import annotations

import heapq
import time

from mazes.core.grid import Cell, WallGrid
from mazes.solvers.base import EXPLORED, SolveResult, Solver, register_solver


@register_solver
class DijkstraSolver(Solver):
    name = "dijkstra"
    description = "Plus court chemin par file de priorité (coût uniforme)"
    complexity = "O(n² log n)"
    optimal = True

    def solve(self, grid: WallGrid, start: Cell, goal: Cell) -> SolveResult:
        debut = time.perf_counter()
        n2 = grid.n * grid.n

        state = bytearray(n2)
        distances = [-1] * n2          # -1 = infini
        predecesseurs: dict[Cell, Cell] = {}
        finalisees = bytearray(n2)

        distances[grid.index(start)] = 0
        file: list[tuple[int, Cell]] = [(0, start)]
        expanded = explored = 1
        max_frontier = 1
        state[grid.index(start)] = EXPLORED

        while file:
            max_frontier = max(max_frontier, len(file))
            distance, cellule = heapq.heappop(file)
            i = grid.index(cellule)
            if finalisees[i]:
                continue  # doublon laissé dans le tas
            finalisees[i] = 1
            expanded += 1

            if cellule == goal:
                break

            for voisine in grid.accessible(cellule):
                j = grid.index(voisine)
                candidate = distance + 1
                if distances[j] == -1 or candidate < distances[j]:
                    if distances[j] == -1:
                        explored += 1
                        state[j] = EXPLORED
                    distances[j] = candidate
                    predecesseurs[voisine] = cellule
                    heapq.heappush(file, (candidate, voisine))

        chemin: list[Cell] = []
        if distances[grid.index(goal)] != -1:
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
