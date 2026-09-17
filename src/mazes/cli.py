"""Interface en ligne de commande.

Pipeline de la consigne : générer (algorithme choisi) -> résoudre (algorithme
choisi) -> exporter en JPEG. Aucun algorithme n'est codé en dur : les choix
viennent des registres, donc ajouter un fichier dans ``generators/`` ou
``solvers/`` suffit à l'exposer.
"""

from __future__ import annotations

import argparse
import contextlib
import sys
from pathlib import Path

from mazes.core.grid import entry_cell, exit_cell
from mazes.core.rng import RandomSource
from mazes.core.validation import is_perfect, validate_path
from mazes.generators import available_generators, generator_choices, get_generator
from mazes.rendering import read_ascii, render_to_string, write_ascii, write_image
from mazes.solvers import available_solvers, get_solver, solver_choices

OUTPUTS = Path("outputs")


def _sortie(chemin: str | None, defaut: str) -> Path:
    if chemin:
        p = Path(chemin)
    else:
        OUTPUTS.mkdir(exist_ok=True)
        p = OUTPUTS / defaut
    p.parent.mkdir(parents=True, exist_ok=True)
    return p


def _ecrire_resultat(grille, resultat, base: Path) -> Path:
    """Écrit le labyrinthe résolu en ASCII (``.txt``) et en image JPEG (``.jpg``)."""
    txt = base.with_suffix(".txt")
    write_ascii(grille, txt, state=resultat.state)
    jpg = base.with_suffix(".jpg")
    write_image(grille, jpg, state=resultat.state)
    return jpg


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
    grille = generateur.generate(args.n, rng)

    if args.check and not is_perfect(grille):
        print("ERREUR : le labyrinthe produit n'est pas parfait", file=sys.stderr)
        return 1

    sortie = _sortie(args.output, f"maze_{args.algorithm}_{args.n}.txt")
    write_ascii(grille, sortie)
    print(f"généré avec {args.algorithm} (seed {rng.seed}) — écrit dans {sortie}", file=sys.stderr)

    if args.print:
        print(render_to_string(grille))
    return 0


def cmd_solve(args: argparse.Namespace) -> int:
    grille = read_ascii(args.input)
    solveur = get_solver(args.algorithm)
    start, goal = entry_cell(grille), exit_cell(grille)
    resultat = solveur.solve(grille, start, goal)

    if not resultat.path:
        print("Aucun chemin trouvé.", file=sys.stderr)
        return 1
    problemes = validate_path(grille, resultat.path, start, goal)
    if problemes:
        print("Chemin invalide : " + "; ".join(problemes), file=sys.stderr)
        return 1

    base = _sortie(args.output, f"solved_{args.algorithm}_{grille.n}")
    jpg = _ecrire_resultat(grille, resultat, base)
    print(
        f"{args.algorithm} : chemin {resultat.path_length} cellules, "
        f"développées {resultat.expanded}, {resultat.elapsed_s * 1000:.1f} ms",
        file=sys.stderr,
    )
    print(f"ASCII : {base.with_suffix('.txt')}", file=sys.stderr)
    print(f"JPEG  : {jpg}", file=sys.stderr)
    return 0


def cmd_run(args: argparse.Namespace) -> int:
    rng = RandomSource(args.seed)
    grille = get_generator(args.generator).generate(args.n, rng)
    solveur = get_solver(args.solver)
    start, goal = entry_cell(grille), exit_cell(grille)
    resultat = solveur.solve(grille, start, goal)

    if not resultat.path:
        print("Aucun chemin trouvé.", file=sys.stderr)
        return 1

    base = _sortie(args.output, f"{args.generator}_{args.solver}_{args.n}")
    jpg = _ecrire_resultat(grille, resultat, base)
    print(
        f"généré avec {args.generator}, résolu avec {args.solver} (seed {rng.seed})",
        file=sys.stderr,
    )
    print(f"ASCII : {base.with_suffix('.txt')}", file=sys.stderr)
    print(f"JPEG  : {jpg}", file=sys.stderr)
    return 0


def cmd_convert(args: argparse.Namespace) -> int:
    grille = read_ascii(args.input)
    sortie = Path(args.output)
    sortie.parent.mkdir(parents=True, exist_ok=True)
    if sortie.suffix.lower() in (".txt", ".md"):
        write_ascii(grille, sortie)
    else:
        write_image(grille, sortie)
    print(f"écrit dans {sortie}", file=sys.stderr)
    return 0


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
    p.set_defaults(func=cmd_generate)

    p = sub.add_parser("solve", help="résout un labyrinthe (ASCII) et l'exporte en JPEG")
    p.add_argument("--input", required=True,
                   help="labyrinthe ASCII à résoudre (généré au préalable)")
    p.add_argument("--algorithm", default=noms_sol[0], choices=noms_sol,
                   help="algorithme de résolution")
    p.add_argument("--output", default=None, help="fichier de sortie (sans extension)")
    p.set_defaults(func=cmd_solve)

    p = sub.add_parser("run", help="pipeline complet : générer -> résoudre -> JPEG")
    p.add_argument("--n", type=int, default=20, help="côté de la grille")
    p.add_argument("--generator", default=noms_gen[0], choices=noms_gen,
                   help="algorithme de génération")
    p.add_argument("--solver", default=noms_sol[0], choices=noms_sol,
                   help="algorithme de résolution")
    p.add_argument("--seed", type=int, default=None, help="graine reproductible")
    p.add_argument("--output", default=None, help="fichier de sortie (sans extension)")
    p.set_defaults(func=cmd_run)

    p = sub.add_parser("convert", help="convertit un labyrinthe ASCII en image")
    p.add_argument("--input", required=True)
    p.add_argument("--output", required=True)
    p.set_defaults(func=cmd_convert)

    return parser


def main(argv: list[str] | None = None) -> int:
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
