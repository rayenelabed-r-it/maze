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

        depart = (rng.randrange(n), rng.randrange(n))
        visitees[grid.index(depart)] = 1

        frontiere = [(depart, v) for v in grid.neighbors(depart)]

        while frontiere:
            # tirage au hasard + swap-pop : O(1) au lieu du pop(index) en O(k)
            i = rng.randrange(len(frontiere))
            frontiere[i], frontiere[-1] = frontiere[-1], frontiere[i]
            a, b = frontiere.pop()

            if visitees[grid.index(b)]:
                continue  # abattre ce mur créerait un cycle

            visitees[grid.index(b)] = 1
            grid.carve(a, b)
            for voisine in grid.neighbors(b):
                if not visitees[grid.index(voisine)]:
                    frontiere.append((b, voisine))

        return grid
