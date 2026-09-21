"""Benchmark des solveurs : mesures, rapport et courbes.

::

    python benchmarks/scaling.py
    python benchmarks/scaling.py --sizes 100 1000
    python benchmarks/scaling.py --sans-courbes

Le dossier ``outputs/`` contient deux sortes de fichiers ``.txt`` : les
labyrinthes, et les fichiers de statistiques écrits quand un export est refusé.
Les premiers sont résolus par chaque solveur et mesurés ; les seconds sont
listés dans le rapport avec leur coût estimé.

Le temps et la mémoire sont relevés dans deux passes séparées. ``tracemalloc``
ralentit le code mesuré : chronométrer la passe tracée gonflerait la durée.

« Léger » désigne le pic mémoire réel, et non ``max_frontier``, dont le
classement est trompeur (voir ``doc/README.md``).
"""

from __future__ import annotations

import argparse
import contextlib
import re
import sys
import unicodedata
from dataclasses import dataclass
from pathlib import Path

# La racine du dépôt doit être dans sys.path avant les imports : « benchmarks »
# est un paquet sans __init__.py, et lancé en script, sys.path[0] vaut
# benchmarks/, pas la racine.
RACINE = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(RACINE / "src"))
sys.path.insert(0, str(RACINE))

from benchmarks.collecte import (  # noqa: E402
    Inventaire,
    Metriques,
    agreger,
    grouper,
    lire_outputs,
    mesurer_labyrinthe,
)
from tqdm import tqdm  # noqa: E402

from mazes.rendering import format_bytes  # noqa: E402
from mazes.solvers import solver_choices  # noqa: E402

OUTPUTS = RACINE / "outputs"


def _slug(nom: str) -> str:
    """Nom de fichier sans accent ni espace."""
    decompose = unicodedata.normalize("NFKD", nom)
    sans_accent = "".join(c for c in decompose if not unicodedata.combining(c))
    return re.sub(r"[^A-Za-z0-9]+", "_", sans_accent).strip("_").lower()


@dataclass(frozen=True, slots=True)
class Analyse:
    """Un couple ``(générateur, n)`` et ses solveurs agrégés."""

    generateur: str | None
    n: int
    labyrinthes: int
    par_solveur: dict[str, Metriques]


def analyser(inventaire: Inventaire, *, tailles: set[int] | None = None) -> list[Analyse]:
    """Résout chaque labyrinthe et agrège les mesures par ``(générateur, n)``."""
    groupes = [
        (cle, mazes)
        for cle, mazes in grouper(inventaire.mazes).items()
        if tailles is None or cle[1] in tailles
    ]

    analyses: list[Analyse] = []
    for (generateur, n), mazes in tqdm(
        groupes, desc="mesure", unit="groupe", disable=None, file=sys.stderr
    ):
        par_labyrinthe = [mesurer_labyrinthe(maze.grille) for maze in mazes]
        analyses.append(
            Analyse(
                generateur=generateur,
                n=n,
                labyrinthes=len(mazes),
                par_solveur=agreger(par_labyrinthe),
            )
        )
    return analyses


def _nom_generateur(generateur: str | None) -> str:
    return generateur if generateur is not None else "générateur inconnu"


def _verdict(analyse: Analyse) -> tuple[Metriques, Metriques, Metriques]:
    """Les gagnants des trois critères : rapide, efficace, léger."""
    mesures = list(analyse.par_solveur.values())
    return (
        min(mesures, key=lambda m: m.temps_s),
        min(mesures, key=lambda m: m.developpees),
        min(mesures, key=lambda m: m.pic_kio),
    )


def _nombre(valeur: float) -> str:
    """Formate un nombre à la française : espace pour les milliers, virgule décimale.

    Le rapport est lu par des humains : « 402 472 » s'y lit mieux que « 402,472 ».
    """
    texte = f"{valeur:,.0f}" if float(valeur).is_integer() else f"{valeur:,.2f}"
    return texte.replace(",", " ").replace(".", ",")


def _tableau(analyse: Analyse) -> list[str]:
    lignes = [
        "| Programme | Temps (ms) | Cases examinées | Mémoire max (Kio) "
        "| Liste d'attente | Chemin (cases) | Efficacité |",
        "|---|---:|---:|---:|---:|---:|---:|",
    ]
    for nom, m in sorted(analyse.par_solveur.items()):
        marque = "" if m.valide else " (résultat invalide)"
        lignes.append(
            f"| {nom}{marque} | {_nombre(m.temps_s * 1000)} | {_nombre(m.developpees)} "
            f"| {_nombre(m.pic_kio)} | {_nombre(m.frontiere)} | {_nombre(m.chemin)} "
            f"| {_nombre(m.efficacite)} |"
        )
    return lignes


