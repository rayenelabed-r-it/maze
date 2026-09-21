"""Interface en ligne de commande.

Pipeline de la consigne : générer (algorithme choisi) -> résoudre (algorithme
choisi) -> exporter en JPEG. Aucun algorithme n'est codé en dur : les choix
viennent des registres, donc ajouter un fichier dans ``generators/`` ou
``solvers/`` suffit à l'exposer.

Trois refus possibles, dans cet ordre : le budget mémoire, qui empêche de lancer
le calcul (``mazes.budget``) ; la politique d'export, qui décide ce qui tient sur
le disque (``mazes.rendering.ExportPolicy``) ; et la taille du fichier, qui
déclenche une demande de confirmation (``mazes.interaction``).

Dans les trois cas, un fichier de statistiques remplace la sortie manquante.
"""

from __future__ import annotations

import argparse
import contextlib
import sys
from collections.abc import Callable
from pathlib import Path

from mazes.budget import (
    BUDGET_ENV_VAR,
    estimate_generation,
    estimate_solving,
    fits_generation,
    fits_solving,
    memory_budget,
)
from mazes.core.grid import WallGrid, entry_cell, exit_cell
from mazes.core.rng import RandomSource
from mazes.core.validation import is_perfect, validate_path
from mazes.generators import available_generators, generator_choices, get_generator
from mazes.interaction import should_write
from mazes.rendering import (
    ExportPlan,
    ExportPolicy,
    format_bytes,
    read_ascii,
    render_to_string,
    write_ascii,
    write_image,
    write_refused,
    write_stats,
)
from mazes.solvers import available_solvers, get_solver, solver_choices
from mazes.solvers.base import SolveResult

OUTPUTS = Path("outputs")


# --------------------------------------------------------------------------- #
# Chemins et politique
# --------------------------------------------------------------------------- #
def _sortie(chemin: str | None, defaut: str) -> Path:
    if chemin:
        p = Path(chemin)
    else:
        OUTPUTS.mkdir(exist_ok=True)
        p = OUTPUTS / defaut
    p.parent.mkdir(parents=True, exist_ok=True)
    return p


def _politique_export() -> ExportPolicy:
    """Fabrique la politique d'export.

    Passe par une fonction au lieu d'appeler ``ExportPolicy()`` en direct : c'est
    le seul point où les tests peuvent injecter des limites basses. Sans lui,
    vérifier qu'un refus se produit demanderait d'écrire des fichiers de
    plusieurs gigaoctets.
    """
    return ExportPolicy()


def _chemin_statistiques(base: Path) -> Path:
    """``outputs/x.txt`` -> ``outputs/x_statistiques.txt``."""
    return base.with_name(f"{base.stem}_statistiques.txt")


# --------------------------------------------------------------------------- #
# Écriture sous confirmation
# --------------------------------------------------------------------------- #
def _ecrire_si_autorise(
    chemin: Path,
    octets: int,
    quoi: str,
    ecrire: Callable[[Path], object],
    *,
    force: bool,
    stats_only: bool,
) -> Path | None:
    """Écrit ``chemin`` après confirmation. ``None`` si l'écriture est refusée.

    On n'arrive ici que pour un fichier que la politique autorise, donc un
    verdict ``None`` (aucun terminal joignable) suit cette décision et écrit.
    """
    verdict = should_write(
        octets,
        f"Le fichier {quoi} {chemin.name} pèsera {format_bytes(octets)}. "
        f"Souhaites-tu l'enregistrer ?",
        force=force,
        stats_only=stats_only,
    )
    if verdict is None or verdict:
        ecrire(chemin)
        return chemin

    print(f"{quoi} non enregistré ({format_bytes(octets)}).", file=sys.stderr)
    return None


def _signaler_refus_ascii(plan: ExportPlan) -> None:
    """Explique un refus décidé par la politique, sans qu'aucune question soit posée."""
    print(
        f"ASCII non écrit : {plan.reason}",
        file=sys.stderr,
    )


