"""Kruskal aléatoire : on mélange tous les murs et on abat ceux qui
relient deux composantes différentes."""

from __future__ import annotations

from mazes.core.grid import WallGrid
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

        # Droite et bas uniquement : chaque paire de voisines apparaît une fois
        murs = []
        for r in range(n):
            for c in range(n):
                if c + 1 < n:
                    murs.append(((r, c), (r, c + 1)))
                if r + 1 < n:
                    murs.append(((r, c), (r + 1, c)))

        rng.shuffle(murs)

        uf = UnionFind(n * n)
        restants = n * n - 1
        for a, b in murs:
            if uf.union(grid.index(a), grid.index(b)):
                grid.carve(a, b)
                restants -= 1
                if restants == 0:
                    break  # l'arbre couvrant est complet, inutile de continuer
        return grid