def _section_introduction() -> list[str]:
    return [
        "## Ce que compare ce rapport",
        "",
        "Trois programmes savent trouver le chemin entre l'entrée et la sortie d'un "
        "labyrinthe. Ce rapport les compare sur des labyrinthes déjà produits.",
        "",
        "Les labyrinthes ne se ressemblent pas tous : ils ont été construits par "
        "trois autres programmes (`kruskal`, `prim`, `recursive_backtracking`), qui "
        "produisent des couloirs plus ou moins longs et tortueux. Un même solveur ne "
        "se comporte donc pas pareil selon qui a construit le labyrinthe, et les "
        "résultats sont présentés séparément pour chacun des trois.",
        "",
        "| Programme | Comment il cherche le chemin |",
        "|---|---|",
        "| `astar` | se dirige vers la sortie, en examinant d'abord les cases qui "
        "en paraissent les plus proches |",
        "| `dijkstra` | explore dans toutes les directions à égalité, sans se "
        "diriger vers la sortie |",
        "| `recursive_backtracking` | avance tant qu'il peut, puis revient sur ses "
        "pas quand il tombe sur un cul-de-sac |",
        "",
        "Les trois trouvent un chemin de même longueur, mais pas au même prix. Ce "
        "prix se mesure de trois façons :",
        "",
        "| Question | Ce qui est mesuré | Unité |",
        "|---|---|---|",
        "| Lequel va le plus vite ? | durée de la recherche | millisecondes |",
        "| Lequel travaille le moins ? | nombre de cases examinées | cases |",
        "| Lequel occupe le moins de mémoire ? | mémoire maximale utilisée | Kio |",
        "",
        "Kio vaut 1024 octets. L'« efficacité » vaut 1 quand le programme n'examine "
        "que les cases de son chemin, et se rapproche de 0 quand il en examine "
        "beaucoup d'inutiles.",
        "",
    ]


def _section_protocole(inventaire: Inventaire) -> list[str]:
    return [
        "## Comment les mesures ont été prises",
        "",
        f"{_nombre(len(inventaire.mazes))} labyrinthes ont été relus depuis "
        "`outputs/`. Les fichiers de statistiques en ont été écartés : ils sont "
        "traités dans une section à part, plus bas.",
        "",
        "Les mesures suivent quatre règles.",
        "",
        "* Chaque labyrinthe est résolu par les trois programmes, l'un après "
        "l'autre : la comparaison porte donc toujours sur le même labyrinthe.",
        "* Un premier essai n'est pas compté. Le programme est lancé une fois sans "
        "être chronométré, ce passage servant à lire le labyrinthe et à remplir la "
        "mémoire de l'ordinateur. Sans lui, la première mesure serait trop élevée.",
        "* Le temps et la mémoire sont mesurés séparément. Compter la mémoire "
        "ralentit le programme : chronométrer les deux à la fois gonflerait la "
        "durée. Chaque programme est donc lancé deux fois.",
        "* Quand plusieurs labyrinthes ont la même taille, on retient la valeur du "
        "milieu de leurs mesures, et non leur moyenne. Un labyrinthe anormalement "
        "long à résoudre déplacerait la moyenne, mais pas cette valeur du milieu.",
        "",
        "La mémoire retenue est celle réellement utilisée, relevée par "
        "`tracemalloc`, l'outil de Python qui recense tout ce que le programme "
        "alloue. Regarder la seule liste d'attente du programme serait trompeur : "
        "elle ne compte ni ses tables de travail, ni le chemin déjà parcouru.",
        "",
    ]