def _refuser_calcul(
    *,
    etiquette: str,
    phase: str,
    quoi: str,
    algorithme: str,
    n: int,
    base: Path,
    cout: int,
    alternatives: list[str],
) -> int:
    """Refuse un calcul hors budget et écrit les statistiques à la place.

    Code de retour ``1``, contrairement au refus d'export qui sort en ``0`` : ici
    le labyrinthe demandé n'existe pas du tout.

    ``etiquette`` porte les accents du message console, ``phase`` la clé écrite
    dans le fichier de statistiques, lequel est encodé en ASCII strict. Les
    confondre fait planter l'écriture sur le « é » de « Résolution ».
    """
    budget = memory_budget()

    print(
        f"{etiquette} refusée : {algorithme} demanderait {format_bytes(cout)} "
        f"pour n={n}, au-delà du budget de {format_bytes(budget)}.",
        file=sys.stderr,
    )

    # Ne conseiller que ce qui passe : quand c'est prim qui echoue, proposer
    # prim serait une plaisanterie.
    piste = (
        f"Essayer un {quoi} plus sobre : {', '.join(alternatives)}."
        if alternatives
        else f"Aucun {quoi} ne passe à cette taille."
    )
    print(f"{piste} Relever {BUDGET_ENV_VAR}, ou réduire --n.", file=sys.stderr)

    chemin = write_refused(
        n,
        _chemin_statistiques(base),
        phase=phase.lower(),
        raison=(
            f"{algorithme} demanderait {format_bytes(cout)} pour {n * n} cellules "
            f"(budget {format_bytes(budget)})"
        ),
    )
    print(f"statistiques : {chemin}", file=sys.stderr)
    return 1


def _refuser_generation(generateur: str, n: int, base: Path) -> int:
    """Refus d'une génération : le labyrinthe lui-même n'a pas pu être construit."""
    return _refuser_calcul(
        etiquette="Génération",
        phase="generation",
        quoi="générateur",
        algorithme=generateur,
        n=n,
        base=base,
        cout=estimate_generation(generateur, n),
        alternatives=sorted(
            nom
            for nom in generator_choices()
            if nom != generateur and fits_generation(nom, n)
        ),
    )


def _refuser_resolution(solveur: str, n: int, base: Path) -> int:
    """Refus d'une résolution : le labyrinthe existe, mais pas de quoi le parcourir."""
    return _refuser_calcul(
        etiquette="Résolution",
        phase="resolution",
        quoi="solveur",
        algorithme=solveur,
        n=n,
        base=base,
        cout=estimate_solving(solveur, n),
        alternatives=sorted(
            nom for nom in solver_choices() if nom != solveur and fits_solving(nom, n)
        ),
    )


def _ecrire_resultat(
    grille: WallGrid,
    resultat: SolveResult,
    base: Path,
    *,
    plan: ExportPlan,
    force: bool,
    stats_only: bool,
) -> tuple[Path | None, Path | None]:
    """Écrit l'ASCII puis le JPEG, chacun sous confirmation.

    Renvoie les deux chemins, ou ``None`` là où l'écriture n'a pas eu lieu --
    refusée par la politique ou par l'utilisateur. L'appelant en déduit s'il doit
    écrire un fichier de statistiques.
    """
    txt = base.with_suffix(".txt")
    if plan.ascii_full:
        ascii_ecrit = _ecrire_si_autorise(
            txt,
            plan.ascii_bytes,
            "ASCII",
            lambda chemin: write_ascii(grille, chemin, state=resultat.state),
            force=force,
            stats_only=stats_only,
        )
    else:
        # La politique refuse l'ASCII, ou ne sait produire qu'une version
        # réduite que ``write_ascii`` ne sait pas écrire.
        _signaler_refus_ascii(plan)
        ascii_ecrit = None

    jpg = base.with_suffix(".jpg")
    image_ecrite = _ecrire_si_autorise(
        jpg,
        plan.image_bytes,
        "image",
        lambda chemin: write_image(
            grille, chemin, state=resultat.state, scale=plan.image_scale
        ),
        force=force,
        stats_only=stats_only,
    )
    return ascii_ecrit, image_ecrite


