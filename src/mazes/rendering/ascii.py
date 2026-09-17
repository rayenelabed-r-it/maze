"""WallGrid <-> texte.

Format : une grille de (2n+1) x (2n+1) caractères.
  '#'  mur
  ' '  couloir
  '*'  cellule explorée par le solveur
  'o'  cellule du chemin solution
L'entrée est percée au-dessus de (0,0), la sortie sous (n-1, n-1).
"""

from __future__ import annotations

from mazes.core.grid import WallGrid
from mazes.solvers.base import EXPLORED, PATH

WALL = "#"
OPEN = " "
EXPLORED_CHAR = "*"
PATH_CHAR = "o"

_CHARS = {0: OPEN, EXPLORED: EXPLORED_CHAR, PATH: PATH_CHAR}


def to_ascii(grid: WallGrid, state: bytes | bytearray | None = None) -> str:
    """Rend la grille en texte. `state` vient de SolveResult.state."""
    n = grid.n
    if state is not None and len(state) != n * n:
        raise ValueError(f"state de taille {len(state)}, attendu {n * n}")

    lignes = [[WALL] * (2 * n + 1) for _ in range(2 * n + 1)]

    def char(cell) -> str:
        if state is None:
            return OPEN
        return _CHARS.get(state[grid.index(cell)], OPEN)

    for r in range(n):
        for c in range(n):
            ici = char((r, c))
            lignes[2 * r + 1][2 * c + 1] = ici
            if c + 1 < n and grid.is_open((r, c), (r, c + 1)):
                voisin = char((r, c + 1))
                lignes[2 * r + 1][2 * c + 2] = _liaison(ici, voisin)
            if r + 1 < n and grid.is_open((r, c), (r + 1, c)):
                voisin = char((r + 1, c))
                lignes[2 * r + 2][2 * c + 1] = _liaison(ici, voisin)

    # entrée et sortie
    lignes[0][1] = char((0, 0))
    lignes[2 * n][2 * n - 1] = char((n - 1, n - 1))

    return "\n".join("".join(ligne) for ligne in lignes)


def _liaison(a: str, b: str) -> str:
    """Le couloir entre deux cellules prend leur état commun, sinon reste vide."""
    if a == PATH_CHAR and b == PATH_CHAR:
        return PATH_CHAR
    if a in (PATH_CHAR, EXPLORED_CHAR) and b in (PATH_CHAR, EXPLORED_CHAR):
        return EXPLORED_CHAR
    return OPEN


def from_ascii(text: str) -> WallGrid:
    """Relit un labyrinthe écrit au format ci-dessus.

    Les marques '*' et 'o' d'une résolution précédente sont acceptées et
    ignorées : seule la position des murs compte.
    """
    lignes = [ligne.rstrip("\n") for ligne in text.splitlines() if ligne.strip()]
    if not lignes:
        raise ValueError("entrée vide")

    hauteur = len(lignes)
    if hauteur % 2 == 0:
        raise ValueError(f"nombre de lignes pair ({hauteur}) : format invalide")
    n = (hauteur - 1) // 2

    largeur = 2 * n + 1
    lignes = [ligne.ljust(largeur) for ligne in lignes]
    for i, ligne in enumerate(lignes):
        if len(ligne) != largeur:
            raise ValueError(f"ligne {i} de longueur {len(ligne)}, attendu {largeur}")

    grid = WallGrid(n)
    for r in range(n):
        for c in range(n):
            if c + 1 < n and lignes[2 * r + 1][2 * c + 2] != WALL:
                grid.carve((r, c), (r, c + 1))
            if r + 1 < n and lignes[2 * r + 2][2 * c + 1] != WALL:
                grid.carve((r, c), (r + 1, c))
    return grid


def read_ascii_file(path: str) -> WallGrid:
    with open(path, "r", encoding="utf-8") as f:
        return from_ascii(f.read())


def write_ascii_file(path: str, grid: WallGrid, state=None) -> str:
    with open(path, "w", encoding="utf-8") as f:
        f.write(to_ascii(grid, state))
        f.write("\n")
    return path