def _section_ecart_frontiere(analyses: list[Analyse]) -> list[str]:
    """Cas où frontière et pic mémoire désignent deux solveurs différents.

    Ne produit rien si les données ne montrent pas d'écart : ce serait alors une
    observation gratuite.
    """
    ecarts = []
    for analyse in analyses:
        mesures = list(analyse.par_solveur.values())
        par_frontiere = min(mesures, key=lambda m: m.frontiere)
        par_pic = min(mesures, key=lambda m: m.pic_kio)
        if par_frontiere.solveur != par_pic.solveur:
            ecarts.append((analyse, par_frontiere, par_pic))

    if not ecarts:
        return []

    cadrage = (
        f"Dans les {_nombre(len(analyses))} groupes analysés"
        if len(ecarts) == len(analyses)
        else f"Sur {_nombre(len(analyses))} groupes analysés, {_nombre(len(ecarts))}"
    )

    lignes = [
        "## La liste d'attente ne dit pas tout",
        "",
        f"{cadrage}, le programme qui garde la plus petite liste d'attente n'est pas "
        "celui qui utilise le moins de mémoire au total. Comparer les programmes sur "
        "cette seule liste donnerait donc un autre classement, et un faux.",
        "",
        "| Cas | Plus petite liste d'attente | Mémoire réellement utilisée |",
        "|---|---|---|",
    ]
    for analyse, par_frontiere, par_pic in ecarts:
        cas = f"{_nom_generateur(analyse.generateur)}, n = {_nombre(analyse.n)}"
        lignes.append(
            f"| {cas} | {par_frontiere.solveur} ({_nombre(par_frontiere.frontiere)}) "
            f"| {par_pic.solveur} ({_nombre(par_pic.pic_kio)} Kio) |"
        )
    lignes.append("")
    return lignes


def _section_refus(inventaire: Inventaire) -> list[str]:
    refuses = [r for r in inventaire.refus if r.phase]
    reussis = [r for r in inventaire.refus if r.phase is None and r.passages is not None]

    lignes = ["## Les labyrinthes qui n'ont pas pu être produits", ""]

    if refuses:
        lignes += [
            f"{_nombre(len(refuses))} labyrinthes n'ont pas pu être construits : ils "
            "demandaient plus de mémoire que le programme ne s'en autorise. La "
            "dernière colonne indique le poids qu'aurait pris le calcul ; c'est une "
            "estimation faite à partir de la taille, pas une mesure, puisque rien "
            "n'a été lancé.",
            "",
            "| Fichier | Taille | Étape refusée | Mémoire qu'il aurait fallu |",
            "|---|---:|---|---:|",
        ]
        for refus in sorted(refuses, key=lambda r: (r.phase or "", r.n)):
            cout = format_bytes(refus.cout_bytes) if refus.cout_bytes else "inconnu"
            etape = "construction" if refus.phase == "generation" else "résolution"
            lignes.append(
                f"| {refus.chemin.name} | n = {_nombre(refus.n)} | {etape} | {cout} |"
            )
        lignes.append("")

    if reussis:
        lignes += [
            f"À l'inverse, {_nombre(len(reussis))} labyrinthes ont bien été construits. "
            "Leur image n'a pas pu être écrite, mais les chiffres du labyrinthe "
            "existent et sont réels :",
            "",
            "| Fichier | Taille | Cases | Passages | Longueur du chemin |",
            "|---|---:|---:|---:|---:|",
        ]
        for refus in sorted(reussis, key=lambda r: r.n):
            longueur = (
                _nombre(refus.chemin_longueur) if refus.chemin_longueur else "inconnu"
            )
            lignes.append(
                f"| {refus.chemin.name} | n = {_nombre(refus.n)} "
                f"| {_nombre(refus.n * refus.n)} | {_nombre(refus.passages)} "
                f"| {longueur} |"
            )
        lignes.append("")

    return lignes


def _section_limites(analyses: list[Analyse]) -> list[str]:
    nombres = sorted({a.labyrinthes for a in analyses})
    mini = min(nombres) if nombres else 0
    maxi = max(nombres) if nombres else 0

    return [
        "## Ce que ces résultats ne disent pas",
        "",
        f"* Les labyrinthes n'ont pas été produits pour ce comparatif, ils étaient "
        f"déjà là. Chaque groupe en compte de {mini} à {maxi}, et ceux qui n'en ont "
        "qu'un ne permettent pas de savoir si la mesure est typique. Une "
        "comparaison solide demanderait cinq labyrinthes par groupe.",
        "* Entre deux points d'une courbe, les labyrinthes ne sont pas les mêmes. La "
        "pente mélange donc deux effets : celui de la taille, et le fait que deux "
        "labyrinthes de même taille ne se résolvent pas à la même vitesse. Ce second "
        "effet peut atteindre 37 % du nombre de cases examinées.",
        "* Sur les courbes de mémoire, les pointillés ne sont pas des mesures mais "
        "des estimations calculées à partir de la taille. Aucun labyrinthe de ces "
        "tailles n'a pu être construit.",
        "",
    ]


