"""Solveurs de labyrinthes.

Importer ce paquet suffit à peupler le registre : chaque module s'enregistre
lui-même via ``@register_solver``. Les deux solveurs trouvent le même chemin dans
un labyrinthe parfait (il est unique) ; ils diffèrent par le coût de la recherche.
"""

from mazes.solvers import (  # noqa: F401  (effet de bord : enregistrement)
    astar,
    recursive_backtracking,
)
from mazes.solvers.astar import AStarSolver, build_heuristic
from mazes.solvers.base import (
    EXPLORED,
    ON_PATH,
    SOLVERS,
    UNVISITED,
    Solver,
    SolveResult,
    available_solvers,
    get_solver,
    register_solver,
    solver_choices,
)
from mazes.solvers.recursive_backtracking import RecursiveBacktrackingSolver

__all__ = [
    "EXPLORED",
    "ON_PATH",
    "SOLVERS",
    "UNVISITED",
    "AStarSolver",
    "RecursiveBacktrackingSolver",
    "SolveResult",
    "Solver",
    "available_solvers",
    "build_heuristic",
    "get_solver",
    "register_solver",
    "solver_choices",
]
