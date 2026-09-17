import pytest

from mazes.core.rng import RandomSource
from mazes.generators import get_generator
from mazes.rendering.ascii import from_ascii, to_ascii
from mazes.solvers import get_solver


@pytest.fixture(scope="module")
def grille():
    return get_generator("prim").generate(15, RandomSource(11))


def test_dimensions(grille):
    lignes = to_ascii(grille).splitlines()
    assert len(lignes) == 2 * grille.n + 1
    assert all(len(l) == 2 * grille.n + 1 for l in lignes)


def test_aller_retour_texte(grille):
    assert from_ascii(to_ascii(grille)) == grille


def test_marques_du_solveur(grille):
    resultat = get_solver("astar").solve(grille, grille.entry, grille.goal)
    texte = to_ascii(grille, resultat.state)
    assert "o" in texte
    # les marques ne changent pas les murs : relecture identique
    assert from_ascii(texte) == grille


def test_entree_vide():
    with pytest.raises(ValueError):
        from_ascii("")