def rendre_markdown(
    analyses: list[Analyse],
    inventaire: Inventaire,
    figures: list[Path],
) -> str:
    """Construit le compte rendu Markdown."""
    lignes = [
        "# Benchmark des solveurs",
        "",
        f"Ce rapport couvre {_nombre(len(analyses))} groupes de labyrinthes, chacun "
        f"résolu par les {len(solver_choices())} programmes : "
        f"{', '.join(solver_choices())}.",
        "",
    ]
    lignes += _section_introduction()
    lignes += _section_protocole(inventaire)

    lignes += ["## Résultats", ""]
    for analyse in analyses:
        lignes.append(
            f"### Labyrinthes {_nom_generateur(analyse.generateur)}, "
            f"n = {_nombre(analyse.n)}"
        )
        lignes.append("")
        if analyse.labyrinthes > 1:
            lignes.append(
                f"Cette taille compte {_nombre(analyse.labyrinthes)} labyrinthes "
                "différents. Chaque chiffre est la valeur du milieu de leurs mesures."
            )
        else:
            lignes.append(
                "Cette taille ne compte qu'un labyrinthe : il n'y a pas de valeur du "
                "milieu à calculer."
            )
        lignes.append("")
        lignes += _tableau(analyse)
        lignes.append("")

        rapide, efficace, leger = _verdict(analyse)
        lignes += [
            f"- Le plus rapide : {rapide.solveur}, avec "
            f"{_nombre(rapide.temps_s * 1000)} ms",
            f"- Le plus économe en travail : {efficace.solveur}, avec "
            f"{_nombre(efficace.developpees)} cases examinées",
            f"- Le plus économe en mémoire : {leger.solveur}, avec "
            f"{_nombre(leger.pic_kio)} Kio",
            "",
        ]

    lignes += _section_ecart_frontiere(analyses)

    lignes += ["## Qui gagne le plus souvent", ""]
    victoires: dict[str, dict[str, int]] = {
        nom: {"rapide": 0, "efficace": 0, "leger": 0} for nom in solver_choices()
    }
    for analyse in analyses:
        rapide, efficace, leger = _verdict(analyse)
        victoires[rapide.solveur]["rapide"] += 1
        victoires[efficace.solveur]["efficace"] += 1
        victoires[leger.solveur]["leger"] += 1

    lignes += [
        "Chaque groupe de labyrinthes donne un gagnant par critère. Voici combien de "
        "fois chaque programme l'emporte, sur l'ensemble des groupes analysés.",
        "",
        "| Programme | Le plus rapide | Le plus économe en travail "
        "| Le plus économe en mémoire |",
        "|---|---:|---:|---:|",
    ]
    for nom in solver_choices():
        v = victoires[nom]
        lignes.append(
            f"| {nom} | {_nombre(v['rapide'])} | {_nombre(v['efficace'])} "
            f"| {_nombre(v['leger'])} |"
        )
    lignes.append("")

    lignes += _section_refus(inventaire)

    if figures:
        lignes += ["## Figures", ""]
        lignes += [f"- `{figure.name}`" for figure in figures]
        lignes.append("")

    lignes += _section_limites(analyses)
    return "\n".join(lignes) + "\n"


def _series_par_generateur(
    analyses: list[Analyse],
) -> dict[str | None, dict[str, dict[int, Metriques]]]:
    """``générateur -> solveur -> n -> métriques``. La clé vaut ``None`` si le
    nom du fichier ne dit pas le générateur."""
    series: dict[str | None, dict[str, dict[int, Metriques]]] = {}
    for analyse in analyses:
        par_solveur = series.setdefault(analyse.generateur, {})
        for solveur, metriques in analyse.par_solveur.items():
            par_solveur.setdefault(solveur, {})[analyse.n] = metriques
    return series


