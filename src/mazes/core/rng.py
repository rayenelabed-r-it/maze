"""RandomSource : aléatoire reproductible, partagé par générateurs et solveurs.

Expose à la fois l'attribut ``python`` (un ``random.Random``, utilisé par les
solveurs et les tests) et des méthodes de convenance ``randrange``/``choice``/
``shuffle`` (utilisées par les générateurs).
"""

from __future__ import annotations

import random
from collections.abc import MutableSequence, Sequence
from typing import TypeVar

T = TypeVar("T")

#: Graine par défaut.
DEFAULT_SEED = 20250101


class RandomSource:
    __slots__ = ("python", "seed")

    def __init__(self, seed: int | None = None) -> None:
        if seed is None:
            seed = random.SystemRandom().randrange(2**32)
        self.seed = int(seed)
        self.python = random.Random(self.seed)

    def randrange(self, stop: int) -> int:
        return self.python.randrange(stop)

    def choice(self, seq: Sequence[T]) -> T:
        return seq[self.python.randrange(len(seq))]

    def shuffle(self, seq: MutableSequence) -> None:
        self.python.shuffle(seq)

    def __repr__(self) -> str:
        return f"RandomSource(seed={self.seed})"
