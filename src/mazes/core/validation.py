"""Vérifications structurelles d'un labyrinthe et d'un chemin.

Répond à une seule question : *le résultat est-il correct ?* Fournit aussi
:func:`solve_bruteforce`, le BFS de référence auquel tous les solveurs sont
comparés (le chemin est unique dans un labyrinthe parfait).
"""

from __future__ import annotations

from array import array
from collections import deque
from typing import TYPE_CHECKING

if TYPE_CHECKING:  # pragma: no cover
    from mazes.core.grid import WallGrid

Cell = tuple[int, int]

#: Type des tableaux d'indices (4 octets par élément, voir ``core.unionfind``).
_INDEX_TYPECODE = "i"


def _bfs(
    grid: WallGrid,
    depart: int,
    vus: bytearray,
    parents: array | None = None,
) -> int:
    """Parcours en largeur depuis ``depart`` (index linéaire) ; renvoie le nombre d'atteintes.

    ``vus`` peut être pré-rempli pour énumérer les composantes connexes. ``parents``
    reçoit l'index d'origine (le départ est son propre parent). Index linéaires,
    pas de tuples : une ``deque`` d'entiers évite ``n**2`` objets.
    """
    n = grid.n
    east = grid.east
    south = grid.south

    vus[depart] = 1
    file = deque([depart])
    atteintes = 1

    while file:
        idx = file.popleft()
        r, c = divmod(idx, n)

        # Est
        if c + 1 < n:
            j = idx
            voisin = idx + 1
            if not vus[voisin] and not (east[j >> 3] >> (j & 7)) & 1:
                vus[voisin] = 1
                if parents is not None:
                    parents[voisin] = idx
                file.append(voisin)
                atteintes += 1

        # Ouest : le mur est stocké chez le voisin, en tant que son mur Est
        if c > 0:
            voisin = idx - 1
            j = voisin
            if not vus[voisin] and not (east[j >> 3] >> (j & 7)) & 1:
                vus[voisin] = 1
                if parents is not None:
                    parents[voisin] = idx
                file.append(voisin)
                atteintes += 1

        # Sud
        if r + 1 < n:
            j = idx
            voisin = idx + n
            if not vus[voisin] and not (south[j >> 3] >> (j & 7)) & 1:
                vus[voisin] = 1
                if parents is not None:
                    parents[voisin] = idx
                file.append(voisin)
                atteintes += 1

        # Nord : le mur est stocké chez le voisin, en tant que son mur Sud
        if r > 0:
            voisin = idx - n
            j = voisin
            if not vus[voisin] and not (south[j >> 3] >> (j & 7)) & 1:
                vus[voisin] = 1
                if parents is not None:
                    parents[voisin] = idx
                file.append(voisin)
                atteintes += 1

    return atteintes


def _bfs_parents(grid: WallGrid, start: Cell) -> tuple[array, int]:
    """BFS depuis ``(row, col)`` : table des parents et nombre d'atteintes."""
    n = grid.n
    row, col = start
    if not (0 <= row < n and 0 <= col < n):
        raise IndexError(f"depart hors grille : {start} pour n={n}")

    parents = array(_INDEX_TYPECODE, [-1]) * (n * n)
    depart = row * n + col
    parents[depart] = depart
    atteintes = _bfs(grid, depart, bytearray(n * n), parents)
    return parents, atteintes


def _count_components(grid: WallGrid) -> int:
    """Nombre de composantes connexes du labyrinthe."""
    n = grid.n
    total = n * n
    vus = bytearray(total)
    composantes = 0

    for depart in range(total):
        if vus[depart]:
            continue
        composantes += 1
        _bfs(grid, depart, vus)

    return composantes


def count_open_passages(grid: WallGrid) -> int:
    """Compte les passages ouverts entre cellules voisines (``n**2 - 1`` pour un labyrinthe parfait).

    On compte les bits à 1 des deux tampons avec ``int.bit_count()`` (en C), puis
    on retire les bords droit/bas et les bits de remplissage — pas de boucle sur
    les ``2n(n-1)`` murs.
    """
    n = grid.n
    if n < 2:
        return 0  # aucune paire de cellules voisines

    east = grid.east
    south = grid.south

    murs = int.from_bytes(east, "little").bit_count()
    murs += int.from_bytes(south, "little").bit_count()

    hors_jeu = 0
    for r in range(n):  # bord droit, stocké dans east
        i = r * n + n - 1
        hors_jeu += (east[i >> 3] >> (i & 7)) & 1
    for c in range(n):  # bord bas, stocké dans south
        i = (n - 1) * n + c
        hors_jeu += (south[i >> 3] >> (i & 7)) & 1
    for i in range(n * n, len(east) * 8):  # bits de remplissage : au plus 7
        hors_jeu += (east[i >> 3] >> (i & 7)) & 1
        hors_jeu += (south[i >> 3] >> (i & 7)) & 1

    return 2 * n * (n - 1) - (murs - hors_jeu)


def count_reachable(grid: WallGrid, start: Cell = (0, 0)) -> int:
    """Nombre de cellules atteignables depuis ``start`` (``n**2`` si connexe)."""
    return _bfs_parents(grid, start)[1]


def is_connected(grid: WallGrid, start: Cell = (0, 0)) -> bool:
    """Indique si toutes les cellules sont atteignables depuis ``start``."""
    return count_reachable(grid, start) == grid.n * grid.n


def has_no_cycle(grid: WallGrid) -> bool:
    """Indique si le labyrinthe est sans boucle (``arêtes == sommets - composantes``)."""
    n = grid.n
    return count_open_passages(grid) == n * n - _count_components(grid)


