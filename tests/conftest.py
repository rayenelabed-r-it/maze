"""Fixtures partagees par les tests des solveurs.

Strategie
---------
Un solveur bugge ne plante pas. Il produit un chemin qui **a l'air** correct mais
qui traverse un mur, ou qui saute une cellule. Sans verification, on ne le voit
jamais.

On teste donc des **invariants** plutot qu'un resultat attendu :

1. le chemin part de l'entree et arrive a la sortie ;
2. il ne traverse aucun mur et ne saute aucune cellule ;
3. il est **identique** a celui d'un parcours en largeur de reference ;
4. le masque d'etat est coherent (les `o` forment le chemin, les `*` le reste).

Le point 3 est le plus fort : dans un labyrinthe parfait, le chemin est unique,
donc tous les solveurs doivent renvoyer exactement la meme liste de cellules.

Reproductibilite
----------------
Les tailles restent petites (1 a 21) : c'est la que les cas limites se
manifestent, et le rendu ASCII y est lisible a l'oeil. Les mesures de performance
sont le role des benchmarks, pas des tests.
"""

from __future__ import annotations

import pytest

from mazes.core.grid import WallGrid
from mazes.core.rng import RandomSource
from mazes.solvers import get_solver, solver_choices
from tests.fixtures import random_maze, snake

#: Graine fixe. Un test qui echoue doit echouer de la meme facon a chaque fois.
TEST_SEED = 12345

#: Tailles des tests. 1 est un cas limite a part entiere.
SIZES = (1, 2, 3, 4, 5, 8, 13, 21)


@pytest.fixture
def rng() -> RandomSource:
    """Source aleatoire reproductible, reinitialisee a chaque test."""
    return RandomSource(TEST_SEED)


@pytest.fixture(params=solver_choices())
def solver_name(request: pytest.FixtureRequest) -> str:
    """Parametre chaque test sur tous les solveurs enregistres.

    Ajouter un solveur au registre l'inclut automatiquement dans toute la suite.
    """
    return request.param


@pytest.fixture
def solver(solver_name: str):
    """Instance du solveur courant."""
    return get_solver(solver_name)


@pytest.fixture(params=("snake", "random"))
def maze(request: pytest.FixtureRequest, rng: RandomSource) -> WallGrid:
    """Labyrinthe de reference ``13 x 13``, en deux variantes.

    ``snake`` a un chemin maximal (le pire cas pour un solveur), ``random`` est
    representatif d'un vrai labyrinthe. Tester les deux evite de valider un
    solveur sur un seul type de labyrinthe.
    """
    if request.param == "snake":
        return snake(13)
    return random_maze(13, rng)


@pytest.fixture
def endpoints(maze: WallGrid) -> tuple[tuple[int, int], tuple[int, int]]:
    """Entree et sortie : ``(0, 0)`` et ``(n-1, n-1)``."""
    return (0, 0), (maze.n - 1, maze.n - 1)
