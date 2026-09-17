"""Rendu d'un labyrinthe en image JPG.

Chaîne de traitement : ``WallGrid`` (bits) -> matrice dense ``uint8`` ->
sous-échantillonnage -> Pillow. Le développement est vectorisé (tranches numpy),
et au-delà d'un budget mémoire on procède par bandes. Voir ``doc/05-export.md``.
"""

from __future__ import annotations

import math
from dataclasses import dataclass
from pathlib import Path
from typing import TYPE_CHECKING

from mazes.core.grid import (
    DENSE_EXPLORED,
    DENSE_FREE,
    DENSE_MEMORY_BUDGET,
    DENSE_PATH,
    DENSE_WALL,
)

if TYPE_CHECKING:  # pragma: no cover
    import numpy as np
    from PIL import Image

    from mazes.core.grid import WallGrid

#: Hauteur (en lignes de cellules) des bandes du chemin par bandes.
BAND_HEIGHT = 512

#: Valeurs du tableau dense, reprises de ``core.grid`` (une seule source de vérité).
WALL = DENSE_WALL
FREE = DENSE_FREE
PATH_MARK = DENSE_PATH
EXPLORED_MARK = DENSE_EXPLORED

#: Une couleur : un triplet RGB ``(r, v, b)``, ou un entier (gris, étalé sur les 3 canaux).
Couleur = int | tuple[int, int, int]


@dataclass(frozen=True, slots=True)
class ImageStyle:
    """Correspondance valeurs denses -> couleurs RGB (un entier devient un gris)."""

    wall: Couleur = (0, 0, 0)
    free: Couleur = (255, 255, 255)
    path: Couleur = (220, 20, 60)
    explored: Couleur = (173, 216, 230)

    def build_palette(self) -> np.ndarray:
        """Table ``valeur -> couleur`` de 256 entrées RGB, appliquée via ``palette[dense]``."""
        import numpy as np

        palette = np.empty((256, 3), dtype=np.uint8)
        palette[:] = _en_rgb(self.free)
        palette[WALL] = _en_rgb(self.wall)
        palette[FREE] = _en_rgb(self.free)
        palette[PATH_MARK] = _en_rgb(self.path)
        palette[EXPLORED_MARK] = _en_rgb(self.explored)
        return palette


def _en_rgb(couleur: Couleur) -> tuple[int, int, int]:
    """Convertit une couleur en triplet RGB ; un entier est étalé sur les trois canaux."""
    if isinstance(couleur, int):
        rgb = (couleur, couleur, couleur)
    else:
        rgb = tuple(couleur)  # type: ignore[assignment]
        if len(rgb) != 3:
            raise ValueError(
                f"une couleur doit avoir 3 composantes (r, v, b), recu {couleur!r}"
            )
    for canal in rgb:
        if not (0 <= canal <= 255):
            raise ValueError(
                f"chaque composante doit etre entre 0 et 255, recu {couleur!r}"
            )
    return rgb  # type: ignore[return-value]


#: Style par défaut : couleur (murs noirs, passages blancs, chemin rouge,
#: cellules explorées bleu clair).
DEFAULT_STYLE = ImageStyle()


def render_dense(
    grid: WallGrid,
    state: bytearray | None = None,
) -> np.ndarray:
    """Développe le labyrinthe en matrice dense ``(2n+1, 2n+1)`` de ``uint8``."""
    return grid.to_dense(state)


def render_dense_banded(
    grid: WallGrid,
    state: bytearray | None = None,
    *,
    band_height: int = BAND_HEIGHT,
) -> np.ndarray:
    """Variante de :func:`render_dense` par bandes, mémoire ``O(grid_side * band_height)``."""
    import numpy as np

    n = grid.n
    cote = 2 * n + 1
    dense = np.empty((cote, cote), dtype=np.uint8)
    etats = None if state is None else np.frombuffer(state, dtype=np.uint8)

    r0 = 0
    while r0 < n:
        r1 = min(r0 + band_height, n)
        # Les lignes de cellules [r0, r1) produisent les lignes denses [2*r0, 2*r1].
        d0 = 2 * r0
        d1 = min(2 * r1 + 1, cote)
        _remplir_bande(grid, etats, dense[d0:d1], d0)
        r0 = r1

    return dense


