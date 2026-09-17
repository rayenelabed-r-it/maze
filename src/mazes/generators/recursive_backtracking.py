"""Exploration exhaustive avec retour sur trace, en version itérative.

La récursion naturelle atteindrait la limite de Python dès n = 100
(la pile peut contenir jusqu'à n² cellules) : on gère donc la pile
explicitement.
"""

from __future__ import annotations

from mazes.core.grid import WallGrid
from mazes.core.rng import RandomSource
from mazes.generators.base import Generator, register_generator


@register_generator
class RecursiveBacktrackingGenerator(Generator):
    name = "recursive_backtracking"
    description = "Exploration exhaustive avec retour sur trace (DFS itératif)"
    complexity = "O(n²)"

    def generate(self, n: int, rng: RandomSource) -> WallGrid:
        grid = WallGrid(n)
        visitees = bytearray(n * n)

        depart = (rng.randrange(n), rng.randrange(n))
        visitees[grid.index(depart)] = 1
        pile = [depart]

        while pile:
            cellule = pile[-1]
            candidats = [
                v for v in grid.neighbors(cellule) if not visitees[grid.index(v)]
            ]
            if not candidats:
                pile.pop()  # cul-de-sac : on revient sur nos pas
                continue
            voisine = rng.choice(candidats)
            grid.carve(cellule, voisine)
            visitees[grid.index(voisine)] = 1
            pile.append(voisine)

        return grid
