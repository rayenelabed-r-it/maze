"""Kruskal aléatoire : on mélange tous les murs et on abat ceux qui
relient deux composantes différentes."""

from __future__ import annotations

from mazes.core.grid import EAST, SOUTH, WallGrid
from mazes.core.rng import RandomSource
from mazes.core.unionfind import UnionFind
from mazes.generators.base import Generator, register_generator


@register_generator
class KruskalGenerator(Generator):
    name = "kruskal"
    description = "Kruskal aléatoire (arbre couvrant via Union-Find)"
    complexity = "O(n² alpha(n²)) ~ O(n²)"

    def generate(self, n: int, rng: RandomSource) -> WallGrid:
        grid = WallGrid(n)
        if n == 1:
            return grid

        # Droite et bas uniquement : chaque paire de voisines apparaît une fois.
        murs = []
        for r in range(n):
            for c in range(n):
                if c + 1 < n:
                    murs.append((r, c, EAST))
                if r + 1 < n:
                    murs.append((r, c, SOUTH))

        rng.shuffle(murs)

        uf = UnionFind(n * n)
        restants = n * n - 1
        for r, c, d in murs:
            a = grid.index(r, c)
            b = a + 1 if d == EAST else a + n
            if uf.union(a, b):
                grid.carve(r, c, d)
                restants -= 1
                if restants == 0:
                    break  # l'arbre couvrant est complet, inutile de continuer
        return grid
