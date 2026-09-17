"""WallGrid : la grille compacte, 2 bits par cellule.

Chaque cellule ne stocke que deux passages : vers l'Est et vers le Sud.
Les passages Nord/Ouest sont ceux de la cellule voisine, donc chaque mur
n'est stocké qu'une seule fois. Pour n = 1000, cela fait 250 Ko au lieu
de plusieurs dizaines de Mo avec un set de tuples.
"""

from __future__ import annotations

from typing import Iterable, Iterator

Cell = tuple[int, int]

_EAST = 0
_SOUTH = 1


class WallGrid:
    """Grille carrée n x n. Au départ, tous les murs sont fermés."""

    __slots__ = ("n", "_bits")

    def __init__(self, n: int) -> None:
        if n < 1:
            raise ValueError(f"taille de grille invalide : {n}")
        self.n = n
        # 2 bits par cellule -> 4 cellules par octet
        self._bits = bytearray((n * n + 3) // 4)

    # ---------------------------------------------------------------- bits

    def _get(self, index: int, bit: int) -> bool:
        shift = 2 * (index % 4) + bit
        return bool(self._bits[index // 4] >> shift & 1)

    def _set(self, index: int, bit: int) -> None:
        shift = 2 * (index % 4) + bit
        self._bits[index // 4] |= 1 << shift

    # ------------------------------------------------------------ cellules

    def in_bounds(self, cell: Cell) -> bool:
        r, c = cell
        return 0 <= r < self.n and 0 <= c < self.n

    def index(self, cell: Cell) -> int:
        """Indice linéaire de la cellule, utilisé aussi pour `state`."""
        r, c = cell
        return r * self.n + c

    def cells(self) -> Iterator[Cell]:
        for r in range(self.n):
            for c in range(self.n):
                yield (r, c)

    def neighbors(self, cell: Cell) -> list[Cell]:
        """Voisins dans la grille, murs compris."""
        r, c = cell
        candidats = ((r - 1, c), (r + 1, c), (r, c - 1), (r, c + 1))
        return [v for v in candidats if self.in_bounds(v)]

    # -------------------------------------------------------------- murs

    def _slot(self, a: Cell, b: Cell) -> tuple[int, int]:
        """Renvoie (index, bit) du mur entre a et b, qui doivent être voisines."""
        (ra, ca), (rb, cb) = a, b
        if not (self.in_bounds(a) and self.in_bounds(b)):
            raise ValueError(f"cellule hors grille : {a} / {b}")
        if ra == rb and cb == ca + 1:
            return self.index(a), _EAST
        if ra == rb and ca == cb + 1:
            return self.index(b), _EAST
        if ca == cb and rb == ra + 1:
            return self.index(a), _SOUTH
        if ca == cb and ra == rb + 1:
            return self.index(b), _SOUTH
        raise ValueError(f"cellules non adjacentes : {a} et {b}")

    def is_open(self, a: Cell, b: Cell) -> bool:
        """Vrai si le mur entre a et b a été abattu."""
        index, bit = self._slot(a, b)
        return self._get(index, bit)

    def carve(self, a: Cell, b: Cell) -> None:
        """Abat le mur entre deux cellules adjacentes."""
        index, bit = self._slot(a, b)
        self._set(index, bit)

    def accessible(self, cell: Cell) -> list[Cell]:
        """Voisins réellement atteignables (mur abattu). C'est l'API utilisée
        par les solveurs : aucun solveur ne manipule les bits directement."""
        r, c = cell
        out = []
        if c + 1 < self.n and self._get(self.index(cell), _EAST):
            out.append((r, c + 1))
        if r + 1 < self.n and self._get(self.index(cell), _SOUTH):
            out.append((r + 1, c))
        if c > 0 and self._get(self.index((r, c - 1)), _EAST):
            out.append((r, c - 1))
        if r > 0 and self._get(self.index((r - 1, c)), _SOUTH):
            out.append((r - 1, c))
        return out

    def passages(self) -> Iterator[tuple[Cell, Cell]]:
        """Itère sur tous les murs abattus, une seule fois chacun."""
        for r in range(self.n):
            for c in range(self.n):
                i = self.index((r, c))
                if c + 1 < self.n and self._get(i, _EAST):
                    yield ((r, c), (r, c + 1))
                if r + 1 < self.n and self._get(i, _SOUTH):
                    yield ((r, c), (r + 1, c))

    def count_passages(self) -> int:
        return sum(1 for _ in self.passages())

    # ------------------------------------------------------- constructeurs

    @classmethod
    def from_passages(cls, n: int, passages: Iterable[tuple[Cell, Cell]]) -> "WallGrid":
        grid = cls(n)
        for a, b in passages:
            grid.carve(a, b)
        return grid

    @property
    def entry(self) -> Cell:
        return (0, 0)

    @property
    def goal(self) -> Cell:
        return (self.n - 1, self.n - 1)

    def __eq__(self, other: object) -> bool:
        return (
            isinstance(other, WallGrid)
            and other.n == self.n
            and other._bits == self._bits
        )

    def __repr__(self) -> str:
        return f"WallGrid(n={self.n}, passages={self.count_passages()})"