def _ecrire_statistiques(
    grille: WallGrid,
    base: Path,
    plan: ExportPlan,
    *,
    resultat: SolveResult | None = None,
    ascii_ecrit: bool,
) -> Path:
    """Écrit le fichier de statistiques et l'annonce."""
    chemin = write_stats(
        grille,
        _chemin_statistiques(base),
        plan,
        result=resultat,
        ascii_ecrit=ascii_ecrit,
    )
    print(f"statistiques : {chemin}", file=sys.stderr)
    return chemin


def _ajouter_options_ecriture(parser: argparse.ArgumentParser) -> None:
    """Drapeaux communs de contrôle de l'écriture, sur toutes les sous-commandes."""
    parser.add_argument(
        "--yes",
        "-y",
        action="store_true",
        help="enregistrer sans demander confirmation",
    )
    parser.add_argument(
        "--stats-only",
        action="store_true",
        help="n'écrire que le fichier de statistiques, aucune sortie lourde",
    )


# --------------------------------------------------------------------------- #
# Sous-commandes
# --------------------------------------------------------------------------- #
def cmd_list(args: argparse.Namespace) -> int:
    print("Générateurs :")
    for nom, cls in available_generators().items():
        print(f"  {nom:<24} {cls.description}  [{cls.complexity}]")
    print("\nSolveurs :")
    for nom, cls in available_solvers().items():
        marque = "optimal" if cls.optimal else "non optimal"
        print(f"  {nom:<24} {cls.description}  [{cls.complexity}, {marque}]")
    return 0


def cmd_generate(args: argparse.Namespace) -> int:
    rng = RandomSource(args.seed)
    generateur = get_generator(args.algorithm)
    sortie = _sortie(args.output, f"maze_{args.algorithm}_{args.n}.txt")

    # Avant toute allocation : partir quand meme tuerait le processus.
    if not fits_generation(args.algorithm, args.n):
        return _refuser_generation(args.algorithm, args.n, sortie)

    grille = generateur.generate(args.n, rng)

    if args.check and not is_perfect(grille):
        print("ERREUR : le labyrinthe produit n'est pas parfait", file=sys.stderr)
        return 1

    plan = _politique_export().plan(grille.n)

    if plan.ascii_full:
        ascii_ecrit = _ecrire_si_autorise(
            sortie,
            plan.ascii_bytes,
            "ASCII",
            lambda chemin: write_ascii(grille, chemin),
            force=args.yes,
            stats_only=args.stats_only,
        )
    else:
        _signaler_refus_ascii(plan)
        ascii_ecrit = None

    if ascii_ecrit is not None:
        print(
            f"généré avec {args.algorithm} (seed {rng.seed}) — écrit dans {sortie}",
            file=sys.stderr,
        )

    if plan.write_stats or ascii_ecrit is None:
        _ecrire_statistiques(grille, sortie, plan, ascii_ecrit=ascii_ecrit is not None)

    if args.print:
        print(render_to_string(grille))
    return 0


