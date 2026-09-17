"""Labyrinthes déterministes pour les tests, avec des propriétés connues.

* :func:`snake` — chemin entrée-sortie maximal (pire cas pour un solveur) ;
* :func:`cul_de_sac` — impasse garantie avant la sortie (pour tester le marquage ``*``) ;
* :func:`random_maze` — labyrinthe parfait aléatoire via le vrai générateur.
"""

from __future__ import annotations

from mazes.core.grid import EAST, NORTH, SOUTH, WEST, WallGrid
from mazes.core.rng import RandomSource
from mazes.generators import get_generator


def snake(n: int) -> WallGrid:
    """Labyrinthe parfait en serpentin : le chemin entrée-sortie est maximal (``n²``)."""
    if n < 1:
        raise ValueError(f"n doit etre >= 1, recu {n}")
    grid = WallGrid(n)

    for r in range(n):
        if r % 2 == 0:
            for c in range(n - 1):
                grid.carve(r, c, EAST)
            c_end = n - 1
        else:
            for c in range(n - 1, 0, -1):
                grid.carve(r, c, WEST)
            c_end = 0
        if r + 1 < n:
            grid.carve(r, c_end, SOUTH)

    return grid


def cul_de_sac() -> WallGrid:
    """Labyrinthe ``3 x 3`` où le solveur doit obligatoirement faire demi-tour."""
    grid = WallGrid(3)
    grid.carve(0, 0, EAST)  # (0,0)-(0,1) : l'impasse où l'on entre en premier
    grid.carve(0, 0, SOUTH)  # (0,0)-(1,0)
    grid.carve(1, 0, EAST)  # (1,0)-(1,1)
    grid.carve(1, 1, EAST)  # (1,1)-(1,2)
    grid.carve(1, 2, NORTH)  # (1,2)-(0,2) : seconde impasse
    grid.carve(1, 2, SOUTH)  # (1,2)-(2,2) : la sortie
    grid.carve(2, 0, EAST)  # (2,0)-(2,1)
    grid.carve(2, 1, EAST)  # (2,1)-(2,2)
    return grid


def random_maze(n: int, rng: RandomSource) -> WallGrid:
    """Labyrinthe parfait aléatoire via le générateur Recursive Backtracking."""
    return get_generator("recursive_backtracking").generate(n, rng)
