"""Solveur de Dijkstra (file de priorité), la référence « aveugle » face à A*.

Dijkstra trouve le plus court chemin dans un graphe **pondéré**. Ici tous les
couloirs coûtent 1 : la file de priorité sort donc les cellules dans l'ordre
exact d'un parcours en largeur, et le chemin obtenu est celui des autres
solveurs (il est unique dans un labyrinthe parfait). Le seul écart avec un BFS
est le **surcoût du tas** — c'est précisément ce que le benchmark mesure.

Autrement dit : à coût uniforme, la file de priorité est un FIFO déguisé. C'est
l'intérêt pédagogique de la comparaison, pas un défaut de l'algorithme. Dijkstra
ne devient réellement distinct d'un BFS que si les couloirs ont des coûts
différents, cas que cette grille n'expose pas.

Voir ``doc/04-solveurs.md``.
"""

from __future__ import annotations

from array import array
from heapq import heappop, heappush
from time import perf_counter
from typing import TYPE_CHECKING

from mazes.core.grid import DELTA_COL, DELTA_ROW, DIRECTIONS, EAST, SOUTH, WEST
from mazes.solvers.base import EXPLORED, Solver, SolveResult, register_solver

if TYPE_CHECKING:  # pragma: no cover
    from mazes.core.grid import WallGrid

#: Type des tableaux d'indices : 4 octets par élément, sans objet ``int`` par entrée.
_INDEX_TYPECODE = "i"

Cell = tuple[int, int]


@register_solver
class DijkstraSolver(Solver):
    """Plus court chemin par file de priorité (coût uniforme)."""

    name = "dijkstra"
    description = "Plus court chemin par file de priorité (coût uniforme)"
    complexity = "O(n^2 log n) temps, O(n^2) memoire"
    optimal = True

    def solve(self, grid: WallGrid, start: Cell, goal: Cell) -> SolveResult:
        """Résout par Dijkstra : tas ``heapq``, ``distances``/``parents`` en ``array("i")``.

        ``-1`` sert de sentinelle « non atteint » dans ``distances`` (``array("i")``
        ne stocke pas l'infini) : le test doit donc être
        ``ancienne < 0 or nouvelle < ancienne``. La suppression paresseuse
        ignore les entrées obsolètes du tas via ``closed``.

        Contrairement à A*, aucune heuristique n'oriente la recherche : les
        cellules sortent par distance croissante, ce qui reproduit exactement
        l'ordre d'un BFS puisque tous les couloirs coûtent 1.
        """
        self._require_endpoints(grid, start, goal)

        debut = perf_counter()
        n = grid.n
        total = n * n
        east = grid.east
        south = grid.south

        depart = start[0] * n + start[1]
        arrivee = goal[0] * n + goal[1]

        distances = array(_INDEX_TYPECODE, [-1]) * total
        parents = array(_INDEX_TYPECODE, [-1]) * total
        closed = bytearray(total)
        state = bytearray(total)

        distances[depart] = 0
        parents[depart] = depart  # le départ est son propre parent : arrête la remontée

        # (distance, index) : deux entiers, donc comparable sans départage explicite.
        tas = [(0, depart)]

        expanded = 0
        explored = 1
        max_frontier = 1

        while tas:
            distance, index = heappop(tas)

            if closed[index]:  # entrée obsolète (suppression paresseuse)
                continue

            closed[index] = 1
            state[index] = EXPLORED
            expanded += 1

            if index == arrivee:
                break

            r, c = divmod(index, n)
            nouvelle = distance + 1

            for d in DIRECTIONS:
                nr = r + DELTA_ROW[d]
                nc = c + DELTA_COL[d]
                if not (0 <= nr < n and 0 <= nc < n):
                    continue
                voisin = nr * n + nc
                if closed[voisin]:
                    continue

                # Le mur à lire dépend de la direction : Ouest -> mur Est du voisin,
                # Nord -> mur Sud du voisin.
                if d == EAST:
                    i = index
                    masque = east
                elif d == WEST:
                    i = voisin
                    masque = east
                elif d == SOUTH:
                    i = index
                    masque = south
                else:  # NORTH
                    i = voisin
                    masque = south
                if (masque[i >> 3] >> (i & 7)) & 1:
                    continue

                ancienne = distances[voisin]
                # `ancienne < 0` est indispensable : sans lui la première
                # amélioration d'une cellule non atteinte serait rejetée.
                if ancienne < 0 or nouvelle < ancienne:
                    if ancienne < 0:
                        explored += 1
                    distances[voisin] = nouvelle
                    parents[voisin] = index
                    heappush(tas, (nouvelle, voisin))

            if len(tas) > max_frontier:
                max_frontier = len(tas)

        chemin = self._reconstruct(parents, start, goal, n)
        self._mark_states(chemin, state, n)

        return SolveResult(
            path=chemin,
            state=state,
            expanded=expanded,
            explored=explored,
            max_frontier=max_frontier,
            elapsed_s=perf_counter() - debut,
            algorithm=self.name,
        )
