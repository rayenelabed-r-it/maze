"""Fichier de statistiques : ce qui reste quand l'export est refusé.

Quand un labyrinthe est trop gros pour être exporté, ou quand l'utilisateur
refuse l'écriture, ce module produit un résumé texte du résultat. Format décrit
dans ``doc/05-export.md``.

Le fichier est en ASCII pur : une raison d'export contenant un accent ferait
échouer l'écriture.
"""

from __future__ import annotations

from collections.abc import Iterator
from pathlib import Path
from typing import TYPE_CHECKING

from mazes.rendering.ascii import write_text_lines

if TYPE_CHECKING:  # pragma: no cover
    from mazes.core.grid import WallGrid
    from mazes.rendering.policy import ExportPlan
    from mazes.solvers.base import SolveResult

#: Taille des bandes de comptage. À ``n = 100000``, dérouler les 1,25 Gio du
#: tampon d'un coup demanderait 10 Gio de mémoire temporaire.
BAND_BYTES = 1 << 20

#: Première ligne du format.
HEADER = "labyrinthe_statistiques"


def _popcount(tampon: bytearray, band_bytes: int) -> int:
    """Nombre de bits à 1 d'un tampon, bande par bande."""
    import numpy as np

    vue = memoryview(tampon)
    total = 0
    for debut in range(0, len(tampon), band_bytes):
        bande = np.frombuffer(vue[debut : debut + band_bytes], dtype=np.uint8)
        total += int(np.bitwise_count(bande).sum())
    return total


def count_passages(grid: WallGrid, *, band_bytes: int = BAND_BYTES) -> int:
    """Nombre de murs abattus, soit ``n² - 1`` pour un labyrinthe parfait.

    Le dernier octet de chaque tampon déborde de ``8·len - n²`` bits qui ne
    désignent aucune cellule. ``WallGrid.__init__`` les force à 1, donc les
    compter comme des murs fausserait le total de 7 à 15 unités. On les retranche
    du popcount.

    Le comptage parcourt les octets, pas les cellules : à ``n = 100000``, une
    boucle par cellule demanderait ``10¹⁰`` itérations.
    """
    if band_bytes < 1:
        raise ValueError(f"band_bytes doit etre >= 1, recu {band_bytes}")

    n = grid.n
    cellules = n * n
    remplissage = 8 * len(grid.east) - cellules

    murs = _popcount(grid.east, band_bytes) + _popcount(grid.south, band_bytes)
    return 2 * cellules - murs + 2 * remplissage


def _etat_ascii(plan: ExportPlan, ecrit: bool) -> str:
    """Sort de l'ASCII : ``oui``, ``refuse``, ou ``reduit xK``."""
    if not ecrit:
        return "refuse"
    if plan.ascii_full:
        return "oui"
    return f"reduit x{plan.ascii_scale}"


def _raison_ascii(plan: ExportPlan, ecrit: bool) -> str | None:
    """Pourquoi l'ASCII n'est pas là, ou ``None`` quand il l'est."""
    if ecrit and plan.ascii_full:
        return None
    if not ecrit and plan.ascii_full:
        return "refuse par l'utilisateur"
    return plan.reason


def _etat_image(plan: ExportPlan) -> str:
    """Description de l'image exportée."""
    if plan.image_scale == 1:
        return "pleine resolution"
    return (
        f"reduite x{plan.image_scale} -> "
        f"{plan.projected_image_side}x{plan.projected_image_side}"
    )


def _longueur_chemin(result: SolveResult | None) -> str:
    """Longueur du chemin, ou ``inconnu`` sans résultat de résolution."""
    if result is None:
        return "inconnu"
    try:
        return str(result.path_length)
    except AttributeError:
        raise TypeError(
            f"{type(result).__name__} n'a pas d'attribut 'path_length' : "
            f"attendu un SolveResult"
        ) from None


def stats_lines(
    grid: WallGrid,
    plan: ExportPlan,
    *,
    result: SolveResult | None = None,
    ascii_ecrit: bool | None = None,
) -> Iterator[str]:
    """Lignes du fichier de statistiques.

    ``ascii_ecrit`` vaut ``None`` pour « selon la politique ». Le CLI y passe
    ``False`` quand c'est l'utilisateur qui a refusé une écriture que la
    politique autorisait, sinon le fichier annoncerait un export qui n'a pas eu
    lieu. Attention au défaut : « écrit selon la politique » vaut ``non refuse``,
    pas ``ascii_full``, un ASCII réduit étant bien écrit.
    """
    n = grid.n
    ecrit = (not plan.ascii_refused) if ascii_ecrit is None else ascii_ecrit

    yield HEADER
    yield f"n: {n}"
    yield f"cellules: {n * n}"
    yield f"passages: {count_passages(grid)}"
    yield f"chemin_longueur: {_longueur_chemin(result)}"
    yield f"export_ascii: {_etat_ascii(plan, ecrit)}"

    raison = _raison_ascii(plan, ecrit)
    if raison is not None:
        yield f"export_ascii_raison: {raison}"

    yield f"export_image: {_etat_image(plan)}"


def write_stats(
    grid: WallGrid,
    destination: Path | str,
    plan: ExportPlan,
    *,
    result: SolveResult | None = None,
    ascii_ecrit: bool | None = None,
) -> Path:
    """Écrit le fichier de statistiques et renvoie son chemin."""
    return write_text_lines(
        stats_lines(grid, plan, result=result, ascii_ecrit=ascii_ecrit),
        destination,
    )


def refused_lines(n: int, *, phase: str, raison: str) -> Iterator[str]:
    """Lignes du fichier quand un calcul a été refusé.

    ``phase`` vaut ``"generation"`` ou ``"resolution"``. Aucune grille n'existe,
    donc ``passages`` et ``chemin_longueur`` valent ``inconnu`` et non zéro : un
    zéro se lirait comme « labyrinthe sans passage ».

    Les lignes d'export sont absentes : rien n'a été produit, donc rien n'a été
    refusé à l'export.
    """
    if n < 1:
        raise ValueError(f"n doit etre >= 1, recu {n}")

    yield HEADER
    yield f"n: {n}"
    yield f"cellules: {n * n}"
    yield "passages: inconnu"
    yield "chemin_longueur: inconnu"
    yield f"{phase}: refusee"
    yield f"{phase}_raison: {raison}"


def write_refused(
    n: int,
    destination: Path | str,
    *,
    phase: str,
    raison: str,
) -> Path:
    """Écrit le fichier de statistiques d'un calcul refusé."""
    return write_text_lines(
        refused_lines(n, phase=phase, raison=raison),
        destination,
    )
