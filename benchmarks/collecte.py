"""Lecture de ``outputs/`` et mesure des solveurs.

Le dossier ``outputs/`` contient deux sortes de fichiers ``.txt`` : les
labyrinthes, et les fichiers de statistiques que le CLI écrit quand un export
est refusé. Les premiers sont résolus par chaque solveur, les seconds sont
seulement listés.

La mesure suit le protocole de ``doc/README.md`` : échauffement, même labyrinthe
pour tous les solveurs, et médiane quand plusieurs labyrinthes de même taille
sont disponibles.
"""

from __future__ import annotations

import statistics
import sys
from dataclasses import dataclass
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))

from mazes.budget import estimate_generation, estimate_solving
from mazes.core.grid import WallGrid, entry_cell, exit_cell
from mazes.core.validation import validate_path
from mazes.generators import generator_choices
from mazes.metrics import measure
from mazes.rendering import read_ascii
from mazes.solvers import get_solver, solver_choices

ENTETE_STATS = "labyrinthe_statistiques"
SUFFIXE_STATS = "_statistiques"


@dataclass(frozen=True, slots=True)
class Maze:
    """Un labyrinthe de ``outputs/``, et ce que son nom indique."""

    chemin: Path
    grille: WallGrid
    generateur: str | None
    n: int


@dataclass(frozen=True, slots=True)
class Refus:
    """Un fichier de statistiques.

    ``phase`` vaut ``"generation"`` ou ``"resolution"`` pour un calcul refusé
    faute de mémoire, et ``None`` quand la génération a réussi mais que l'export
    a été refusé. Dans ce second cas, ``passages`` et ``chemin_longueur``
    contiennent les mesures réelles du labyrinthe.
    """

    chemin: Path
    n: int
    generateur: str | None
    solveur: str | None
    phase: str | None
    raison: str | None
    cout_bytes: int | None
    passages: int | None
    chemin_longueur: int | None


@dataclass(frozen=True, slots=True)
class Inventaire:
    """Résultat du tri de ``outputs/``."""

    mazes: tuple[Maze, ...]
    refus: tuple[Refus, ...]
    ignores: tuple[tuple[Path, str], ...]


@dataclass(frozen=True, slots=True)
class Metriques:
    """Mesures d'un solveur sur un labyrinthe.

    ``pic_kio`` est le pic d'allocation relevé par ``tracemalloc``, et non
    ``max_frontier`` : la frontière ignore les tables ``g``, ``parents`` et
    ``closed`` d'A*, et son classement est trompeur (voir ``doc/README.md``).
    """

    solveur: str
    temps_s: float
    pic_kio: float
    developpees: int
    frontiere: int
    chemin: int
    efficacite: float
    valide: bool


def _entier_final(nom: str) -> int | None:
    """Le nombre en fin de nom, ou ``None``."""
    reste, _, dernier = nom.rpartition("_")
    if not reste or not dernier.isdigit():
        return None
    return int(dernier)


def classer(nom: str) -> tuple[str | None, str | None, int | None]:
    """Décompose un nom de fichier en ``(générateur, solveur, n)``.

    Les noms suivent les conventions du CLI : ``<générateur>_<solveur>_<n>``,
    ``maze_<générateur>_<n>`` pour ``generate`` et ``solved_<solveur>_<n>`` pour
    ``solve``. Comme ``recursive_backtracking`` contient un tiret bas, on compare
    aux noms connus du registre au lieu de découper sur ``_``.

    Un nom non reconnu donne ``None`` : un labyrinthe attribué au mauvais
    générateur fausserait une figure entière.
    """
    n = _entier_final(nom)
    if n is None:
        return None, None, None

    reste = nom[: -(len(str(n)) + 1)]
    generateurs = sorted(generator_choices(), key=len, reverse=True)
    solveurs = sorted(solver_choices(), key=len, reverse=True)

    for prefixe, est_generateur in (("maze_", True), ("solved_", False)):
        if reste.startswith(prefixe):
            algorithme = reste[len(prefixe) :]
            connus = generateurs if est_generateur else solveurs
            if algorithme not in connus:
                return None, None, n
            return (algorithme, None, n) if est_generateur else (None, algorithme, n)

    for generateur in generateurs:
        for solveur in solveurs:
            if reste == f"{generateur}_{solveur}":
                return generateur, solveur, n

    for generateur in generateurs:
        if reste == generateur:
            return generateur, None, n
    for solveur in solveurs:
        if reste == solveur:
            return None, solveur, n

    return None, None, n


def _lire_champs_stats(chemin: Path) -> dict[str, str]:
    """Champs ``clé: valeur`` d'un fichier de statistiques."""
    champs: dict[str, str] = {}
    for ligne in chemin.read_text(encoding="ascii").splitlines():
        if ": " in ligne:
            cle, valeur = ligne.split(": ", 1)
            champs[cle] = valeur
    return champs


def _entier(champs: dict[str, str], cle: str) -> int | None:
    """Champ entier, ou ``None`` quand il vaut ``inconnu``."""
    valeur = champs.get(cle)
    return int(valeur) if valeur and valeur.isdigit() else None


def _cout_du_refus(phase: str, algorithme: str | None, n: int) -> int | None:
    """Coût estimé d'un refus, recalculé avec le modèle de ``mazes.budget``.

    Le fichier ne contient que la valeur formatée (« 2.1 Tio »). Plutôt que de
    l'analyser, on rappelle le modèle qui l'a produite : le résultat est le même
    et il n'y a pas d'expression régulière à maintenir.
    """
    if algorithme is None:
        return None
    estimateur = estimate_generation if phase == "generation" else estimate_solving
    try:
        return estimateur(algorithme, n)
    except ValueError:
        return None


