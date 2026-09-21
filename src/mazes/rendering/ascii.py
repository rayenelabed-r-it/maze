"""Conversion entre une :class:`~mazes.core.grid.WallGrid` et sa forme ASCII.

Une cellule ``(r, c)`` occupe ``(2r+1, 2c+1)`` d'une grille de ``(2n+1)`` par
``(2n+1)`` caractères ; les positions paires portent les murs. Écriture en flux,
ligne par ligne, avec des ``\\n`` explicites. Voir ``doc/05-export.md``.
"""

from __future__ import annotations

import math
from collections.abc import Iterator
from dataclasses import dataclass
from pathlib import Path
from typing import TYPE_CHECKING, TextIO

from mazes.core.grid import EAST, SOUTH, WallGrid

if TYPE_CHECKING:  # pragma: no cover
    pass

#: Fins de ligne : toujours ``\n``, jamais ``os.linesep``.
NEWLINE = "\n"

#: Encodage des fichiers ASCII.
ENCODING = "ascii"


@dataclass(frozen=True, slots=True)
class Charset:
    """Jeu de caractères du rendu ASCII (configurable pour les tests et la console)."""

    wall: str = "#"
    free: str = "."
    path: str = "o"
    explored: str = "*"
    entry: str = "."
    exit: str = "."

    def for_state(self, state_value: int) -> str:
        """Caractère d'une valeur de masque : ``0`` -> free, ``1`` -> explored, ``2`` -> path."""
        if state_value == 2:
            return self.path
        if state_value == 1:
            return self.explored
        return self.free

    def validate(self) -> None:
        """Vérifie que le jeu est utilisable : 1 caractère ASCII chacun, marqueurs distincts."""
        marqueurs = {
            "wall": self.wall,
            "free": self.free,
            "path": self.path,
            "explored": self.explored,
        }
        for nom, caractere in {**marqueurs, "entry": self.entry, "exit": self.exit}.items():
            if len(caractere) != 1:
                raise ValueError(
                    f"{nom} doit faire exactement un caractere, recu {caractere!r}"
                )
            if not caractere.isascii():
                raise ValueError(f"{nom} doit etre un caractere ASCII, recu {caractere!r}")

        vus: dict[str, str] = {}
        for nom, caractere in marqueurs.items():
            if caractere in vus:
                raise ValueError(
                    f"{nom} et {vus[caractere]} ont le meme caractere {caractere!r}"
                )
            vus[caractere] = nom

        for nom in ("entry", "exit"):
            if getattr(self, nom) == self.wall:
                raise ValueError(f"{nom} ne peut pas etre le caractere de mur {self.wall!r}")


#: Jeu de caractères par défaut, conforme à l'énoncé.
DEFAULT_CHARSET = Charset()


