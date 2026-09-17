"""Générateurs de labyrinthes parfaits.

Importer ce paquet enregistre les algorithmes via ``@register_generator``.
"""

from mazes.generators import (  # noqa: F401  (effet de bord : enregistrement)
    kruskal,
    prim,
    recursive_backtracking,
)
from mazes.generators.base import (
    GENERATORS,
    Generator,
    available_generators,
    generator_choices,
    get_generator,
    register_generator,
)
from mazes.generators.kruskal import KruskalGenerator
from mazes.generators.prim import PrimGenerator
from mazes.generators.recursive_backtracking import RecursiveBacktrackingGenerator

__all__ = [
    "GENERATORS",
    "Generator",
    "KruskalGenerator",
    "PrimGenerator",
    "RecursiveBacktrackingGenerator",
    "available_generators",
    "generator_choices",
    "get_generator",
    "register_generator",
]
