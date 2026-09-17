"""Importer ce paquet suffit à enregistrer tous les solveurs."""

from mazes.solvers import astar, dijkstra, recursive_backtracking  # noqa: F401
from mazes.solvers.base import (  # noqa: F401
    SolveResult,
    Solver,
    available_solvers,
    get_solver,
    register_solver,
)
