"""Politique d'export : que peut-on raisonnablement écrire sur le disque ?

L'export 1:1 devient impossible au-delà d'un seuil (disque et limite JPEG). Une
:class:`ExportPolicy` décide, avant le calcul, ce qui sera écrit : ASCII complet,
image réduite, ou fichier de statistiques seul. Voir ``doc/05-export.md``.
"""

from __future__ import annotations

import math
from dataclasses import dataclass

#: Cote maximal, en caractères, d'un export ASCII 1:1.
MAX_ASCII_SIDE = 8_000

#: Cote maximal, en pixels, d'une image exportée (sous la limite JPEG de 65 535).
MAX_IMAGE_SIDE = 32_768

#: Au-delà de ce côté, un fichier de statistiques est toujours écrit.
STATS_ALWAYS_ABOVE = 2_000

#: Octets par pixel d'un JPEG qualité 95 en 4:4:4, **état du solveur compris**.
#:
#: Mesuré sur des labyrinthes parfaits résolus -- chemin rouge et cellules
#: explorées bleu clair, donc ce que le CLI écrit réellement. De 1.34 à 1.25
#: o/px de ``n = 200`` à ``n = 3000``, en décroissant lentement.
#:
#: La mesure **sans** état donnerait 1.13 : l'écart de 15 % vient des zones
#: explorées, qu'un calibrage sur grille nue oublierait complètement.
#:
#: La valeur retenue majore la mesure. Surestimer fait prévenir un peu tôt ;
#: sous-estimer laisserait remplir le disque en silence.
IMAGE_BYTES_PER_PIXEL = 1.35

#: Idem pour une image sous-échantillonnée.
#:
#: Le régime réduit n'est **pas** simplement « plus léger » : ``subsample_dense``
#: réduit par minimum de bloc et préserve le chemin (``preserve_path``), si bien
#: que le chemin et les zones explorées occupent une part croissante d'une image
#: de plus en plus petite. L'image ne blanchit donc pas.
#:
#: Mesuré sur ``n`` de 200 à 3000 et des facteurs de 2 à 32 : 0.05 à 0.39 o/px.
#: Le maximum tombe au plus petit facteur (x2), celui qui produit la plus grande
#: image -- donc le cas qui compte pour le seuil d'alerte. Là encore, la valeur
#: retenue majore, ce qui prévient trop tôt aux forts facteurs mais ne laisse
#: jamais passer un fichier énorme.
IMAGE_BYTES_PER_PIXEL_REDUCED = 0.45


