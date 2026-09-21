"""Tests des solveurs.

Ce que l'on verifie, et pourquoi
--------------------------------
Un solveur bugge ne plante pas. Il produit un chemin qui **a l'air** correct mais
qui traverse un mur. Ces tests verifient donc des **invariants** qui doivent tenir
pour toute taille et tout labyrinthe.

Le test central est :func:`TestReferenceBFS.test_meme_chemin_que_le_bfs`. Dans un
labyrinthe parfait le chemin est unique, donc tous les solveurs doivent renvoyer
exactement la meme liste de cellules que le parcours en largeur de reference. Une
divergence est forcement un bug.

Ce qu'on ne teste pas de facon exacte
-------------------------------------
Le nombre de cellules developpees par A* n'est pas previsible : il depend de
l'ordre de sortie des ex aequo dans le tas. On verifie donc des **bornes** et des
**relations**, jamais une valeur exacte -- sinon le test casserait au moindre
changement d'implementation sans rien garantir de plus.
"""

from __future__ import annotations

import pytest

from mazes.core.grid import WallGrid
from mazes.core.rng import RandomSource
from mazes.core.validation import solve_bruteforce, validate_path
from mazes.solvers.base import EXPLORED, ON_PATH
from tests.conftest import SIZES
from tests.fixtures import cul_de_sac, random_maze, snake


class TestValiditeDuChemin:
    """Le chemin renvoye est un chemin valide.

    Un seul appel a ``validate_path`` couvre toutes ces proprietes : la fonction
    verifie deja le depart, l'arrivee, les cellules hors grille, l'adjacence des
    etapes, l'absence de mur entre elles et l'absence de doublon. En cas
    d'echec elle renvoie le detail du probleme, ce qu'une assertion par
    propriete ne ferait pas mieux. Decouper ces verifications en autant de tests
    ne couvrirait donc rien de plus.
    """

    def test_ne_traverse_aucun_mur(self, solver, maze: WallGrid, endpoints) -> None:
        """Chaque etape emprunte un passage ouvert.

        C'est la verification la plus importante : un solveur qui traverse un mur
        peut sembler fonctionner sur un petit labyrinthe tout en etant faux.
        """
        start, goal = endpoints
        resultat = solver.solve(maze, start, goal)
        problemes = validate_path(maze, resultat.path, start, goal)
        assert problemes == [], problemes

    @pytest.mark.parametrize("n", SIZES)
    def test_toutes_les_tailles(self, solver, n: int, rng: RandomSource) -> None:
        """Le chemin reste valide de ``n = 1`` a ``n = 21``."""
        for grille in (snake(n), random_maze(n, rng)):
            start, goal = (0, 0), (n - 1, n - 1)
            resultat = solver.solve(grille, start, goal)
            assert validate_path(grille, resultat.path, start, goal) == []


class TestReferenceBFS:
    """Comparaison au parcours en largeur, dont la correction est etablie.

    Une seule comparaison suffit : en comparant la liste de cellules entiere, on
    fixe le chemin exact, donc sa longueur et sa forme. Verifier en plus des
    bornes de longueur (Manhattan, ``n²``) ne testerait rien de plus -- ce sont
    des consequences de l'egalite deja verifiee, pas des proprietes
    independantes.
    """

    def test_meme_chemin_que_le_bfs(self, solver, maze: WallGrid, endpoints) -> None:
        """Le chemin est identique, cellule pour cellule, a celui du BFS.

        Le test central. Il est rendu possible par l'unicite du chemin dans un
        labyrinthe parfait : sans elle, on ne pourrait comparer que les longueurs.
        """
        start, goal = endpoints
        attendu = solve_bruteforce(maze, start, goal)
        obtenu = solver.solve(maze, start, goal).path
        assert obtenu == attendu

