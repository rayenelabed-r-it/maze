"""Tableau comparatif : temps, mémoire et efficacité des solveurs
en fonction de la taille du labyrinthe.

  python benchmarks/scaling.py --sizes 100 500 1000 --repeat 3
"""

from __future__ import annotations

import argparse
import csv
import sys
from pathlib import Path

from mazes.core.rng import RandomSource
from mazes.core.validation import shortest_path, validate_path
from mazes.generators import available_generators, get_generator
from mazes.metrics import measure
from mazes.solvers import available_solvers, get_solver

COLONNES = [
    "n", "generateur", "solveur", "temps_ms", "pic_kio",
    "longueur", "optimal", "developpees", "atteintes", "pic_frontiere",
]


def mesurer(n: int, nom_gen: str, nom_sol: str, seed: int, repeat: int) -> dict:
    rng = RandomSource(seed)
    grille = get_generator(nom_gen).generate(n, rng)
    solveur = get_solver(nom_sol)
    start, goal = grille.entry, grille.goal

    reference = len(shortest_path(grille, start, goal))

    meilleur = None
    mesure = None
    for _ in range(repeat):
        mesure = measure(lambda: solveur.solve(grille, start, goal))
        resultat = mesure.result
        if meilleur is None or resultat.elapsed_s < meilleur.elapsed_s:
            meilleur = resultat

    validate_path(grille, meilleur.path, start, goal)

    return {
        "n": n,
        "generateur": nom_gen,
        "solveur": nom_sol,
        "temps_ms": round(meilleur.elapsed_s * 1000, 2),
        "pic_kio": round(mesure.peak_kib, 1),
        "longueur": meilleur.length,
        "optimal": "oui" if meilleur.length == reference else "non",
        "developpees": meilleur.expanded,
        "atteintes": meilleur.explored,
        "pic_frontiere": meilleur.max_frontier,
    }


def afficher(lignes: list[dict]) -> None:
    largeurs = {c: max(len(c), *(len(str(l[c])) for l in lignes)) for c in COLONNES}
    entete = "  ".join(c.ljust(largeurs[c]) for c in COLONNES)
    print(entete)
    print("-" * len(entete))
    for ligne in lignes:
        print("  ".join(str(ligne[c]).ljust(largeurs[c]) for c in COLONNES))


def main(argv: list[str] | None = None) -> int:
    noms_gen = [c.name for c in available_generators()]
    noms_sol = [c.name for c in available_solvers()]

    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--sizes", type=int, nargs="+", default=[50, 100, 200])
    parser.add_argument("--generators", nargs="+", default=noms_gen, choices=noms_gen)
    parser.add_argument("--solvers", nargs="+", default=noms_sol, choices=noms_sol)
    parser.add_argument("--seed", type=int, default=1234)
    parser.add_argument("--repeat", type=int, default=1, help="on garde le meilleur temps")
    parser.add_argument("--csv", default=None, help="fichier CSV de sortie")
    args = parser.parse_args(argv)

    lignes = []
    for n in args.sizes:
        for nom_gen in args.generators:
            for nom_sol in args.solvers:
                print(f"... n={n} {nom_gen}/{nom_sol}", file=sys.stderr)
                lignes.append(mesurer(n, nom_gen, nom_sol, args.seed, args.repeat))

    afficher(lignes)

    if args.csv:
        chemin = Path(args.csv)
        chemin.parent.mkdir(parents=True, exist_ok=True)
        with chemin.open("w", newline="", encoding="utf-8") as f:
            writer = csv.DictWriter(f, fieldnames=COLONNES)
            writer.writeheader()
            writer.writerows(lignes)
        print(f"CSV écrit dans {chemin}", file=sys.stderr)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