def _bits_ligne(masque: bytearray, n: int, r: int) -> np.ndarray:
    """Les ``n`` bits de la ligne ``r`` d'un tampon de murs, en booléens.

    ``bitorder="little"`` est indispensable (voir :meth:`WallGrid.to_dense`).
    """
    import numpy as np

    debut = r * n
    premier_octet = debut >> 3
    dernier_octet = ((debut + n - 1) >> 3) + 1
    brut = np.frombuffer(masque, dtype=np.uint8)[premier_octet:dernier_octet]
    decalage = debut & 7
    return np.unpackbits(brut, bitorder="little")[decalage : decalage + n].astype(bool)


def _remplir_bande(
    grid: WallGrid, etats: np.ndarray | None, bande: np.ndarray, d0: int
) -> None:
    """Remplit une bande de lignes denses à partir de la ligne globale ``d0``."""
    import numpy as np

    n = grid.n
    table_etat = np.array([DENSE_FREE, DENSE_EXPLORED, DENSE_PATH], dtype=np.uint8)

    # Tout mur par défaut : coins et bordures latérales le restent.
    bande[:] = DENSE_WALL

    for i in range(bande.shape[0]):
        ligne_dense = d0 + i
        ligne = bande[i]

        if ligne_dense % 2 == 1:
            # Ligne de cellules : les cellules aux colonnes impaires.
            r = ligne_dense // 2
            if etats is None:
                ligne[1::2] = DENSE_FREE
            else:
                ligne[1::2] = table_etat[etats[r * n : (r + 1) * n]]
            # Murs verticaux : colonne 2c porte le mur Est de (r, c-1).
            bits = _bits_ligne(grid.east, n, r)
            ligne[2:-1:2] = np.where(bits[:-1], DENSE_WALL, DENSE_FREE)
        else:
            # Ligne de murs horizontaux.
            r = ligne_dense // 2
            if r == 0:
                if grid.entry_open:
                    ligne[1] = DENSE_FREE
            elif r == n:
                if grid.exit_open:
                    ligne[-2] = DENSE_FREE
            else:
                # La ligne dense 2r porte le mur Sud de la ligne r-1.
                bits = _bits_ligne(grid.south, n, r - 1)
                ligne[1::2] = np.where(bits, DENSE_WALL, DENSE_FREE)