class TestMasqueEtat:
    """Le masque qui pilote le rendu des ``o`` et des ``*``."""

    def test_taille_du_masque(self, solver, maze: WallGrid, endpoints) -> None:
        start, goal = endpoints
        resultat = solver.solve(maze, start, goal)
        assert len(resultat.state) == maze.n * maze.n

    def test_valeurs_valides(self, solver, maze: WallGrid, endpoints) -> None:
        """Aucune valeur hors de ``{0, 1, 2}``."""
        start, goal = endpoints
        resultat = solver.solve(maze, start, goal)
        assert set(resultat.state) <= {0, EXPLORED, ON_PATH}

    def test_les_cellules_du_chemin_sont_marquees(self, solver, maze: WallGrid, endpoints) -> None:
        """Chaque cellule du chemin porte ``ON_PATH`` -- donc sera rendue ``o``."""
        start, goal = endpoints
        resultat = solver.solve(maze, start, goal)
        n = maze.n
        for r, c in resultat.path:
            assert resultat.state[r * n + c] == ON_PATH

    def test_chemin_et_explore_sont_disjoints(self, solver, maze: WallGrid, endpoints) -> None:
        """Une cellule ne peut pas etre a la fois ``o`` et ``*``.

        Une cellule du chemin ne doit jamais etre presentee comme un cul-de-sac
        explore, meme si le solveur y est passe avant d'y revenir.
        """
        start, goal = endpoints
        resultat = solver.solve(maze, start, goal)
        n = maze.n
        for r, c in resultat.path:
            assert resultat.state[r * n + c] != EXPLORED

    def test_les_deux_marqueurs_apparaissent(self, solver) -> None:
        """Le masque contient des ``o`` **et** des ``*``.

        C'est l'exigence de l'enonce : le fichier doit montrer le parcours
        parcouru et les cases explorees qui n'en font pas partie.

        On utilise ``cul_de_sac``, un labyrinthe ou le demi-tour est **certain**.
        L'affirmer sur un labyrinthe quelconque serait faux : quand le chemin
        vers la sortie se trouve dans l'ordre d'examen des voisins, le solveur y
        va droit, ne recule jamais, et ne produit alors aucun ``*``. Mesure sur
        ce projet : environ une graine sur dix a ``n = 8``, et **jamais** sur un
        labyrinthe en couloir comme ``snake``.
        """
        grille = cul_de_sac()
        resultat = solver.solve(grille, (0, 0), (2, 2))
        assert ON_PATH in resultat.state, "le chemin doit apparaitre"
        assert EXPLORED in resultat.state, (
            "ce labyrinthe place une impasse avant la sortie : le solveur doit "
            "reculer et laisser au moins une case '*'"
        )

    def test_cellules_explorees_connectees(self, solver, maze: WallGrid, endpoints) -> None:
        """Les cellules atteintes forment un ensemble connexe contenant l'entree."""
        start, goal = endpoints
        resultat = solver.solve(maze, start, goal)
        n = maze.n
        atteintes = {i for i, v in enumerate(resultat.state) if v != 0}
        assert start[0] * n + start[1] in atteintes

        # parcours depuis l'entree, en ne passant que par des cases atteintes
        vus = {start[0] * n + start[1]}
        pile = [start[0] * n + start[1]]
        while pile:
            idx = pile.pop()
            r, c = divmod(idx, n)
            for d, (dr, dc) in enumerate(((-1, 0), (0, 1), (1, 0), (0, -1))):
                nr, nc = r + dr, c + dc
                if not (0 <= nr < n and 0 <= nc < n):
                    continue
                nidx = nr * n + nc
                if nidx not in atteintes or nidx in vus:
                    continue
                if not self._passage(maze, idx, d):
                    continue
                vus.add(nidx)
                pile.append(nidx)
        assert vus == atteintes

    @staticmethod
    def _passage(grid: WallGrid, idx: int, d: int) -> bool:
        """Indique si un passage ouvert relie ``idx`` au voisin dans la direction ``d``."""
        n, e, s = grid.n, grid.east, grid.south
        if d == 1:
            return not (e[idx >> 3] >> (idx & 7)) & 1
        if d == 2:
            return not (s[idx >> 3] >> (idx & 7)) & 1
        if d == 3:
            j = idx - 1
            return not (e[j >> 3] >> (j & 7)) & 1
        j = idx - n
        return not (s[j >> 3] >> (j & 7)) & 1


class TestMetriques:
    """Les chiffres que le benchmark utilisera."""

    def test_developpees_au_moins_la_longueur_du_chemin(
        self, solver, maze: WallGrid, endpoints
    ) -> None:
        start, goal = endpoints
        resultat = solver.solve(maze, start, goal)
        assert resultat.expanded >= len(resultat.path)

    def test_developpees_au_plus_le_nombre_de_cellules(
        self, solver, maze: WallGrid, endpoints
    ) -> None:
        start, goal = endpoints
        resultat = solver.solve(maze, start, goal)
        assert resultat.expanded <= maze.n * maze.n

    def test_efficacite_entre_zero_et_un(self, solver, maze: WallGrid, endpoints) -> None:
        start, goal = endpoints
        resultat = solver.solve(maze, start, goal)
        assert 0.0 <= resultat.efficiency <= 1.0

    def test_duree_positive(self, solver, maze: WallGrid, endpoints) -> None:
        start, goal = endpoints
        resultat = solver.solve(maze, start, goal)
        assert resultat.elapsed_s > 0.0

    def test_mesures_reproductibles(self, solver, maze: WallGrid, endpoints) -> None:
        """Deux executions sur le meme labyrinthe donnent le meme ``expanded``.

        Pour A*, cela verifie indirectement que le departage des ex aequo est
        deterministe : un ordre d'insertion non maitrise ferait varier la mesure
        d'un run a l'autre, et rendrait toute comparaison impossible.
        """
        start, goal = endpoints
        premier = solver.solve(maze, start, goal).expanded
        second = solver.solve(maze, start, goal).expanded
        assert premier == second


class TestCasLimites:
    """Cas particuliers, a traiter sans exception."""

    def test_labyrinthe_une_cellule(self, solver) -> None:
        """``n = 1`` : le depart est la sortie, le chemin a une seule cellule."""
        grille = snake(1)
        resultat = solver.solve(grille, (0, 0), (0, 0))
        assert resultat.path == [(0, 0)]

    def test_depart_egal_arrivee(self, solver, maze: WallGrid) -> None:
        resultat = solver.solve(maze, (3, 3), (3, 3))
        assert resultat.path == [(3, 3)]

    def test_entree_et_sortie_adjacentes(self, solver, rng: RandomSource) -> None:
        """Deux cellules voisines peuvent n'etre reliees que par un long detour.

        Le passage direct entre ``(0, 0)`` et ``(0, 1)`` est peut-etre ferme :
        dans un labyrinthe parfait, le chemin peut alors faire le tour du
        labyrinthe. On ne peut donc pas predire sa longueur -- seulement qu'il
        est unique, donc identique a celui du BFS.
        """
        grille = random_maze(8, rng)
        depart, arrivee = (0, 0), (0, 1)
        resultat = solver.solve(grille, depart, arrivee)
        assert validate_path(grille, resultat.path, depart, arrivee) == []
        assert resultat.path == solve_bruteforce(grille, depart, arrivee)