@dataclass(frozen=True, slots=True)
class ExportPlan:
    """Ce qui sera effectivement écrit pour un labyrinthe de taille ``n``."""

    n: int
    grid_side: int
    ascii_full: bool
    #: ``True`` quand l'ASCII 1:1 ne tient pas et que la réduction n'est pas
    #: autorisée : aucun fichier ASCII ne sera écrit, ni complet ni réduit.
    #: Sans ce drapeau, ``ascii_scale`` laisserait croire à une réduction.
    ascii_refused: bool
    ascii_scale: int
    image_scale: int
    write_stats: bool
    ascii_bytes: int
    image_bytes: int
    reason: str
    warnings: tuple[str, ...] = ()

    @property
    def written_bytes(self) -> int:
        """Octets que la politique laisse écrire : l'ASCII 1:1 et l'image.

        L'ASCII refusé compte pour zéro : c'est ce que la politique décide de ne
        pas écrire, et c'est cette valeur qui doit servir à prévenir l'utilisateur.
        """
        return (self.ascii_bytes if self.ascii_full else 0) + self.image_bytes

    @property
    def projected_ascii_side(self) -> int:
        """Cote de la grille ASCII après sous-échantillonnage."""
        return self.grid_side // self.ascii_scale

    @property
    def projected_image_side(self) -> int:
        """Cote de l'image après sous-échantillonnage."""
        return self.grid_side // self.image_scale

    @property
    def is_degraded(self) -> bool:
        """``True`` si l'export n'est pas fidèle à l'échelle 1:1."""
        return self.ascii_scale > 1 or self.image_scale > 1

    def _resume_ascii(self) -> str:
        """Décrit le sort de l'ASCII : écrit, réduit, ou refusé.

        Les deux cas où ``ascii_full`` est faux ne se ressemblent pas : avec
        ``ascii_subsample`` un fichier réduit est écrit, sans lui **rien** ne
        l'est. Les confondre ferait annoncer une réduction qui n'aura pas lieu.
        """
        if self.ascii_full:
            return "oui"
        if self.ascii_refused:
            return f"non -- refuse (la grille ferait {self.grid_side} caracteres)"
        return (
            f"non -- reduit x{self.ascii_scale} "
            f"({self.projected_ascii_side} caracteres)"
        )

    def describe(self) -> str:
        """Résumé multi-lignes de la décision, pour l'affichage console."""
        lignes = [
            "  Export ASCII 1:1  : " + self._resume_ascii(),
            "  Export image      : "
            + (
                "pleine resolution"
                if self.image_scale == 1
                else f"reduite x{self.image_scale} -> {self.projected_image_side} pixels"
            ),
            f"  Statistiques      : {'oui' if self.write_stats else 'non'}",
        ]
        lignes.append(f"  {self.reason}")
        if self.warnings:
            lignes.extend(f"  ! {avertissement}" for avertissement in self.warnings)
        return "\n".join(lignes)


