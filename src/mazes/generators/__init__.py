"""Importer ce paquet suffit à enregistrer tous les générateurs."""

from mazes.generators import kruskal, prim, recursive_backtracking  # noqa: F401
from mazes.generators.base import (  # noqa: F401
    Generator,
    available_generators,
    get_generator,
    register_generator,
)
