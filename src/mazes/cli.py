"""Interface en ligne de commande.

Aucun algorithme n'est codé en dur ici : les choix proposés par --algorithm
viennent des registres, donc ajouter un fichier dans generators/ ou solvers/
suffit à l'exposer.
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

from mazes.core.rng import RandomSource
from mazes.core.validation import is_perfect, validate_path
from mazes.generators import available_generators, get_generator
from mazes.rendering import image as image_rendering
from mazes.rendering.ascii import read_ascii_file, to_ascii, write_ascii_file
from mazes.rendering.policy import DEFAULT_POLICY
from mazes.solvers import available_solvers, get_solver

OUTPUTS = Path("outputs")


def _sortie(chemin: str | None, defaut: str) -> Path:
    if chemin:
        p = Path(chemin)
    else:
        OUTPUTS.mkdir(exist_ok=True)
        p = OUTPUTS / defaut
    p.parent.mkdir(parents=True, exist_ok=True)
    return p


def cmd_list(args: argparse.Namespace) -> int:
    print("Générateurs :")
    for cls in available_generators():
        print(f"  {cls.name:<24} {cls.description}  [{cls.complexity}]")
    print("\nSolveurs :")
    for cls in available_solvers():
        marque = "optimal" if cls.optimal else "non optimal"
        print(f"  {cls.name:<24} {cls.description}  [{cls.complexity}, {marque}]")
    return 0


def _charger_grille(args: argparse.Namespace):
    if getattr(args, "input", None):
        return read_ascii_file(args.input)
    rng = RandomSource(args.seed)
    generateur = get_generator(args.algorithm_gen)
    grille = generateur.generate(args.n, rng)
    print(f"Généré avec {generateur.name} (seed {rng.seed})", file=sys.stderr)
    return grille


def cmd_generate(args: argparse.Namespace) -> int:
    rng = RandomSource(args.seed)
    generateur = get_generator(args.algorithm)
    grille = generateur.generate(args.n, rng)

    if args.check and not is_perfect(grille):
        print("ERREUR : le labyrinthe produit n'est pas parfait", file=sys.stderr)
        return 1

    texte = to_ascii(grille)
    sortie = _sortie(args.output, f"maze_{generateur.name}_{args.n}.txt")
    sortie.write_text(texte + "\n", encoding="utf-8")
    print(f"seed {rng.seed} — écrit dans {sortie}", file=sys.stderr)

    if DEFAULT_POLICY.should_print(args.n):
        print(texte)
    else:
        print(DEFAULT_POLICY.explain(args.n), file=sys.stderr)

    if args.image:
        taille = DEFAULT_POLICY.cell_size(args.n, args.cell_size)
        fichier = sortie.with_suffix(".png")
        image_rendering.save_image(str(fichier), grille, cell_size=taille)
        print(f"image : {fichier}", file=sys.stderr)
    return 0


def cmd_solve(args: argparse.Namespace) -> int:
    grille = _charger_grille(args)
    solveur = get_solver(args.algorithm)
    start, goal = grille.entry, grille.goal

    resultat = solveur.solve(grille, start, goal)
    if not resultat.found:
        print("Aucun chemin trouvé entre l'entrée et la sortie.", file=sys.stderr)
        return 1

    validate_path(grille, resultat.path, start, goal)

    texte = to_ascii(grille, resultat.state)
    sortie = _sortie(args.output, f"solved_{solveur.name}_{grille.n}.txt")
    sortie.write_text(texte + "\n", encoding="utf-8")

    if DEFAULT_POLICY.should_print(grille.n):
        print(texte)

    print(
        f"{solveur.name} : chemin {resultat.length} cellules, "
        f"développées {resultat.expanded}, atteintes {resultat.explored}, "
        f"pic frontière {resultat.max_frontier}, {resultat.elapsed_s * 1000:.1f} ms",
        file=sys.stderr,
    )
    print(f"écrit dans {sortie}", file=sys.stderr)

    if args.image:
        taille = DEFAULT_POLICY.cell_size(grille.n, args.cell_size)
        fichier = sortie.with_suffix(".png")
        image_rendering.save_image(str(fichier), grille, resultat.path, cell_size=taille)
        print(f"image : {fichier}", file=sys.stderr)
    return 0


def cmd_convert(args: argparse.Namespace) -> int:
    grille = read_ascii_file(args.input)
    sortie = Path(args.output)
    sortie.parent.mkdir(parents=True, exist_ok=True)
    if sortie.suffix.lower() in (".txt", ".md"):
        write_ascii_file(str(sortie), grille)
    else:
        taille = DEFAULT_POLICY.cell_size(grille.n, args.cell_size)
        image_rendering.save_image(str(sortie), grille, cell_size=taille)
    print(f"écrit dans {sortie}", file=sys.stderr)
    return 0


def build_parser() -> argparse.ArgumentParser:
    noms_gen = [c.name for c in available_generators()]
    noms_sol = [c.name for c in available_solvers()]

    parser = argparse.ArgumentParser(prog="mazes", description="Génération et résolution de labyrinthes parfaits")
    sub = parser.add_subparsers(dest="command", required=True)

    p = sub.add_parser("list", help="liste les algorithmes disponibles")
    p.set_defaults(func=cmd_list)

    p = sub.add_parser("generate", help="génère un labyrinthe")
    p.add_argument("--n", type=int, default=20, help="côté de la grille")
    p.add_argument("--algorithm", default=noms_gen[0], choices=noms_gen)
    p.add_argument("--seed", type=int, default=None, help="graine reproductible")
    p.add_argument("--output", default=None)
    p.add_argument("--image", action="store_true", help="produit aussi un PNG")
    p.add_argument("--cell-size", type=int, default=None)
    p.add_argument("--check", action="store_true", help="vérifie que le labyrinthe est parfait")
    p.set_defaults(func=cmd_generate)

    p = sub.add_parser("solve", help="résout un labyrinthe")
    p.add_argument("--n", type=int, default=20)
    p.add_argument("--algorithm", default=noms_sol[0], choices=noms_sol)
    p.add_argument("--algorithm-gen", default=noms_gen[0], choices=noms_gen,
                   help="générateur utilisé si aucun --input n'est donné")
    p.add_argument("--input", default=None, help="labyrinthe ASCII à relire")
    p.add_argument("--seed", type=int, default=None)
    p.add_argument("--output", default=None)
    p.add_argument("--image", action="store_true")
    p.add_argument("--cell-size", type=int, default=None)
    p.set_defaults(func=cmd_solve)

    p = sub.add_parser("convert", help="convertit un labyrinthe ASCII en image")
    p.add_argument("--input", required=True)
    p.add_argument("--output", required=True)
    p.add_argument("--cell-size", type=int, default=None)
    p.set_defaults(func=cmd_convert)

    return parser


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    try:
        return args.func(args)
    except (KeyError, ValueError, RuntimeError, FileNotFoundError) as err:
        print(f"Erreur : {err}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
