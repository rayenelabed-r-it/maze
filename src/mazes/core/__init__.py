"""Structures de bas niveau du projet.

Aucun algorithme de labyrinthe ici : uniquement le modele memoire
(:mod:`mazes.core.grid`), la structure d'ensembles disjoints
(:mod:`mazes.core.unionfind`), l'aleatoire reproductible
(:mod:`mazes.core.rng`) et les verifications structurelles
(:mod:`mazes.core.validation`).
"""

from mazes.core.grid import (
    DELTA_COL,
    DELTA_ROW,
    DIRECTION_NAMES,
    DIRECTIONS,
    EAST,
    NORTH,
    SOUTH,
    WEST,
    WallGrid,
    entry_cell,
    exit_cell,
)
from mazes.core.rng import DEFAULT_SEED, RandomSource
from mazes.core.unionfind import UnionFind
from mazes.core.validation import (
    count_open_passages,
    count_reachable,
    is_connected,
    is_perfect,
    solve_bruteforce,
    unique_path_exists,
    validate_path,
)

__all__ = [
    "DEFAULT_SEED",
    "DELTA_COL",
    "DELTA_ROW",
    "DIRECTIONS",
    "DIRECTION_NAMES",
    "EAST",
    "NORTH",
    "SOUTH",
    "WEST",
    "RandomSource",
    "UnionFind",
    "WallGrid",
    "count_open_passages",
    "count_reachable",
    "entry_cell",
    "exit_cell",
    "is_connected",
    "is_perfect",
    "solve_bruteforce",
    "unique_path_exists",
    "validate_path",
]
