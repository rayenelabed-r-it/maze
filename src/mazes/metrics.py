"""Chronométrage et mesure mémoire."""

from __future__ import annotations

import time
import tracemalloc
from collections.abc import Callable
from dataclasses import dataclass
from typing import TypeVar

T = TypeVar("T")


@dataclass
class Measurement:
    result: object
    elapsed_s: float
    peak_kib: float

    def __str__(self) -> str:
        return f"{self.elapsed_s * 1000:.1f} ms, pic {self.peak_kib:.0f} Kio"


def measure(fn: Callable[[], T], trace_memory: bool = True) -> Measurement:
    """Exécute `fn` en mesurant durée et pic d'allocation.

    tracemalloc ralentit sensiblement le code mesuré : pour un benchmark de
    temps pur, appeler avec trace_memory=False.
    """
    if trace_memory:
        tracemalloc.start()
    debut = time.perf_counter()
    resultat = fn()
    duree = time.perf_counter() - debut
    if trace_memory:
        _, pic = tracemalloc.get_traced_memory()
        tracemalloc.stop()
    else:
        pic = 0
    return Measurement(result=resultat, elapsed_s=duree, peak_kib=pic / 1024)
