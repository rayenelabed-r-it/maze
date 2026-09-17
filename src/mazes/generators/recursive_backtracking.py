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

        r, c = rng.randrange(n), rng.randrange(n)
        visitees[grid.index(r, c)] = 1
        pile = [(r, c)]

        while pile:
            r, c = pile[-1]
            candidats = [
                (nr, nc, d)
                for nr, nc, d in grid.iter_neighbors(r, c)
                if not visitees[grid.index(nr, nc)]
            ]
            if not candidats:
                pile.pop()  # cul-de-sac : on revient sur nos pas
                continue
            nr, nc, d = rng.choice(candidats)
            grid.carve(r, c, d)
            visitees[grid.index(nr, nc)] = 1
            pile.append((nr, nc))

        return grid
