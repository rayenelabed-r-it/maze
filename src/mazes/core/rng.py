"""RandomSource : aléatoire reproductible.

Le prototype appelait `random.shuffle` / `random.randrange` sur le module
global : impossible de rejouer un labyrinthe. Ici, chaque génération reçoit
une source explicite, et `--seed` suffit à reproduire exactement le résultat.
"""

from __future__ import annotations

import random
from typing import MutableSequence, Sequence, TypeVar

T = TypeVar("T")


class RandomSource:
    __slots__ = ("seed", "_rng")

    def __init__(self, seed: int | None = None) -> None:
        if seed is None:
            seed = random.SystemRandom().randrange(2**32)
        self.seed = seed
        self._rng = random.Random(seed)

    def randrange(self, stop: int) -> int:
        return self._rng.randrange(stop)

    def choice(self, seq: Sequence[T]) -> T:
        return seq[self._rng.randrange(len(seq))]

    def shuffle(self, seq: MutableSequence) -> None:
        self._rng.shuffle(seq)

    def __repr__(self) -> str:
        return f"RandomSource(seed={self.seed})"
