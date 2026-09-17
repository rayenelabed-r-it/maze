"""Interface Generator + registre par décorateur."""

from __future__ import annotations

from abc import ABC, abstractmethod

from mazes.core.grid import WallGrid
from mazes.core.rng import RandomSource

#: Table ``nom -> classe``, remplie par ``@register_generator``.
GENERATORS: dict[str, type[Generator]] = {}


class Generator(ABC):
    name: str = ""
    description: str = ""
    complexity: str = ""

    @abstractmethod
    def generate(self, n: int, rng: RandomSource) -> WallGrid:
        """Renvoie un labyrinthe parfait de taille n x n."""


def register_generator(cls: type[Generator]) -> type[Generator]:
    if not cls.name:
        raise ValueError(f"{cls.__name__} n'a pas de nom")
    if cls.name in GENERATORS:
        raise ValueError(f"générateur déjà enregistré : {cls.name!r}")
    GENERATORS[cls.name] = cls
    return cls


def get_generator(name: str) -> Generator:
    try:
        return GENERATORS[name]()
    except KeyError:
        valides = ", ".join(sorted(GENERATORS))
        raise KeyError(f"générateur inconnu : {name!r}. Disponibles : {valides}") from None


def available_generators() -> dict[str, type[Generator]]:
    return dict(GENERATORS)


def generator_choices() -> list[str]:
    return sorted(GENERATORS)
