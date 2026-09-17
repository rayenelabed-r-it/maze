import pytest

from mazes.core.rng import RandomSource
from mazes.core.validation import shortest_path, validate_path
from mazes.generators import get_generator
from mazes.solvers import available_solvers, get_solver
from mazes.solvers.base import PATH


@pytest.fixture(scope="module")
def grille():
    return get_generator("kruskal").generate(30, RandomSource(3))


@pytest.mark.parametrize("cls", available_solvers(), ids=lambda c: c.name)
def test_chemin_valide(cls, grille):
    start, goal = grille.entry, grille.goal
    resultat = cls().solve(grille, start, goal)
    validate_path(grille, resultat.path, start, goal)


@pytest.mark.parametrize("cls", available_solvers(), ids=lambda c: c.name)
def test_longueur_egale_au_bfs(cls, grille):
    # Dans un labyrinthe parfait, le chemin simple est unique : tous les
    # solveurs corrects doivent trouver la même longueur que le BFS.
    attendu = len(shortest_path(grille, grille.entry, grille.goal))
    resultat = cls().solve(grille, grille.entry, grille.goal)
    assert resultat.length == attendu


@pytest.mark.parametrize("cls", available_solvers(), ids=lambda c: c.name)
def test_state_marque_le_chemin(cls, grille):
    resultat = cls().solve(grille, grille.entry, grille.goal)
    assert len(resultat.state) == grille.n * grille.n
    for cellule in resultat.path:
        assert resultat.state[grille.index(cellule)] == PATH


def test_solveur_inconnu():
    with pytest.raises(KeyError):
        get_solver("bfs_magique")