def iter_ascii_lines(
    grid: WallGrid,
    state: bytearray | None = None,
    charset: Charset = DEFAULT_CHARSET,
) -> Iterator[str]:
    """Produit les ``2n + 1`` lignes du rendu ASCII, une à une."""
    charset.validate()
    n = grid.n
    cote = 2 * n + 1

    o_mur = ord(charset.wall)
    o_libre = ord(charset.free)
    o_chemin = ord(charset.path)
    o_explore = ord(charset.explored)
    o_haut = ord(charset.entry) if grid.entry_open else o_mur
    o_bas = ord(charset.exit) if grid.exit_open else o_mur

    east = grid.east
    south = grid.south
    ligne = bytearray(cote)  # réallouée une fois, réutilisée

    for gr in range(cote):
        if gr % 2 == 0:
            # Ligne de murs horizontaux.
            r = gr // 2
            for gc in range(cote):
                ligne[gc] = o_mur

            if r == 0:
                ligne[1] = o_haut  # entrée, au-dessus de (0, 0)
            elif r == n:
                ligne[2 * n - 1] = o_bas  # sortie, sous (n-1, n-1)
            else:
                base = (r - 1) * n
                for gc in range(1, cote, 2):
                    i = base + gc // 2
                    if not (south[i >> 3] >> (i & 7)) & 1:
                        ligne[gc] = o_libre
        else:
            # Ligne de cellules.
            r = gr // 2
            base = r * n

            ligne[0] = o_mur
            ligne[cote - 1] = o_mur

            for gc in range(1, cote, 2):
                if state is None:
                    ligne[gc] = o_libre
                    continue
                valeur = state[base + gc // 2]
                if valeur == 2:
                    ligne[gc] = o_chemin
                elif valeur == 1:
                    ligne[gc] = o_explore
                else:
                    ligne[gc] = o_libre

            for gc in range(2, cote - 1, 2):
                i = base + gc // 2 - 1
                if (east[i >> 3] >> (i & 7)) & 1:
                    ligne[gc] = o_mur
                else:
                    ligne[gc] = o_libre

        yield ligne.decode("ascii")


def write_ascii(
    grid: WallGrid,
    destination: Path | str,
    state: bytearray | None = None,
    charset: Charset = DEFAULT_CHARSET,
    *,
    append: bool = False,
) -> Path:
    """Écrit le labyrinthe (et son parcours éventuel) dans un fichier, en flux."""
    chemin = Path(destination)
    chemin.parent.mkdir(parents=True, exist_ok=True)

    separateur = b""
    if append and chemin.exists() and chemin.stat().st_size > 0:
        separateur = b"\n"

    with open(chemin, "ab" if append else "wb") as fichier:
        if separateur:
            fichier.write(separateur)
        for ligne in iter_ascii_lines(grid, state, charset):
            fichier.write(ligne.encode(ENCODING))
            fichier.write(b"\n")

    return chemin


def render_to_string(
    grid: WallGrid,
    state: bytearray | None = None,
    charset: Charset = DEFAULT_CHARSET,
) -> str:
    """Rend le labyrinthe en une seule chaîne (petits labyrinthes uniquement)."""
    return NEWLINE.join(iter_ascii_lines(grid, state, charset))


def parse_ascii(text: str, charset: Charset = DEFAULT_CHARSET) -> WallGrid:
    """Reconstruit un :class:`WallGrid` depuis un rendu ASCII."""
    charset.validate()

    lignes = text.splitlines()
    while lignes and not lignes[-1]:
        lignes.pop()
    if not lignes:
        raise ValueError("le texte ne contient aucune ligne")

    cote = len(lignes[0])
    if cote % 2 == 0:
        raise ValueError(f"le cote doit etre impair, soit 2n + 1 : recu {cote}")
    if cote < 3:
        raise ValueError(f"le cote doit valoir au moins 3, soit n >= 1 : recu {cote}")
    if len(lignes) != cote:
        raise ValueError(
            f"le rendu doit etre carre : {len(lignes)} lignes pour {cote} colonnes"
        )
    for rang, ligne in enumerate(lignes):
        if len(ligne) != cote:
            raise ValueError(
                f"ligne {rang} : {len(ligne)} caracteres au lieu de {cote}"
            )

    autorises = {
        charset.wall,
        charset.free,
        charset.path,
        charset.explored,
        charset.entry,
        charset.exit,
    }
    inconnus = set(text) - autorises - {NEWLINE, "\r"}
    if inconnus:
        raise ValueError(
            f"caracteres inconnus dans le rendu : {sorted(inconnus)}"
        )

    n = (cote - 1) // 2
    grid = WallGrid(n)  # part fermée : on ne perce que les passages ouverts

    for r in range(n):
        ligne_cellules = lignes[2 * r + 1]
        for c in range(n - 1):
            if ligne_cellules[2 * c + 2] != charset.wall:
                grid.carve(r, c, EAST)
        if r + 1 < n:
            ligne_suivante = lignes[2 * r + 2]
            for c in range(n):
                if ligne_suivante[2 * c + 1] != charset.wall:
                    grid.carve(r, c, SOUTH)

    grid.entry_open = lignes[0][1] != charset.wall
    grid.exit_open = lignes[2 * n][2 * n - 1] != charset.wall

    return grid


def read_ascii(source: Path | str, charset: Charset = DEFAULT_CHARSET) -> WallGrid:
    """Lit un fichier ASCII et renvoie le labyrinthe correspondant."""
    chemin = Path(source)
    taille = chemin.stat().st_size
    if taille > MAX_READ_BYTES:
        raise ValueError(
            f"fichier trop volumineux : {taille} octets "
            f"(limite {MAX_READ_BYTES}). Ce n'est pas un rendu ASCII destine a "
            f"etre relu."
        )

    try:
        texte = chemin.read_bytes().decode(ENCODING)
    except UnicodeDecodeError as exc:
        raise ValueError(
            f"le fichier n'est pas de l'ASCII pur : {exc}. "
            f"Un rendu de labyrinthe ne contient que des caracteres ASCII."
        ) from None

    return parse_ascii(texte, charset)


def write_text_lines(lines: Iterator[str], destination: Path | str, *, append: bool = False) -> Path:
    """Écrit une suite de lignes dans un fichier, en flux."""
    chemin = Path(destination)
    chemin.parent.mkdir(parents=True, exist_ok=True)

    with open(chemin, "ab" if append else "wb") as fichier:
        for ligne in lines:
            fichier.write(ligne.encode(ENCODING))
            fichier.write(b"\n")

    return chemin


#: Taille maximale acceptée en lecture, en octets.
MAX_READ_BYTES = 512 * 1024 * 1024


def print_preview(
    grid: WallGrid,
    state: bytearray | None = None,
    *,
    max_side: int = 41,
    charset: Charset = DEFAULT_CHARSET,
    stream: TextIO | None = None,
) -> None:
    """Affiche un aperçu du labyrinthe, réduit si nécessaire."""
    import sys

    sortie = stream if stream is not None else sys.stdout
    lignes = list(iter_ascii_lines(grid, state, charset))

    facteur = math.ceil(len(lignes) / max_side) if len(lignes) > max_side else 1
    if facteur == 1:
        sortie.write(NEWLINE.join(lignes) + NEWLINE)
        return

    for index in range(0, len(lignes), facteur):
        sortie.write(lignes[index][::facteur] + NEWLINE)
    sortie.write(f"[apercu reduit : 1 caractere sur {facteur}]\n")