def cmd_solve(args: argparse.Namespace) -> int:
    grille = read_ascii(args.input)
    solveur = get_solver(args.algorithm)
    base = _sortie(args.output, f"solved_{args.algorithm}_{grille.n}")

    # La grille existe deja : seule la resolution peut etre hors budget.
    if not fits_solving(args.algorithm, grille.n):
        return _refuser_resolution(args.algorithm, grille.n, base)

    start, goal = entry_cell(grille), exit_cell(grille)
    resultat = solveur.solve(grille, start, goal)

    if not resultat.path:
        print("Aucun chemin trouvé.", file=sys.stderr)
        return 1
    problemes = validate_path(grille, resultat.path, start, goal)
    if problemes:
        print("Chemin invalide : " + "; ".join(problemes), file=sys.stderr)
        return 1

    plan = _politique_export().plan(grille.n)
    txt, jpg = _ecrire_resultat(
        grille, resultat, base, plan=plan, force=args.yes, stats_only=args.stats_only
    )

    print(
        f"{args.algorithm} : chemin {resultat.path_length} cellules, "
        f"développées {resultat.expanded}, {resultat.elapsed_s * 1000:.1f} ms",
        file=sys.stderr,
    )

    if plan.write_stats or txt is None or jpg is None:
        _ecrire_statistiques(
            grille, base, plan, resultat=resultat, ascii_ecrit=txt is not None
        )

    if txt is not None:
        print(f"ASCII : {txt}", file=sys.stderr)
    if jpg is not None:
        print(f"JPEG  : {jpg}", file=sys.stderr)
    return 0


def cmd_run(args: argparse.Namespace) -> int:
    rng = RandomSource(args.seed)
    base = _sortie(args.output, f"{args.generator}_{args.solver}_{args.n}")

    # Les deux phases sont verifiees avant d'allouer quoi que ce soit.
    if not fits_generation(args.generator, args.n):
        return _refuser_generation(args.generator, args.n, base)
    if not fits_solving(args.solver, args.n):
        return _refuser_resolution(args.solver, args.n, base)

    grille = get_generator(args.generator).generate(args.n, rng)
    solveur = get_solver(args.solver)
    start, goal = entry_cell(grille), exit_cell(grille)
    resultat = solveur.solve(grille, start, goal)

    if not resultat.path:
        print("Aucun chemin trouvé.", file=sys.stderr)
        return 1

    plan = _politique_export().plan(grille.n)
    txt, jpg = _ecrire_resultat(
        grille, resultat, base, plan=plan, force=args.yes, stats_only=args.stats_only
    )

    print(
        f"généré avec {args.generator}, résolu avec {args.solver} (seed {rng.seed})",
        file=sys.stderr,
    )

    if plan.write_stats or txt is None or jpg is None:
        _ecrire_statistiques(
            grille, base, plan, resultat=resultat, ascii_ecrit=txt is not None
        )

    if txt is not None:
        print(f"ASCII : {txt}", file=sys.stderr)
    if jpg is not None:
        print(f"JPEG  : {jpg}", file=sys.stderr)
    return 0


def cmd_convert(args: argparse.Namespace) -> int:
    grille = read_ascii(args.input)
    sortie = Path(args.output)
    sortie.parent.mkdir(parents=True, exist_ok=True)
    plan = _politique_export().plan(grille.n)

    if sortie.suffix.lower() in (".txt", ".md"):
        if not plan.ascii_full:
            _signaler_refus_ascii(plan)
            _ecrire_statistiques(grille, sortie, plan, ascii_ecrit=False)
            return 0
        ecrit = _ecrire_si_autorise(
            sortie,
            plan.ascii_bytes,
            "ASCII",
            lambda chemin: write_ascii(grille, chemin),
            force=args.yes,
            stats_only=args.stats_only,
        )
    else:
        ecrit = _ecrire_si_autorise(
            sortie,
            plan.image_bytes,
            "image",
            lambda chemin: write_image(grille, chemin, scale=plan.image_scale),
            force=args.yes,
            stats_only=args.stats_only,
        )

    if plan.write_stats or ecrit is None:
        _ecrire_statistiques(grille, sortie, plan, ascii_ecrit=ecrit is not None)

    if ecrit is not None:
        print(f"écrit dans {ecrit}", file=sys.stderr)
    return 0


