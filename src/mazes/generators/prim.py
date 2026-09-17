"""Prim aléatoire : le labyrinthe grandit depuis une cellule de départ,
en tirant au hasard un mur de la frontière à chaque étape."""

from __future__ import annotations

from mazes.core.grid import WallGrid
from mazes.core.rng import RandomSource
from mazes.generators.base import Generator, register_generator


@register_generator
class PrimGenerator(Generator):
    name = "prim"
    description = "Prim aléatoire (croissance depuis une cellule de départ)"
    complexity = "O(n²)"

    def generate(self, n: int, rng: RandomSource) -> WallGrid:
        grid = WallGrid(n)
        visitees = bytearray(n * n)

        r, c = rng.randrange(n), rng.randrange(n)
        visitees[grid.index(r, c)] = 1
        frontiere = [((r, c), (nr, nc), d) for nr, nc, d in grid.iter_neighbors(r, c)]

        while frontiere:
            # tirage au hasard + swap-pop : O(1) au lieu du pop(index) en O(k).
            i = rng.randrange(len(frontiere))
            frontiere[i], frontiere[-1] = frontiere[-1], frontiere[i]
            a, b, d = frontiere.pop()

            br, bc = b
            if visitees[grid.index(br, bc)]:
                continue  # abattre ce mur créerait un cycle

            visitees[grid.index(br, bc)] = 1
            grid.carve(a[0], a[1], d)
            for nr, nc, d2 in grid.iter_neighbors(br, bc):
                if not visitees[grid.index(nr, nc)]:
                    frontiere.append((b, (nr, nc), d2))

        return grid
