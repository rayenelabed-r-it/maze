import pytest

from mazes.core.grid import WallGrid


def test_murs_fermes_au_depart():
    grid = WallGrid(4)
    assert grid.count_passages() == 0
    assert grid.accessible((0, 0)) == []


def test_carve_est_symetrique():
    grid = WallGrid(3)
    grid.carve((0, 0), (0, 1))
    assert grid.is_open((0, 1), (0, 0))
    assert (0, 1) in grid.accessible((0, 0))
    assert (0, 0) in grid.accessible((0, 1))


def test_cellules_non_adjacentes():
    grid = WallGrid(3)
    with pytest.raises(ValueError):
        grid.carve((0, 0), (1, 1))
    with pytest.raises(ValueError):
        grid.carve((0, 0), (0, 5))


def test_from_passages():
    grid = WallGrid.from_passages(2, [((0, 0), (0, 1)), ((0, 1), (1, 1))])
    assert grid.count_passages() == 2
    assert not grid.is_open((0, 0), (1, 0))