def subsample_dense(
    dense: np.ndarray,
    factor: int,
    *,
    preserve_path: bool = True,
) -> np.ndarray:
    """Réduit une matrice dense d'un facteur ``factor`` par minimum de bloc.

    Le minimum conserve « au moins un passage dans cette zone » ; ``preserve_path``
    garde le chemin prioritairement.
    """
    if factor <= 1:
        return dense

    hauteur = (dense.shape[0] // factor) * factor
    largeur = (dense.shape[1] // factor) * factor
    if hauteur == 0 or largeur == 0:
        raise ValueError(
            f"facteur de reduction {factor} trop grand pour une matrice de "
            f"{dense.shape[0]} x {dense.shape[1]} : le resultat serait vide"
        )

    rognee = dense[:hauteur, :largeur]
    blocs = rognee.reshape(hauteur // factor, factor, largeur // factor, factor)
    reduit = blocs.min(axis=(1, 3))

    if preserve_path:
        chemin = (rognee == PATH_MARK).reshape(
            hauteur // factor, factor, largeur // factor, factor
        ).any(axis=(1, 3))
        reduit[chemin] = PATH_MARK

    return reduit


def to_image(dense: np.ndarray, style: ImageStyle = DEFAULT_STYLE) -> Image.Image:
    """Convertit une matrice dense en image Pillow (mode ``"RGB"``)."""
    from PIL import Image

    return Image.fromarray(style.build_palette()[dense])


def write_image(
    grid: WallGrid,
    destination: Path | str,
    state: bytearray | None = None,
    *,
    style: ImageStyle = DEFAULT_STYLE,
    scale: int = 1,
    quality: int = 95,
    fmt: str | None = None,
    max_side: int = 32_768,
) -> Path:
    """Écrit le labyrinthe dans un fichier image JPEG.

    ``scale`` est un facteur de **réduction** (jamais d'agrandissement). Réduire
    *puis* convertir, jamais l'inverse. ``subsampling=0`` (4:4:4) évite le
    bavage du JPEG le long des murs.
    """
    import numpy as np
    from PIL import Image

    chemin = Path(destination)
    chemin.parent.mkdir(parents=True, exist_ok=True)

    nom_format = (fmt or choose_format(chemin)).upper()
    if nom_format != "JPEG":
        raise ValueError(f"format inconnu : {nom_format!r}. Attendu JPEG")
    if scale < 1:
        raise ValueError(f"scale doit etre >= 1, recu {scale}")

    n = grid.n
    cote = 2 * n + 1

    facteur = scale
    if math.ceil(cote / facteur) > max_side:
        facteur = math.ceil(cote / max_side)

    if cote // facteur < 4:
        raise ValueError(
            f"reduction x{facteur} trop forte : la grille de cote {cote} "
            f"donnerait une image de {cote // facteur} pixel(s) de cote. "
            f"Rappel : `scale` est un facteur de REDUCTION, pas d'agrandissement."
        )

    # Pillow refuse par défaut les très grandes images (anti-bombe de décompression) :
    # ici la taille est légitime, demandée par l'utilisateur.
    Image.MAX_IMAGE_PIXELS = None

    if cote * cote <= DENSE_MEMORY_BUDGET:
        dense = render_dense(grid, state)
        reduit = subsample_dense(dense, facteur)
        del dense  # libère avant l'encodage
    else:
        reduit = _render_reduced_banded(grid, state, facteur)

    image = to_image(np.ascontiguousarray(reduit), style)

    options: dict[str, object] = {"format": nom_format}
    if nom_format == "JPEG":
        options["quality"] = quality
        # 4:4:4 : chaque pixel garde sa couleur, sinon le rouge bave le long des murs.
        options["subsampling"] = 0
    image.save(chemin, **options)

    return chemin


def _render_reduced_banded(
    grid: WallGrid, state: bytearray | None, factor: int, band_height: int = BAND_HEIGHT
) -> np.ndarray:
    """Construit directement l'image réduite, sans matérialiser la matrice dense.

    Le pas entre bandes est un multiple de ``factor`` pour que les blocs de
    réduction ne chevauchent jamais deux bandes.
    """
    import numpy as np

    n = grid.n
    cote = 2 * n + 1
    cote_reduit = cote // factor
    if cote_reduit == 0:
        raise ValueError(
            f"facteur de reduction {factor} trop grand pour une grille de cote "
            f"{cote} : l'image serait vide"
        )

    etats = None if state is None else np.frombuffer(state, dtype=np.uint8)
    sortie = np.empty((cote_reduit, cote_reduit), dtype=np.uint8)

    lignes_utiles = cote_reduit * factor
    pas = factor * max(1, band_height // factor)

    debut = 0
    while debut < lignes_utiles:
        fin = min(debut + pas, lignes_utiles)
        bande = np.empty((fin - debut, cote), dtype=np.uint8)
        _remplir_bande(grid, etats, bande, debut)
        reduit = subsample_dense(bande, factor)
        depart = debut // factor
        sortie[depart : depart + reduit.shape[0]] = reduit
        debut = fin

    return sortie


def choose_format(destination: Path | str) -> str:
    """Déduit le format (``"JPEG"``) de l'extension du fichier."""
    extension = Path(destination).suffix.lower()
    if extension in (".jpg", ".jpeg"):
        return "JPEG"
    raise ValueError(
        f"extension inconnue : {extension!r}. Formats acceptes : .jpg, .jpeg"
    )