def is_perfect(grid: WallGrid) -> bool:
    """Indique si le labyrinthe est parfait : connexe et sans boucle."""
    n = grid.n
    if count_open_passages(grid) != n * n - 1:
        return False
    return is_connected(grid)


def unique_path_exists(grid: WallGrid, a: Cell, b: Cell) -> bool:
    """Indique s'il existe exactement un chemin entre ``a`` et ``b``."""
    n = grid.n
    if not (0 <= a[0] < n and 0 <= a[1] < n):
        raise IndexError(f"cellule hors grille : {a} pour n={n}")
    if not (0 <= b[0] < n and 0 <= b[1] < n):
        raise IndexError(f"cellule hors grille : {b} pour n={n}")

    depart = a[0] * n + a[1]
    arrivee = b[0] * n + b[1]
    vus = bytearray(n * n)
    vus[depart] = 1

    return _count_paths(grid, depart, arrivee, vus, limite=2) == 1


def _count_paths(
    grid: WallGrid, idx: int, arrivee: int, vus: bytearray, limite: int
) -> int:
    """Compte les chemins simples de ``idx`` à ``arrivee``, en s'arrêtant à ``limite``."""
    if idx == arrivee:
        return 1

    n = grid.n
    east = grid.east
    south = grid.south
    total = 0
    r, c = divmod(idx, n)

    # Est
    if c + 1 < n:
        voisin = idx + 1
        j = idx
        if not vus[voisin] and not (east[j >> 3] >> (j & 7)) & 1:
            vus[voisin] = 1
            total += _count_paths(grid, voisin, arrivee, vus, limite - total)
            vus[voisin] = 0
            if total >= limite:
                return total

    # Ouest
    if c > 0:
        voisin = idx - 1
        j = voisin
        if not vus[voisin] and not (east[j >> 3] >> (j & 7)) & 1:
            vus[voisin] = 1
            total += _count_paths(grid, voisin, arrivee, vus, limite - total)
            vus[voisin] = 0
            if total >= limite:
                return total

    # Sud
    if r + 1 < n:
        voisin = idx + n
        j = idx
        if not vus[voisin] and not (south[j >> 3] >> (j & 7)) & 1:
            vus[voisin] = 1
            total += _count_paths(grid, voisin, arrivee, vus, limite - total)
            vus[voisin] = 0
            if total >= limite:
                return total

    # Nord
    if r > 0:
        voisin = idx - n
        j = voisin
        if not vus[voisin] and not (south[j >> 3] >> (j & 7)) & 1:
            vus[voisin] = 1
            total += _count_paths(grid, voisin, arrivee, vus, limite - total)
            vus[voisin] = 0

    return total


def solve_bruteforce(grid: WallGrid, start: Cell, goal: Cell) -> list[Cell] | None:
    """Cherche un chemin par BFS (la référence du projet), ``None`` si inatteignable.

    Le parent est enregistré à la **découverte** (pas au dépilage), pour obtenir
    le chemin de longueur minimale.
    """
    n = grid.n
    for cellule, nom in ((start, "depart"), (goal, "arrivee")):
        if not (0 <= cellule[0] < n and 0 <= cellule[1] < n):
            raise IndexError(f"{nom} hors grille : {cellule} pour n={n}")

    parents, _ = _bfs_parents(grid, start)
    arrivee = goal[0] * n + goal[1]
    if parents[arrivee] < 0:
        return None

    chemin: list[Cell] = []
    idx = arrivee
    depart = start[0] * n + start[1]
    while idx != depart:
        chemin.append(divmod(idx, n))
        idx = parents[idx]
    chemin.append(start)
    chemin.reverse()
    return chemin


def validate_path(
    grid: WallGrid,
    path: list[Cell] | tuple[Cell, ...],
    start: Cell = (0, 0),
    goal: Cell | None = None,
) -> list[str]:
    """Vérifie un chemin et renvoie la liste des problèmes (vide si correct)."""
    problemes: list[str] = []
    n = grid.n

    if not path:
        return ["le chemin est vide"]

    # --- départ et arrivée ------------------------------------------- #
    if path[0] != start:
        problemes.append(f"le chemin part de {path[0]} au lieu de {start}")
    if goal is not None and path[-1] != goal:
        problemes.append(f"le chemin arrive en {path[-1]} au lieu de {goal}")

    # --- chaque cellule est dans la grille ---------------------------- #
    for rang, (r, c) in enumerate(path):
        if not (0 <= r < n and 0 <= c < n):
            problemes.append(f"etape {rang} : la cellule {(r, c)} est hors grille")
    if problemes:
        return problemes

    # --- étapes adjacentes, sans mur entre elles ---------------------- #
    from mazes.core.grid import EAST, NORTH, SOUTH, WEST

    for rang in range(1, len(path)):
        r1, c1 = path[rang - 1]
        r2, c2 = path[rang]
        ecart = abs(r1 - r2) + abs(c1 - c2)
        if ecart != 1:
            problemes.append(
                f"etape {rang} : {(r1, c1)} -> {(r2, c2)} ne sont pas voisines (ecart {ecart})"
            )
            continue

        if r2 == r1 + 1:
            direction = SOUTH
        elif r2 == r1 - 1:
            direction = NORTH
        elif c2 == c1 + 1:
            direction = EAST
        else:
            direction = WEST

        if grid.has_wall(r1, c1, direction):
            problemes.append(
                f"etape {rang} : un mur separe {(r1, c1)} de {(r2, c2)}"
            )

    # --- aucune cellule répétée -------------------------------------- #
    if len(set(path)) != len(path):
        vues: set[Cell] = set()
        for rang, cellule in enumerate(path):
            if cellule in vues:
                problemes.append(f"etape {rang} : la cellule {cellule} est repetee")
                break
            vues.add(cellule)

    return problemes