def _meilleurs(analyses: list[Analyse]) -> tuple[dict, dict[str, str]]:
    """Solveur le plus efficace de chaque générateur, sur l'ensemble des tailles.

    Le choisir globalement, et non taille par taille, garde une courbe cohérente :
    sinon la ligne changerait de solveur d'un point à l'autre.
    """
    par_generateur: dict[str, dict[str, dict[int, Metriques]]] = {}
    for analyse in analyses:
        if analyse.generateur is None:
            continue
        par_generateur.setdefault(analyse.generateur, {})
        for solveur, metriques in analyse.par_solveur.items():
            par_generateur[analyse.generateur].setdefault(solveur, {})[
                analyse.n
            ] = metriques

    series: dict[str, dict[int, Metriques]] = {}
    meilleurs: dict[str, str] = {}
    for nom, par_solveur in par_generateur.items():
        totaux = {
            solveur: sum(m.developpees for m in par_n.values())
            for solveur, par_n in par_solveur.items()
        }
        if not totaux:
            continue
        gagnant = min(totaux, key=lambda solveur: totaux[solveur])
        meilleurs[nom] = gagnant
        series[nom] = par_solveur[gagnant]

    return series, meilleurs


def _refus_par_generateur(inventaire: Inventaire) -> dict[str | None, dict[int, int]]:
    """Coûts estimés des générations refusées, par générateur."""
    refus: dict[str | None, dict[int, int]] = {}
    for entree in inventaire.refus:
        if entree.phase != "generation" or entree.cout_bytes is None:
            continue
        refus.setdefault(entree.generateur, {})[entree.n] = entree.cout_bytes
    return refus


def produire_figures(
    analyses: list[Analyse],
    inventaire: Inventaire,
    dossier: Path,
) -> list[Path]:
    """Écrit une figure par générateur, plus celle des meilleurs solveurs.

    Les labyrinthes dont le nom ne dit pas le générateur sont mesurés et figurent
    dans le rapport, mais n'ont pas de courbe : ils sont trop peu nombreux pour
    qu'une courbe compare quoi que ce soit.
    """
    from benchmarks import courbes

    ecrites: list[Path] = []
    refus = _refus_par_generateur(inventaire)

    for nom, par_solveur in _series_par_generateur(analyses).items():
        if nom is None:
            continue
        ecrites.append(
            courbes.figure_generateur(
                nom,
                par_solveur,
                refus.get(nom, {}),
                chemin=dossier / f"courbes_{_slug(nom)}.png",
            )
        )

    series, meilleurs = _meilleurs(analyses)
    if series:
        ecrites.append(
            courbes.figure_meilleurs(
                series, refus, meilleurs, chemin=dossier / "courbes_meilleurs.png"
            )
        )
    return ecrites


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="scaling.py",
        description="Compare les solveurs sur les labyrinthes de outputs/",
    )
    parser.add_argument(
        "--dossier", default=str(OUTPUTS), help="dossier à analyser (défaut : outputs/)"
    )
    parser.add_argument(
        "--sizes",
        type=int,
        nargs="+",
        default=None,
        metavar="N",
        help="ne garder que ces tailles de labyrinthe",
    )
    parser.add_argument(
        "--sans-courbes", action="store_true", help="ne pas produire les figures"
    )
    return parser


def main(argv: list[str] | None = None) -> int:
    """Point d'entrée : collecte, analyse, rapport et figures."""
    # Même raison que dans cli.py : sans cela les accents sortent en « ? » sous
    # Windows, dont la console n'est pas en UTF-8 par défaut.
    for flux in (sys.stdout, sys.stderr):
        reconfigure = getattr(flux, "reconfigure", None)
        if callable(reconfigure):
            with contextlib.suppress(ValueError):
                reconfigure(encoding="utf-8")

    args = build_parser().parse_args(argv)
    dossier = Path(args.dossier).resolve()

    inventaire = lire_outputs(dossier)
    for chemin, raison in inventaire.ignores:
        print(f"ignoré : {chemin.name} ({raison})", file=sys.stderr)

    if not inventaire.mazes:
        print(
            f"Aucun labyrinthe exploitable dans {dossier}. Générez-en d'abord : "
            "mazes generate --n 100 --algorithm kruskal",
            file=sys.stderr,
        )
        return 1

    analyses = analyser(inventaire, tailles=set(args.sizes) if args.sizes else None)
    if not analyses:
        print(
            f"Aucun labyrinthe aux tailles demandées parmi {sorted(args.sizes)}.",
            file=sys.stderr,
        )
        return 1

    figures: list[Path] = []
    if not args.sans_courbes:
        figures = produire_figures(analyses, inventaire, dossier)

    sortie = dossier / "benchmark.md"
    sortie.write_text(rendre_markdown(analyses, inventaire, figures), encoding="utf-8")

    print(f"Compte rendu écrit dans {sortie}")
    for figure in figures:
        print(f"Figure : {figure}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
