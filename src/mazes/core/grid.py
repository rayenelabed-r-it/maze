"""Grille de murs compacte, structure de données centrale du projet.

On ne stocke que deux murs par cellule — Est et Sud — à raison d'**un bit par
mur**, soit ``n**2 / 4`` octets. Le mur Nord d'une cellule est le mur Sud de la
cellule au-dessus ; le mur Ouest, le mur Est de celle à gauche. Voir ``doc/02-grille.md``.
"""

from __future__ import annotations

from collections.abc import Iterator
from typing import TYPE_CHECKING

if TYPE_CHECKING:  # pragma: no cover
    import numpy as np

# --------------------------------------------------------------------------- #
# Directions
# --------------------------------------------------------------------------- #
#: Nord, Est, Sud, Ouest, dans le sens horaire (l'opposée est ``(d + 2) % 4``).
NORTH, EAST, SOUTH, WEST = 0, 1, 2, 3

#: Décalages de ligne / colonne par direction.
DELTA_ROW: tuple[int, int, int, int] = (-1, 0, 1, 0)
DELTA_COL: tuple[int, int, int, int] = (0, 1, 0, -1)

#: Noms lisibles, pour les messages d'erreur et les tests.
DIRECTION_NAMES: tuple[str, str, str, str] = ("N", "E", "S", "W")

#: Les quatre directions, pour ``for d in DIRECTIONS``.
DIRECTIONS: tuple[int, int, int, int] = (NORTH, EAST, SOUTH, WEST)


# --------------------------------------------------------------------------- #
# Tableau dense
# --------------------------------------------------------------------------- #
# Ces valeurs sont produites par :meth:`WallGrid.to_dense` ; le rendu les traduit
# en niveaux de gris. Définies ici (pas dans le rendu) car c'est ``to_dense`` qui
# les produit.

#: Cellule libre, sans parcours.
DENSE_FREE = 0

#: Mur (et valeur des coins).
DENSE_WALL = 1

#: Cellule du chemin solution (rendue ``o``).
DENSE_PATH = 2

#: Cellule atteinte puis abandonnée (rendue ``*``). Valeur 3, pas 1 : l'état
#: ``EXPLORED`` du solveur vaut 1 et entrerait en collision avec ``DENSE_WALL``.
DENSE_EXPLORED = 3

#: Budget mémoire du tableau dense, en octets (512 Mio).
DENSE_MEMORY_BUDGET = 512 * 1024 * 1024