def _construire_refus(chemin: Path, champs: dict[str, str]) -> Refus:
    """Construit un :class:`Refus` à partir des champs lus."""
    n = int(champs["n"])
    generateur, solveur, _ = classer(chemin.stem.removesuffix(SUFFIXE_STATS))

    phase = raison = None
    for candidate in ("generation", "resolution"):
        if champs.get(candidate) == "refusee":
            phase = candidate
            raison = champs.get(f"{candidate}_raison")
            break

    algorithme = generateur if phase == "generation" else solveur
    return Refus(
        chemin=chemin,
        n=n,
        generateur=generateur,
        solveur=solveur,
        phase=phase,
        raison=raison,
        cout_bytes=_cout_du_refus(phase, algorithme, n) if phase else None,
        passages=_entier(champs, "passages"),
        chemin_longueur=_entier(champs, "chemin_longueur"),
    )


def lire_outputs(dossier: Path) -> Inventaire:
    """Trie ``outputs/`` en labyrinthes, refus, et fichiers illisibles.

    Un ``.txt`` qui commence par l'en-tête des statistiques devient un
    :class:`Refus` au lieu d'être confié à ``read_ascii``, qui le rejetterait.
    """
    mazes: list[Maze] = []
    refus: list[Refus] = []
    ignores: list[tuple[Path, str]] = []

    for chemin in sorted(dossier.glob("*.txt")):
        try:
            texte = chemin.read_text(encoding="ascii")
        except (UnicodeDecodeError, OSError) as err:
            ignores.append((chemin, str(err)))
            continue

        if texte.startswith(ENTETE_STATS):
            refus.append(_construire_refus(chemin, _lire_champs_stats(chemin)))
            continue

        try:
            grille = read_ascii(chemin)
        except (ValueError, UnicodeDecodeError) as err:
            ignores.append((chemin, str(err)))
            continue

        generateur, _, n = classer(chemin.stem)
        mazes.append(Maze(chemin=chemin, grille=grille, generateur=generateur, n=n))

    return Inventaire(mazes=tuple(mazes), refus=tuple(refus), ignores=tuple(ignores))


def grouper(mazes: tuple[Maze, ...]) -> dict[tuple[str | None, int], list[Maze]]:
    """Regroupe les labyrinthes par ``(générateur, n)``.

    Chaque liste rassemble des labyrinthes de même taille et de même générateur,
    tirés indépendamment : c'est ce qui permet de prendre une médiane plutôt que
    de dépendre d'un tirage particulier.
    """
    groupes: dict[tuple[str | None, int], list[Maze]] = {}
    for maze in mazes:
        groupes.setdefault((maze.generateur, maze.n), []).append(maze)
    return dict(sorted(groupes.items(), key=lambda item: (str(item[0][0]), item[0][1])))


def mediane(valeurs: list[float]) -> float:
    """Médiane d'une liste non vide."""
    if not valeurs:
        raise ValueError("la mediane d'une liste vide n'existe pas")
    return float(statistics.median(valeurs))


def mesurer_labyrinthe(
    grille: WallGrid,
    solveurs: list[str] | None = None,
    *,
    echauffement: bool = True,
) -> dict[str, Metriques]:
    """Résout ``grille`` avec chaque solveur et relève temps et mémoire.

    Chaque solveur est exécuté deux fois : une sans ``tracemalloc`` pour le
    temps, une avec pour le pic mémoire. Les tracer ensemble fausserait la durée,
    ``tracemalloc`` ralentissant le code mesuré.
    """
    noms = solver_choices() if solveurs is None else solveurs
    start, goal = entry_cell(grille), exit_cell(grille)
    mesures: dict[str, Metriques] = {}

    for nom in noms:
        solveur = get_solver(nom)

        if echauffement:
            solveur.solve(grille, start, goal)

        temps = measure(lambda s=solveur: s.solve(grille, start, goal), trace_memory=False)
        memoire = measure(lambda s=solveur: s.solve(grille, start, goal), trace_memory=True)
        resultat = memoire.result

        problemes = validate_path(grille, resultat.path, start, goal)
        mesures[nom] = Metriques(
            solveur=nom,
            temps_s=temps.elapsed_s,
            pic_kio=memoire.peak_kib,
            developpees=resultat.expanded,
            frontiere=resultat.max_frontier,
            chemin=resultat.path_length,
            efficacite=resultat.efficiency,
            valide=not problemes,
        )

    return mesures


def agreger(par_labyrinthe: list[dict[str, Metriques]]) -> dict[str, Metriques]:
    """Médiane des mesures sur plusieurs labyrinthes, par solveur.

    ``valide`` est vrai seulement si tous les labyrinthes le sont : un chemin qui
    traverse un mur est un bug, pas une valeur aberrante à écarter.
    """
    if not par_labyrinthe:
        raise ValueError("aucun labyrinthe a agreger")

    noms = sorted(par_labyrinthe[0])
    agreges: dict[str, Metriques] = {}
    for nom in noms:
        series = [mesures[nom] for mesures in par_labyrinthe]
        agreges[nom] = Metriques(
            solveur=nom,
            temps_s=mediane([m.temps_s for m in series]),
            pic_kio=mediane([m.pic_kio for m in series]),
            developpees=int(mediane([m.developpees for m in series])),
            frontiere=int(mediane([m.frontiere for m in series])),
            chemin=int(mediane([m.chemin for m in series])),
            efficacite=mediane([m.efficacite for m in series]),
            valide=all(m.valide for m in series),
        )
    return agreges
