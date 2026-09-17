"""Interface Solver, SolveResult et registre par décorateur."""

from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass, field

from mazes.core.grid import Cell, WallGrid

UNVISITED = 0
EXPLORED = 1   # rendu '*'
PATH = 2       # rendu 'o'


@dataclass
class SolveResult:
    path: list[Cell]
    state: bytearray          # n² octets : 0 non visité, 1 exploré, 2 chemin
    expanded: int = 0         # cellules développées -> efficacité
    explored: int = 0         # cellules atteintes
    max_frontier: int = 0     # pic de la structure d'attente -> mémoire
    elapsed_s: float = 0.0
    algorithm: str = ""
    extras: dict = field(default_factory=dict)

    @property
    def found(self) -> bool:
        return bool(self.path)

    @property
    def length(self) -> int:
        return len(self.path)


class Solver(ABC):
    name: str = ""
    description: str = ""
    complexity: str = ""
    optimal: bool = False

    @abstractmethod
    def solve(self, grid: WallGrid, start: Cell, goal: Cell) -> SolveResult: ...

    # Aide commune : marquer le chemin par-dessus l'exploration
    @staticmethod
    def _mark(grid: WallGrid, state: bytearray, path: list[Cell]) -> None:
        for cellule in path:
            state[grid.index(cellule)] = PATH


_REGISTRY: dict[str, type[Solver]] = {}


def register_solver(cls: type[Solver]) -> type[Solver]:
    if not cls.name:
        raise ValueError(f"{cls.__name__} n'a pas de nom")
    if cls.name in _REGISTRY:
        raise ValueError(f"solveur déjà enregistré : {cls.name!r}")
    _REGISTRY[cls.name] = cls
    return cls


def get_solver(name: str) -> Solver:
    try:
        return _REGISTRY[name]()
    except KeyError:
        valides = ", ".join(sorted(_REGISTRY))
        raise KeyError(f"solveur inconnu : {name!r}. Disponibles : {valides}") from None


def available_solvers() -> list[type[Solver]]:
    return [_REGISTRY[k] for k in sorted(_REGISTRY)]