class WallGrid:
    """Grille de murs d'un labyrinthe ``n x n``, stockée en bits.

    ``east``/``south`` : ``bytearray`` de ``ceil(n**2/8)`` octets, bit 1 = mur présent.
    """

    __slots__ = ("east", "entry_open", "exit_open", "n", "south")

    def __init__(self, n: int, *, closed: bool = True) -> None:
        """Alloue une grille ``n x n`` (``closed=True`` : tous murs, sinon ouverte)."""
        if not isinstance(n, int) or isinstance(n, bool):
            raise TypeError(f"n doit etre un entier, recu {type(n).__name__}")
        if n < 1:
            raise ValueError(f"n doit etre >= 1, recu {n}")

        self.n = n
        n_cells = n * n
        n_bytes = (n_cells + 7) // 8

        initial = 0xFF if closed else 0x00
        self.east = bytearray([initial]) * n_bytes
        self.south = bytearray([initial]) * n_bytes

        # Bits non significatifs fixés à 1 (canonique), quel que soit ``closed``,
        # pour que ``__eq__`` (comparaison des tampons) voie deux grilles identiques.
        for r in range(n):
            i = r * n + n - 1  # bord droit, dans east
            self.east[i >> 3] |= 1 << (i & 7)
        for c in range(n):
            i = (n - 1) * n + c  # bord bas, dans south
            self.south[i >> 3] |= 1 << (i & 7)

        reste = n_cells & 7
        if reste:  # bits de remplissage du dernier octet
            complement = (~((1 << reste) - 1)) & 0xFF
            self.east[-1] |= complement
            self.south[-1] |= complement

        self.entry_open = True
        self.exit_open = True

    # ------------------------------------------------------------------ #
    # Plomberie d'indexation
    # ------------------------------------------------------------------ #
    def index(self, row: int, col: int) -> int:
        """Index linéaire de la cellule ``(row, col)``, soit ``row * n + col``."""
        return row * self.n + col

    def memory_bytes(self) -> int:
        """Empreinte mémoire de la grille, en octets (≈ ``n**2 / 4``)."""
        return len(self.east) + len(self.south)

    # ------------------------------------------------------------------ #
    # Plomberie interne
    # ------------------------------------------------------------------ #
    @staticmethod
    def _bit(mask: bytearray, index: int) -> bool:
        """Lit le bit d'index ``index`` dans ``mask``."""
        return bool((mask[index >> 3] >> (index & 7)) & 1)

    @staticmethod
    def _set_bit(mask: bytearray, index: int, value: bool) -> None:
        """Écrit le bit d'index ``index`` dans ``mask``."""
        if value:
            mask[index >> 3] |= 1 << (index & 7)
        else:
            mask[index >> 3] &= ~(1 << (index & 7))

    def _require_cell(self, row: int, col: int) -> None:
        """Vérifie que ``(row, col)`` désigne une cellule de la grille."""
        if not (0 <= row < self.n and 0 <= col < self.n):
            raise IndexError(f"cellule hors grille : ({row}, {col}) pour n={self.n}")

    @staticmethod
    def _require_direction(direction: int) -> None:
        """Vérifie que ``direction`` est l'une des quatre directions."""
        if direction not in (NORTH, EAST, SOUTH, WEST):
            raise ValueError(f"direction inconnue : {direction!r}")

    def _require_boundary_change(self, present: bool, ou: str) -> None:
        """Refuse de percer une bordure autre que l'entrée ou la sortie."""
        if not present:
            raise ValueError(
                f"impossible de percer {ou} : les seules ouvertures du bord "
                f"exterieur sont l'entree (0, 0) et la sortie ({self.n - 1}, {self.n - 1})"
            )

    # ------------------------------------------------------------------ #
    # Lecture / écriture des murs
    # ------------------------------------------------------------------ #
    def has_wall(self, row: int, col: int, direction: int) -> bool:
        """Indique si un mur borde ``(row, col)`` dans ``direction`` (bord extérieur = mur, sauf entrée/sortie)."""
        self._require_cell(row, col)
        self._require_direction(direction)
        n = self.n

        if direction == EAST:
            if col == n - 1:
                return True  # bord droit, jamais percé
            return self._bit(self.east, row * n + col)

        if direction == WEST:
            if col == 0:
                return True  # bord gauche, jamais percé
            return self._bit(self.east, row * n + col - 1)

        if direction == SOUTH:
            if row == n - 1:
                return not (col == n - 1 and self.exit_open)
            return self._bit(self.south, row * n + col)

        # NORTH
        if row == 0:
            return not (col == 0 and self.entry_open)
        return self._bit(self.south, (row - 1) * n + col)

    def set_wall(self, row: int, col: int, direction: int, present: bool) -> None:
        """Pose (``present=True``) ou perce (``present=False``) un mur.

        Sur l'entrée/sortie, agit sur ``entry_open``/``exit_open``.
        """
        self._require_cell(row, col)
        self._require_direction(direction)
        n = self.n

        # --- bordures extérieures ------------------------------------- #
        if direction == EAST and col == n - 1:
            self._require_boundary_change(present, f"le bord droit de {(row, col)}")
            return
        if direction == WEST and col == 0:
            self._require_boundary_change(present, f"le bord gauche de {(row, col)}")
            return
        if direction == NORTH and row == 0:
            if col == 0:
                self.entry_open = not present
                return
            self._require_boundary_change(present, f"le bord superieur de {(row, col)}")
            return
        if direction == SOUTH and row == n - 1:
            if col == n - 1:
                self.exit_open = not present
                return
            self._require_boundary_change(present, f"le bord inferieur de {(row, col)}")
            return

        # --- murs internes (stockés chez la cellule de plus petit index) --- #
        if direction == EAST:
            self._set_bit(self.east, row * n + col, present)
        elif direction == WEST:
            self._set_bit(self.east, row * n + col - 1, present)
        elif direction == SOUTH:
            self._set_bit(self.south, row * n + col, present)
        else:  # NORTH
            self._set_bit(self.south, (row - 1) * n + col, present)

    def carve(self, row: int, col: int, direction: int) -> None:
        """Perce le mur entre ``(row, col)`` et son voisin dans ``direction``."""
        self.set_wall(row, col, direction, present=False)

    def is_boundary_open(self, row: int, col: int, direction: int) -> bool:
        """Indique si une bordure extérieure est percée (entrée ou sortie)."""
        self._require_cell(row, col)
        self._require_direction(direction)
        n = self.n

        if direction == NORTH and row == 0 and col == 0:
            return self.entry_open
        if direction == SOUTH and row == n - 1 and col == n - 1:
            return self.exit_open
        return False

    def wall_at(self, row: int, col: int, direction: int) -> tuple[int, int] | None:
        """Localise le bit du mur : ``(index de cellule, 0=Est / 1=Sud)``, ou ``None`` si bordure."""
        self._require_cell(row, col)
        self._require_direction(direction)
        n = self.n

        if direction == EAST:
            if col == n - 1:
                return None
            return row * n + col, 0
        if direction == WEST:
            if col == 0:
                return None
            return row * n + col - 1, 0
        if direction == SOUTH:
            if row == n - 1:
                return None
            return row * n + col, 1
        if row == 0:
            return None
        return (row - 1) * n + col, 1

    # ------------------------------------------------------------------ #
    # Parcours du voisinage
    # ------------------------------------------------------------------ #
    def in_bounds(self, row: int, col: int) -> bool:
        """Indique si ``(row, col)`` désigne une cellule de la grille."""
        return 0 <= row < self.n and 0 <= col < self.n

    def iter_neighbors(self, row: int, col: int) -> Iterator[tuple[int, int, int]]:
        """Itère sur ``(voisin_row, voisin_col, direction)``, qu'un mur les sépare ou non."""
        self._require_cell(row, col)
        n = self.n

        for d in DIRECTIONS:
            nr = row + DELTA_ROW[d]
            nc = col + DELTA_COL[d]
            if 0 <= nr < n and 0 <= nc < n:
                yield nr, nc, d

    def iter_passages(self, row: int, col: int) -> Iterator[tuple[int, int, int]]:
        """Itère sur les voisins **accessibles** depuis ``(row, col)``."""
        self._require_cell(row, col)
        n = self.n
        east = self.east
        south = self.south

        for d in DIRECTIONS:
            nr = row + DELTA_ROW[d]
            nc = col + DELTA_COL[d]
            if not (0 <= nr < n and 0 <= nc < n):
                continue

            if d == EAST:
                i = row * n + col
                if (east[i >> 3] >> (i & 7)) & 1:
                    continue
            elif d == WEST:
                i = row * n + col - 1
                if (east[i >> 3] >> (i & 7)) & 1:
                    continue
            elif d == SOUTH:
                i = row * n + col
                if (south[i >> 3] >> (i & 7)) & 1:
                    continue
            else:  # NORTH
                i = (row - 1) * n + col
                if (south[i >> 3] >> (i & 7)) & 1:
                    continue

            yield nr, nc, d

    def iter_cells(self) -> Iterator[tuple[int, int]]:
        """Itère sur toutes les cellules, ligne par ligne."""
        n = self.n
        for r in range(n):
            for c in range(n):
                yield r, c

    # ------------------------------------------------------------------ #
    # Conversion
    # ------------------------------------------------------------------ #
    def to_dense(self, state: bytearray | None = None) -> np.ndarray:
        """Développe la grille en tableau dense ``(2n+1, 2n+1)`` de ``uint8``.

        Vectorisé : quatre affectations par tranches, pas de boucle Python. Les
        tranches sont des vues, donc l'affectation écrit en place.
        """
        import numpy as np

        n = self.n
        cote = 2 * n + 1
        taille = cote * cote
        if taille > DENSE_MEMORY_BUDGET:
            raise MemoryError(
                f"le tableau dense ferait {taille / 1024**2:.0f} Mio pour n={n}, "
                f"au-dela de la limite de {DENSE_MEMORY_BUDGET // 1024**2} Mio. "
                f"Utiliser render_dense_banded, qui procede par bandes."
            )

        dense = np.empty((cote, cote), dtype=np.uint8)

        # ``bitorder="little"`` est indispensable : notre codage range le bit
        # d'index ``i & 7`` au poids faible. Sans lui, les murs seraient lus à
        # l'envers — un labyrinthe plausible mais faux, sans erreur levée.
        # ``[: n * n]`` écarte les bits de remplissage du dernier octet.
        murs_est = np.unpackbits(
            np.frombuffer(self.east, dtype=np.uint8), bitorder="little"
        )[: n * n].reshape(n, n).astype(bool)
        murs_sud = np.unpackbits(
            np.frombuffer(self.south, dtype=np.uint8), bitorder="little"
        )[: n * n].reshape(n, n).astype(bool)

        # Murs horizontaux (dense[0::2, 1::2]) : la ligne 2r porte le mur Sud de (r-1, c).
        horizontaux = dense[0::2, 1::2]  # vue (n+1, n)
        horizontaux[:] = DENSE_WALL
        if n >= 2:
            horizontaux[1:-1] = np.where(murs_sud[:-1], DENSE_WALL, DENSE_FREE)
        if self.entry_open:
            horizontaux[0, 0] = DENSE_FREE
        if self.exit_open:
            horizontaux[-1, -1] = DENSE_FREE

        # Murs verticaux (dense[1::2, 0::2]) : la colonne 2c porte le mur Est de (r, c-1).
        verticaux = dense[1::2, 0::2]  # vue (n, n+1)
        verticaux[:] = DENSE_WALL
        if n >= 2:
            verticaux[:, 1:-1] = np.where(murs_est[:, :-1], DENSE_WALL, DENSE_FREE)

        # Coins : toujours des murs.
        dense[0::2, 0::2] = DENSE_WALL

        # Cellules (dense[1::2, 1::2]).
        cellules = dense[1::2, 1::2]  # vue (n, n)
        if state is None:
            cellules[:] = DENSE_FREE
        else:
            etats = np.frombuffer(state, dtype=np.uint8).reshape(n, n)
            # Table etat du solveur -> valeur dense, en une seule indexation.
            cellules[:] = np.array(
                [DENSE_FREE, DENSE_EXPLORED, DENSE_PATH], dtype=np.uint8
            )[etats]

        return dense

    def cell_state_array(self, result: object) -> bytearray:
        """Masque d'état d'un ``SolveResult``, sans copie (valide sa taille ``n**2``)."""
        state = getattr(result, "state", None)
        if state is None:
            raise TypeError(
                f"{type(result).__name__} n'a pas d'attribut 'state' : "
                f"attendu un SolveResult"
            )
        attendu = self.n * self.n
        if len(state) != attendu:
            raise ValueError(
                f"le masque fait {len(state)} octets au lieu de {attendu} "
                f"pour n={self.n}"
            )
        return state  # type: ignore[no-any-return]

    # ------------------------------------------------------------------ #
    # Vérification
    # ------------------------------------------------------------------ #
    def is_perfect(self) -> bool:
        """Vérifie que le labyrinthe est parfait (connexe et sans boucle)."""
        from mazes.core.validation import is_perfect

        return is_perfect(self)

    def __eq__(self, other: object) -> bool:
        if not isinstance(other, WallGrid):
            return NotImplemented
        return (
            self.n == other.n
            and self.east == other.east
            and self.south == other.south
            and self.entry_open == other.entry_open
            and self.exit_open == other.exit_open
        )

    def __repr__(self) -> str:
        return (
            f"WallGrid(n={self.n}, entry_open={self.entry_open}, "
            f"exit_open={self.exit_open}, bytes={self.memory_bytes()})"
        )


def entry_cell(grid: WallGrid) -> tuple[int, int]:
    """Cellule d'entrée : ``(0, 0)``."""
    return (0, 0)


def exit_cell(grid: WallGrid) -> tuple[int, int]:
    """Cellule de sortie : ``(n-1, n-1)``."""
    return (grid.n - 1, grid.n - 1)
