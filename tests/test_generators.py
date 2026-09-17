import pytest

from mazes.core.rng import RandomSource
from mazes.core.validation import is_perfect
from mazes.generators import available_generators, get_generator


@pytest.mark.parametrize("cls", available_generators(), ids=lambda c: c.name)
@pytest.mark.parametrize("n", [1, 2, 5, 25])
def test_labyrinthe_parfait(cls, n):
    grid = cls().generate(n, RandomSource(7))
    assert grid.n == n
    assert is_perfect(grid)


@pytest.mark.parametrize("cls", available_generators(), ids=lambda c: c.name)
def test_reproductible(cls):
    a = cls().generate(12, RandomSource(42))
    b = cls().generate(12, RandomSource(42))
    assert a == b


def test_nom_inconnu_liste_les_valides():
    with pytest.raises(KeyError) as err:
        get_generator("nimportequoi")
    assert "kruskal" in str(err.value)
