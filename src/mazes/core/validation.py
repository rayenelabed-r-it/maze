"""Vérifications indépendantes des algorithmes : un labyrinthe est-il
parfait, quelle est la vraie distance minimale, un chemin est-il valide.

Sert de juge de paix : le BFS ici ne partage aucun code avec les solveurs,
donc il peut servir de référence pour les tester.
"""

from __future__ import annotations

from collections import deque

from mazes.core.grid import Cell, WallGrid


def bfs_distances(grid: WallGrid, start: Cell) -> dict[Cell, int]:
    """Distance en nombre de cellules depuis `start`, par parcours en largeur."""
    distances = {start: 0}
    file = deque([start])
    while file:
        cellule = file.popleft()
        d = distances[cellule] + 1
        for voisine in grid.accessible(cellule):
            if voisine not in distances:
                distances[voisine] = d
                file.append(voisine)
    return distances


def shortest_path(grid: WallGrid, start: Cell, goal: Cell) -> list[Cell]:
    """Chemin le plus court de référence (BFS). Liste vide si inatteignable."""
    if start == goal:
        return [start]
    predecesseurs: dict[Cell, Cell] = {start: start}
    file = deque([start])
    while file:
        cellule = file.popleft()
        for voisine in grid.accessible(cellule):
            if voisine in predecesseurs:
                continue
            predecesseurs[voisine] = cellule
            if voisine == goal:
                return _remonter(predecesseurs, start, goal)
            file.append(voisine)
    return []


def _remonter(predecesseurs: dict[Cell, Cell], start: Cell, goal: Cell) -> list[Cell]:
    chemin = [goal]
    while chemin[-1] != start:
        chemin.append(predecesseurs[chemin[-1]])
    chemin.reverse()
    return chemin


def is_connected(grid: WallGrid) -> bool:
    return len(bfs_distances(grid, (0, 0))) == grid.n * grid.n


def is_perfect(grid: WallGrid) -> bool:
    """Un labyrinthe est parfait s'il est connexe et sans cycle.

    Un graphe connexe à n² sommets est un arbre si et seulement s'il a
    exactement n² - 1 arêtes : inutile de chercher les cycles à la main.
    """
    return grid.count_passages() == grid.n * grid.n - 1 and is_connected(grid)


def validate_path(grid: WallGrid, path: list[Cell], start: Cell, goal: Cell) -> None:
    """Lève ValueError si le chemin n'est pas praticable. Ne renvoie rien."""
    if not path:
        raise ValueError("chemin vide")
    if path[0] != start or path[-1] != goal:
        raise ValueError(
            f"le chemin va de {path[0]} à {path[-1]}, attendu {start} -> {goal}"
        )
    vues = set()
    for cellule in path:
        if not grid.in_bounds(cellule):
            raise ValueError(f"cellule hors grille : {cellule}")
        if cellule in vues:
            raise ValueError(f"le chemin repasse par {cellule}")
        vues.add(cellule)
    for a, b in zip(path, path[1:]):
        if not grid.is_open(a, b):
            raise ValueError(f"mur entre {a} et {b} : le chemin traverse un mur")
