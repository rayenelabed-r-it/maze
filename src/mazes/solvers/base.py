"""Interface commune aux solveurs : :class:`SolveResult`, :class:`Solver` et le registre.

Tout solveur prend une grille, un départ et une arrivée, et renvoie un
:class:`SolveResult` (chemin + masque d'état + métriques). Le masque ``state``
pilote le rendu ``o`` (chemin) / ``*`` (exploré hors chemin).
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from array import array
from dataclasses import dataclass, field
from math import isqrt
from typing import TYPE_CHECKING, TypeVar

if TYPE_CHECKING:  # pragma: no cover
    from mazes.core.grid import WallGrid

Cell = tuple[int, int]

#: Valeurs du masque d'état, indexé par ``row * n + col``.
UNVISITED = 0  # jamais atteinte ('.')
EXPLORED = 1  # atteinte puis abandonnée ('*')
ON_PATH = 2  # sur le chemin final ('o')


@dataclass(slots=True)
class SolveResult:
    """Résultat d'une résolution : chemin, masque d'état et métriques."""

    path: list[Cell]
    state: bytearray
    expanded: int = 0
    explored: int = 0
    max_frontier: int = 0
    elapsed_s: float = 0.0
    algorithm: str = ""
    extra: dict[str, float] = field(default_factory=dict)

    @property
    def path_length(self) -> int:
        """Nombre de cellules du chemin."""
        return len(self.path)

    @property
    def path_cost(self) -> int:
        """Nombre de déplacements, soit ``len(path) - 1``."""
        return max(0, len(self.path) - 1)

    @property
    def efficiency(self) -> float:
        """Rapport ``path_cost / expanded``, entre 0 et 1."""
        return self.path_cost / self.expanded if self.expanded else 0.0

    def state_at(self, row: int, col: int) -> int:
        """État d'une cellule, indexé par ``row * n + col`` (``n`` déduit par ``isqrt``)."""
        cote = isqrt(len(self.state))
        if not (0 <= row < cote and 0 <= col < cote):
            raise IndexError(f"cellule hors grille : ({row}, {col}) pour n={cote}")
        return self.state[row * cote + col]

    def __repr__(self) -> str:
        return (
            f"SolveResult(algorithm={self.algorithm!r}, path_length={self.path_length}, "
            f"expanded={self.expanded}, elapsed_s={self.elapsed_s:.4f})"
        )


class Solver(ABC):
    """Classe de base des solveurs : attributs ``name``/``description``/``complexity``/``optimal``."""

    name: str = ""
    description: str = ""
    complexity: str = ""
    optimal: bool = False

    @abstractmethod
    def solve(self, grid: WallGrid, start: Cell, goal: Cell) -> SolveResult:
        """Cherche un chemin de ``start`` à ``goal`` et renvoie le :class:`SolveResult`."""
        raise NotImplementedError

    def _reconstruct(
        self, parents: list[int] | array, start: Cell, goal: Cell, n: int
    ) -> list[Cell]:
        """Remonte la chaîne des parents de ``goal`` jusqu'à ``start`` (liste vide si non atteint)."""
        depart = start[0] * n + start[1]
        arrivee = goal[0] * n + goal[1]

        if arrivee != depart and parents[arrivee] < 0:
            return []

        chemin: list[Cell] = []
        index = arrivee
        while index != depart:
            chemin.append(divmod(index, n))
            index = parents[index]

        chemin.append(start)
        chemin.reverse()
        return chemin

    def _mark_states(self, path: list[Cell], state: bytearray, n: int) -> None:
        """Reporte le chemin final en :data:`ON_PATH` (écrase l'exploration)."""
        for row, col in path:
            state[row * n + col] = ON_PATH

    @staticmethod
    def _require_endpoints(grid: WallGrid, start: Cell, goal: Cell) -> None:
        """Vérifie que le départ et l'arrivée sont dans la grille."""
        n = grid.n
        for cellule, nom in ((start, "depart"), (goal, "arrivee")):
            row, col = cellule
            if not (0 <= row < n and 0 <= col < n):
                raise IndexError(f"{nom} hors grille : {cellule} pour n={n}")

    def __repr__(self) -> str:
        return f"{type(self).__name__}(name={self.name!r})"


# --------------------------------------------------------------------------- #
# Registre
# --------------------------------------------------------------------------- #

#: Table ``nom -> classe``, remplie par ``@register_solver``.
SOLVERS: dict[str, type[Solver]] = {}

_S = TypeVar("_S", bound=type[Solver])


def register_solver(cls: _S) -> _S:
    """Décorateur enregistrant une classe de solveur dans :data:`SOLVERS`."""
    if not cls.name:
        raise ValueError(f"{cls.__name__} doit definir un attribut 'name' non vide")
    existing = SOLVERS.get(cls.name)
    if existing is not None and existing is not cls:
        raise ValueError(
            f"le nom {cls.name!r} est deja pris par {existing.__name__} ; "
            f"choisir un nom distinct pour {cls.__name__}"
        )
    SOLVERS[cls.name] = cls
    return cls


def get_solver(name: str) -> Solver:
    """Renvoie une instance du solveur enregistré sous ``name``."""
    if not SOLVERS:
        _autodiscover()
    try:
        cls = SOLVERS[name]
    except KeyError:
        available = ", ".join(solver_choices()) or "(aucun)"
        raise KeyError(f"solveur inconnu : {name!r}. Disponibles : {available}") from None
    return cls()


def available_solvers() -> dict[str, type[Solver]]:
    """Copie du registre ``nom -> classe``."""
    if not SOLVERS:
        _autodiscover()
    return dict(SOLVERS)


def solver_choices() -> list[str]:
    """Liste triée des noms de solveurs."""
    return sorted(SOLVERS)


def _iter_solver_modules() -> list[str]:
    """Modules à importer pour peupler le registre."""
    return [
        "mazes.solvers.recursive_backtracking",
        "mazes.solvers.astar",
    ]


def _autodiscover() -> None:
    """Importe les modules de solveurs pour déclencher leurs enregistrements."""
    import importlib

    for module_name in _iter_solver_modules():
        importlib.import_module(module_name)


__all__ = [
    "EXPLORED",
    "ON_PATH",
    "SOLVERS",
    "UNVISITED",
    "SolveResult",
    "Solver",
    "available_solvers",
    "get_solver",
    "register_solver",
    "solver_choices",
]
