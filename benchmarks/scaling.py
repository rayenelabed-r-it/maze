"""Compare les solveurs sur les labyrinthes déjà générés dans ``outputs/``.

Usage :
    1. Générer des labyrinthes :  ``mazes generate --n 100 --algorithm kruskal``
    2. Lancer l'analyse :         ``python benchmarks/scaling.py``
    3. Lire le compte rendu :     ``outputs/benchmark.md``

Chaque labyrinthe trouvé dans ``outputs/`` (fichier ``.txt``) est résolu par
chaque solveur ; les métriques sont comparées, et le compte rendu est écrit en
Markdown dans ``outputs/benchmark.md``.
"""

from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))

from mazes.core.grid import entry_cell, exit_cell
from mazes.core.validation import validate_path
from mazes.rendering import read_ascii
from mazes.solvers import get_solver, solver_choices

OUTPUTS = Path(__file__).resolve().parent.parent / "outputs"


def charger_mazes() -> list[Path]:
    """Renvoie les labyrinthes ASCII de ``outputs/``, triés par nom."""
    return sorted(OUTPUTS.glob("*.txt"))


def analyser(chemin: Path) -> dict:
    """Résout un labyrinthe avec chaque solveur et renvoie ses métriques."""
    grille = read_ascii(chemin)
    start, goal = entry_cell(grille), exit_cell(grille)

    resultats = []
    for nom in solver_choices():
        resultat = get_solver(nom).solve(grille, start, goal)
        problemes = validate_path(grille, resultat.path, start, goal)
        resultats.append(
            {
                "solveur": nom,
                "temps_ms": resultat.elapsed_s * 1000,
                "developpees": resultat.expanded,
                "frontiere": resultat.max_frontier,
                "chemin": resultat.path_length,
                "efficacite": resultat.efficiency,
                "valide": not problemes,
            }
        )
    return {"fichier": chemin.name, "n": grille.n, "resultats": resultats}


def _verdict(analyse: dict) -> str:
    """Résume, pour un labyrinthe, quel solveur gagne sur quel critère."""
    res = analyse["resultats"]
    rapide = min(res, key=lambda r: r["temps_ms"])
    efficace = min(res, key=lambda r: r["developpees"])
    leger = min(res, key=lambda r: r["frontiere"])
    return (
        f"- Plus rapide : **{rapide['solveur']}** ({rapide['temps_ms']:.2f} ms)\n"
        f"- Plus efficace : **{efficace['solveur']}** "
        f"({efficace['developpees']:,} cases développées)\n"
        f"- Plus léger : **{leger['solveur']}** (frontière {leger['frontiere']:,})"
    )


def rendre_markdown(analyses: list[dict]) -> str:
    """Construit le compte rendu Markdown."""
    lignes = ["# Benchmark des solveurs", ""]
    lignes.append(
        f"{len(analyses)} labyrinthe(s) analysé(s) avec {len(solver_choices())} "
        f"solveur(s) : {', '.join(solver_choices())}."
    )
    lignes.append("")

    for analyse in analyses:
        lignes.append(f"## {analyse['fichier']}  ({analyse['n']} x {analyse['n']})")
        lignes.append("")
        lignes.append(
            "| Solveur | Temps (ms) | Cases développées | Frontière | Chemin | Efficacité |"
        )
        lignes.append("|---|---:|---:|---:|---:|---:|")
        for r in analyse["resultats"]:
            marque = " ✅" if r["valide"] else " ❌"
            lignes.append(
                f"| {r['solveur']}{marque} | {r['temps_ms']:.2f} | {r['developpees']:,} "
                f"| {r['frontiere']:,} | {r['chemin']:,} | {r['efficacite']:.3f} |"
            )
        lignes.append("")
        lignes.append(_verdict(analyse))
        lignes.append("")

    # Bilan : qui gagne le plus souvent, tous labyrinthes confondus.
    victoires = {nom: {"rapide": 0, "efficace": 0, "leger": 0} for nom in solver_choices()}
    for analyse in analyses:
        res = analyse["resultats"]
        victoires[min(res, key=lambda r: r["temps_ms"])["solveur"]]["rapide"] += 1
        victoires[min(res, key=lambda r: r["developpees"])["solveur"]]["efficace"] += 1
        victoires[min(res, key=lambda r: r["frontiere"])["solveur"]]["leger"] += 1

    lignes.append("## Bilan")
    lignes.append("")
    lignes.append("| Solveur | Victoires « rapide » | Victoires « efficace » | Victoires « léger » |")
    lignes.append("|---|---:|---:|---:|")
    for nom in solver_choices():
        v = victoires[nom]
        lignes.append(f"| {nom} | {v['rapide']} | {v['efficace']} | {v['leger']} |")
    lignes.append("")

    return "\n".join(lignes) + "\n"


def main(argv: list[str] | None = None) -> int:
    chemins = charger_mazes()
    if not chemins:
        print(
            "Aucun labyrinthe dans outputs/. Générez-en d'abord : "
            "mazes generate --n 100 --algorithm kruskal",
            file=sys.stderr,
        )
        return 1

    analyses = [analyser(c) for c in chemins]
    sortie = OUTPUTS / "benchmark.md"
    sortie.write_text(rendre_markdown(analyses), encoding="utf-8")
    print(f"Compte rendu écrit dans {sortie}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