# --------------------------------------------------------------------------- #
# Analyse des arguments
# --------------------------------------------------------------------------- #
def build_parser() -> argparse.ArgumentParser:
    noms_gen = generator_choices()
    noms_sol = solver_choices()

    parser = argparse.ArgumentParser(
        prog="mazes",
        description="Génération, résolution et export JPEG de labyrinthes parfaits",
    )
    sub = parser.add_subparsers(dest="command", required=True)

    p = sub.add_parser("list", help="liste les algorithmes disponibles")
    p.set_defaults(func=cmd_list)

    p = sub.add_parser("generate", help="génère un labyrinthe et l'écrit en ASCII")
    p.add_argument("--n", type=int, default=20, help="côté de la grille")
    p.add_argument("--algorithm", default=noms_gen[0], choices=noms_gen,
                   help="algorithme de génération")
    p.add_argument("--seed", type=int, default=None, help="graine reproductible")
    p.add_argument("--output", default=None, help="fichier ASCII de sortie")
    p.add_argument("--print", action="store_true", help="affiche le labyrinthe dans le terminal")
    p.add_argument("--check", action="store_true", help="vérifie que le labyrinthe est parfait")
    _ajouter_options_ecriture(p)
    p.set_defaults(func=cmd_generate)

    p = sub.add_parser("solve", help="résout un labyrinthe (ASCII) et l'exporte en JPEG")
    p.add_argument("--input", required=True,
                   help="labyrinthe ASCII à résoudre (généré au préalable)")
    p.add_argument("--algorithm", default=noms_sol[0], choices=noms_sol,
                   help="algorithme de résolution")
    p.add_argument("--output", default=None, help="fichier de sortie (sans extension)")
    _ajouter_options_ecriture(p)
    p.set_defaults(func=cmd_solve)

    p = sub.add_parser("run", help="pipeline complet : générer -> résoudre -> JPEG")
    p.add_argument("--n", type=int, default=20, help="côté de la grille")
    p.add_argument("--generator", default=noms_gen[0], choices=noms_gen,
                   help="algorithme de génération")
    p.add_argument("--solver", default=noms_sol[0], choices=noms_sol,
                   help="algorithme de résolution")
    p.add_argument("--seed", type=int, default=None, help="graine reproductible")
    p.add_argument("--output", default=None, help="fichier de sortie (sans extension)")
    _ajouter_options_ecriture(p)
    p.set_defaults(func=cmd_run)

    p = sub.add_parser("convert", help="convertit un labyrinthe ASCII en image")
    p.add_argument("--input", required=True)
    p.add_argument("--output", required=True)
    _ajouter_options_ecriture(p)
    p.set_defaults(func=cmd_convert)

    return parser


def main(argv: list[str] | None = None) -> int:
    """Point d'entrée : exécute la sous-commande et renvoie un code de sortie.

    ``0`` succès, y compris quand seules les statistiques sont écrites ; ``1``
    échec métier (chemin absent, labyrinthe non parfait, calcul refusé faute de
    mémoire) ; ``2`` erreur d'entrée (fichier manquant, extension inconnue).

    Un refus pour mémoire sort en ``1`` et non en ``0`` : le labyrinthe demandé
    n'existe pas, alors qu'un refus d'export laisse le labyrinthe intact.

    ``argparse`` sort en ``SystemExit(2)`` avant d'arriver ici si la ligne de
    commande est mal formée.
    """
    # Forcer UTF-8 sur la console : sinon les accents français sortent en `�`
    # sous Windows (codepage cp1252/cp850 par défaut).
    for flux in (sys.stdout, sys.stderr):
        reconfigure = getattr(flux, "reconfigure", None)
        if callable(reconfigure):
            with contextlib.suppress(ValueError):
                reconfigure(encoding="utf-8")

    parser = build_parser()
    args = parser.parse_args(argv)
    try:
        return args.func(args)
    except (KeyError, ValueError, RuntimeError, FileNotFoundError) as err:
        print(f"Erreur : {err}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