class ExportPolicy:
    """Décide de la forme des sorties en fonction de la taille du labyrinthe."""

    __slots__ = ("ascii_subsample", "max_ascii_side", "max_image_side")

    def __init__(
        self,
        max_ascii_side: int = MAX_ASCII_SIDE,
        max_image_side: int = MAX_IMAGE_SIDE,
        ascii_subsample: bool = False,
    ) -> None:
        if max_ascii_side < 3:
            raise ValueError("max_ascii_side doit etre >= 3")
        if max_image_side < 3:
            raise ValueError("max_image_side doit etre >= 3")
        self.max_ascii_side = max_ascii_side
        self.max_image_side = max_image_side
        self.ascii_subsample = ascii_subsample

    def plan(self, n: int) -> ExportPlan:
        """Calcule ce qui peut être écrit pour ``n`` couloirs par côté."""
        if n < 1:
            raise ValueError(f"n doit etre >= 1, recu {n}")

        cote = 2 * n + 1
        avertissements: list[str] = []

        if cote <= self.max_ascii_side:
            ascii_complet = True
            echelle_ascii = 1
        elif self.ascii_subsample:
            ascii_complet = False
            echelle_ascii = subsample_factor(cote, self.max_ascii_side)
            avertissements.append(
                "l'ASCII est reduit : le fichier ne represente plus fidelement "
                "le labyrinthe, chaque caractere couvrant plusieurs cellules"
            )
        else:
            ascii_complet = False
            echelle_ascii = subsample_factor(cote, self.max_ascii_side)

        echelle_image = subsample_factor(cote, self.max_image_side)
        octets_ascii = self.estimate_ascii_bytes(n, 1)
        octets_image = self.estimate_image_bytes(n)

        if ascii_complet:
            raison = (
                f"grille de {cote} x {cote} : l'ASCII 1:1 tient sous la limite "
                f"de {self.max_ascii_side} caracteres"
            )
        else:
            raison = (
                f"ASCII 1:1 impossible : la grille ferait {cote} x {cote} "
                f"caracteres, soit {octets_ascii / 1024**3:.1f} Gio "
                f"(limite {self.max_ascii_side} de cote)"
            )
            if not self.ascii_subsample:
                raison += " -- ASCII refuse plutot que reduit"

        if echelle_image > 1:
            avertissements.append(
                f"l'image est reduite x{echelle_image} : cote "
                f"{cote // echelle_image} au lieu de {cote}"
            )

        return ExportPlan(
            n=n,
            grid_side=cote,
            ascii_full=ascii_complet,
            ascii_refused=not ascii_complet and not self.ascii_subsample,
            ascii_scale=1 if ascii_complet else echelle_ascii,
            image_scale=echelle_image,
            write_stats=cote > STATS_ALWAYS_ABOVE,
            ascii_bytes=octets_ascii,
            image_bytes=octets_image,
            reason=raison,
            warnings=tuple(avertissements),
        )

    def ascii_is_feasible(self, n: int) -> bool:
        """Indique si l'ASCII 1:1 tient sous la limite."""
        return 2 * n + 1 <= self.max_ascii_side

    def estimate_ascii_bytes(self, n: int, scale: int = 1) -> int:
        """Taille estimée du fichier ASCII, en octets (retours à la ligne compris)."""
        cote = (2 * n + 1) // max(1, scale)
        return cote * (cote + 1)

    def estimate_dense_bytes(self, n: int) -> int:
        """Mémoire du tableau dense ``(2n+1)**2``, soit 16x la représentation compacte."""
        cote = 2 * n + 1
        return cote * cote

    def estimate_image_bytes(self, n: int) -> int:
        """Taille estimée du JPEG, en octets.

        Deux régimes, et l'écart entre les deux est de deux ordres de grandeur --
        il ne faut donc pas se tromper de branche :

        * ``image_scale == 1`` : l'image garde les murs, elle est très contrastée,
          ``IMAGE_BYTES_PER_PIXEL`` ;
        * ``image_scale > 1`` : le minimum de bloc blanchit presque tout,
          ``IMAGE_BYTES_PER_PIXEL_REDUCED``.

        L'estimation majore volontairement dans le second cas : cette valeur sert
        à prévenir l'utilisateur avant d'écrire, pas à prédire au kilo-octet.
        """
        cote = 2 * n + 1
        facteur = subsample_factor(cote, self.max_image_side)
        # Même découpage que ``write_image`` : la sortie fait ``cote // facteur``.
        cote_reduit = cote // facteur
        par_pixel = (
            IMAGE_BYTES_PER_PIXEL if facteur == 1 else IMAGE_BYTES_PER_PIXEL_REDUCED
        )
        return int(cote_reduit * cote_reduit * par_pixel)

    def __repr__(self) -> str:
        return (
            f"ExportPolicy(max_ascii_side={self.max_ascii_side}, "
            f"max_image_side={self.max_image_side}, ascii_subsample={self.ascii_subsample})"
        )


def subsample_factor(side: int, limit: int) -> int:
    """Plus petit entier ``k`` tel que ``side // k <= limit`` (``1`` si déjà sous la limite)."""
    if limit < 1:
        raise ValueError("limit doit etre >= 1")
    if side <= limit:
        return 1
    return math.ceil(side / limit)


#: Unités binaires, de la plus grande à la plus petite. Le seuil de bascule est
#: la puissance de 1024 elle-même : ``1536`` octets s'écrit ``1.5 Kio``.
_UNITES = (
    (1024**4, "Tio"),
    (1024**3, "Gio"),
    (1024**2, "Mio"),
    (1024, "Kio"),
)


def format_bytes(octets: int) -> str:
    """Formate un nombre d'octets en unité binaire lisible (``1.5 Gio``).

    Aligné sur les unités déjà employées par le reste du projet (``Mio`` dans
    ``grid.py`` et ``image.py``, ``Gio`` dans ``ExportPlan.reason``) : deux
    nombres différents pour la même grandeur seraient pires que le détail près.

    Sous 1024 octets, la valeur reste en octets bruts (``512 o``) : la virgule
    y apporterait plus de bruit que d'information.
    """
    if octets < 0:
        raise ValueError(f"octets doit etre >= 0, recu {octets}")
    for limite, unite in _UNITES:
        if octets >= limite:
            return f"{octets / limite:.1f} {unite}"
    return f"{octets} o"
