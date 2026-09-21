"""Courbes du benchmark : temps et mémoire en fonction de n.

Chaque figure porte quatre panneaux : temps et mémoire, en échelle linéaire et
en log-log. Le log-log rend les lois de puissance lisibles, une droite par
algorithme.

Une figure par générateur (les trois solveurs), plus une figure comparant le
solveur le plus efficace de chaque générateur.

Seul module du benchmark à dépendre de matplotlib.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import TYPE_CHECKING

import matplotlib

matplotlib.use("Agg")  # rendu fichier, aucun écran requis

import matplotlib.pyplot as plt

if TYPE_CHECKING:  # pragma: no cover
    from benchmarks.collecte import Metriques

#: Couleurs et marqueurs, par algorithme. La palette d'Okabe-Ito reste lisible
#: en cas de daltonisme rouge-vert.
_PALETTE: dict[str, tuple[str, str]] = {
    "astar": ("#0072B2", "o"),
    "dijkstra": ("#D55E00", "s"),
    "recursive_backtracking": ("#009E73", "^"),
    "kruskal": ("#0072B2", "o"),
    "prim": ("#D55E00", "s"),
}

_REPLI = ("#7F7F7F", "D")

#: Les coûts estimés des tailles refusées, en gris et pointillés.
_STYLE_REFUS = ("#555555", "v")

#: (métrique, échelle log, axe des ordonnées, titre), dans l'ordre de la grille.
_PANNEAUX = (
    ("temps", False, "Temps (ms)", "temps, échelle linéaire"),
    ("temps", True, "Temps (ms)", "temps, échelle log-log"),
    ("memoire", False, "Pic mémoire (Kio)", "mémoire, échelle linéaire"),
    ("memoire", True, "Pic mémoire (Kio)", "mémoire, échelle log-log"),
)


@dataclass(frozen=True, slots=True)
class Courbe:
    """Une courbe à tracer : une étiquette et des points ``(n, valeur)``."""

    etiquette: str
    abscisses: tuple[int, ...]
    valeurs: tuple[float, ...]
    couleur: str
    marqueur: str
    pointilles: bool = False


def style(nom: str) -> tuple[str, str]:
    """Couleur et marqueur associés à un algorithme."""
    return _PALETTE.get(nom, _REPLI)


def _courbe(
    etiquette: str,
    points: dict[int, float],
    nom_style: str,
    *,
    pointilles: bool = False,
) -> Courbe:
    """Construit une courbe depuis ``{n: valeur}``, n croissants."""
    ordonnes = sorted(points.items())
    couleur, marqueur = _STYLE_REFUS if pointilles else style(nom_style)
    return Courbe(
        etiquette=etiquette,
        abscisses=tuple(n for n, _ in ordonnes),
        valeurs=tuple(v for _, v in ordonnes),
        couleur=couleur,
        marqueur=marqueur,
        pointilles=pointilles,
    )


def courbes_de_metriques(
    series: dict[str, dict[int, Metriques]],
    metrique: str,
    etiquettes: dict[str, str] | None = None,
) -> list[Courbe]:
    """Une courbe par série, pour ``"temps_s"`` ou ``"pic_kio"``.

    ``etiquettes`` découple le texte affiché de la clé qui donne la couleur,
    pour que la figure des « meilleurs » garde la couleur du générateur tout en
    légendant le nom du solveur.
    """
    courbes = []
    for nom, par_n in series.items():
        facteur = 1000.0 if metrique == "temps_s" else 1.0
        valeurs = {
            n: getattr(metriques, metrique) * facteur for n, metriques in par_n.items()
        }
        courbes.append(_courbe((etiquettes or {}).get(nom, nom), valeurs, nom))
    return courbes


def courbes_de_refus(refus: dict[str, dict[int, int]]) -> list[Courbe]:
    """Coûts estimés des tailles refusées, convertis en Kio.

    L'étiquette mentionne « estimé » pour qu'ils ne soient pas pris pour des
    mesures.
    """
    return [
        _courbe(f"{nom}, refusé (estimé)", points, nom, pointilles=True)
        for nom, points in refus.items()
        if points
    ]


def _tracer_panneau(
    ax, courbes: list[Courbe], *, log: bool, ylabel: str, titre: str
) -> None:
    """Trace un panneau. En échelle log, les valeurs non positives sont écartées."""
    for courbe in courbes:
        couples = list(zip(courbe.abscisses, courbe.valeurs, strict=True))
        if log:
            couples = [(x, y) for x, y in couples if x > 0 and y > 0]
        if not couples:
            continue
        ax.plot(
            [x for x, _ in couples],
            [y for _, y in couples],
            label=courbe.etiquette,
            color=courbe.couleur,
            marker=courbe.marqueur,
            linestyle="--" if courbe.pointilles else "-",
            markersize=7,
            linewidth=1.8,
            markerfacecolor="none" if courbe.pointilles else courbe.couleur,
            markeredgewidth=1.6,
        )

    if log:
        ax.set_xscale("log")
        ax.set_yscale("log")
    ax.set_title(titre, fontsize=11)
    ax.set_xlabel("n (couloirs par côté)", fontsize=9)
    ax.set_ylabel(ylabel, fontsize=9)
    ax.grid(True, which="both", alpha=0.25)
    ax.tick_params(labelsize=8)
    if courbes:
        ax.legend(fontsize=7, loc="best")


def figure(
    *,
    titre: str,
    series: dict[str, dict[int, Metriques]],
    refus: dict[str, dict[int, int]] | None = None,
    etiquettes: dict[str, str] | None = None,
    chemin: Path,
) -> Path:
    """Écrit une figure à quatre panneaux.

    ``refus`` contient les coûts estimés des tailles non générées, en octets.
    Ils ne sont tracés que sur le panneau mémoire log-log : leurs valeurs vont
    jusqu'au téraoctet et écraseraient les mesures sur une échelle linéaire.
    """
    chemin.parent.mkdir(parents=True, exist_ok=True)

    temps = courbes_de_metriques(series, "temps_s", etiquettes)
    memoire = courbes_de_metriques(series, "pic_kio", etiquettes)
    refuses = courbes_de_refus(
        {
            nom: {n: octets / 1024 for n, octets in points.items()}
            for nom, points in (refus or {}).items()
        }
    )

    fig, axes = plt.subplots(2, 2, figsize=(13.5, 9.5))
    fig.suptitle(titre, fontsize=13, fontweight="bold")

    for ax, (metrique, log, ylabel, sous_titre) in zip(axes.flat, _PANNEAUX, strict=True):
        courbes = temps if metrique == "temps" else memoire
        if metrique == "memoire" and log:
            courbes = courbes + refuses
        _tracer_panneau(ax, courbes, log=log, ylabel=ylabel, titre=sous_titre)
        if not courbes:
            ax.text(
                0.5,
                0.5,
                "aucune donnée exploitable",
                ha="center",
                va="center",
                fontsize=11,
                color="#888888",
                transform=ax.transAxes,
            )

    fig.tight_layout(rect=(0, 0, 1, 0.96))
    fig.savefig(chemin, dpi=110)
    plt.close(fig)
    return chemin


def figure_generateur(
    generateur: str,
    series: dict[str, dict[int, Metriques]],
    refus: dict[int, int],
    *,
    chemin: Path,
) -> Path:
    """Figure d'un générateur : les trois solveurs, plus les tailles refusées."""
    return figure(
        titre=f"Solveurs sur des labyrinthes {generateur}",
        series=series,
        refus={generateur: refus} if refus else {},
        chemin=chemin,
    )


def figure_meilleurs(
    series: dict[str, dict[int, Metriques]],
    refus: dict[str, dict[int, int]],
    meilleurs: dict[str, str],
    *,
    chemin: Path,
) -> Path:
    """Figure comparant le meilleur solveur de chaque générateur.

    ``meilleurs`` indique quel solveur porte chaque courbe, pour la légende.
    """
    return figure(
        titre="Meilleur solveur par générateur (le plus efficace)",
        series=series,
        refus=refus,
        etiquettes={nom: f"{nom}, {solveur}" for nom, solveur in meilleurs.items()},
        chemin=chemin,
    )
