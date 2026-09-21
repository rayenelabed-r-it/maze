"""Tests de la conversion en image JPG.

Couvre la chaîne complète : développement dense, sous-échantillonnage, conversion
Pillow et écriture JPG. Le chemin par bandes est vérifié en le forçant (budget
mémoire réduit) et en comparant au chemin direct, octet pour octet.
"""

from __future__ import annotations

from pathlib import Path

import numpy as np
import pytest
from PIL import Image

import mazes.rendering.image as image_mod
from mazes.core.grid import DENSE_EXPLORED, DENSE_FREE, DENSE_PATH, DENSE_WALL
from mazes.core.rng import RandomSource
from mazes.rendering import (
    DEFAULT_STYLE,
    ImageStyle,
    choose_format,
    render_dense,
    render_dense_banded,
    subsample_dense,
    to_image,
    write_image,
)
from mazes.solvers import get_solver
from tests.fixtures import random_maze, snake

SIZES = (1, 2, 3, 5, 8, 13)


def _state(grid) -> bytearray:
    """Masque d'état d'une résolution A*, pour superposer un parcours."""
    n = grid.n
    return get_solver("astar").solve(grid, (0, 0), (n - 1, n - 1)).state


class TestDense:
    def test_forme(self) -> None:
        assert render_dense(snake(3)).shape == (7, 7)
        assert render_dense(snake(1)).shape == (3, 3)

    def test_valeurs_autorisees(self) -> None:
        dense = render_dense(snake(8), _state(snake(8)))
        assert set(np.unique(dense)) <= {DENSE_WALL, DENSE_FREE, DENSE_PATH, DENSE_EXPLORED}

    def test_entree_et_sortie_ouvertes(self) -> None:
        dense = render_dense(snake(4))
        assert dense[0, 1] == DENSE_FREE  # entrée
        assert dense[-1, -2] == DENSE_FREE  # sortie
        assert dense[0, 0] == DENSE_WALL  # coin

    @pytest.mark.parametrize("n", SIZES)
    def test_dense_egal_banded(self, n: int) -> None:
        """Le chemin par bandes produit exactement la même image que le chemin direct.

        Vérifié avec et sans masque d'état : c'est la superposition des ``o`` et
        des ``*`` qui exerce la logique de bornes entre bandes. Les deux cas
        portent sur les mêmes grilles, d'où un seul test plutôt que deux.
        """
        for grid in (snake(n), random_maze(n, RandomSource(n))):
            assert np.array_equal(render_dense(grid), render_dense_banded(grid))
            state = _state(grid)
            assert np.array_equal(render_dense(grid, state), render_dense_banded(grid, state))


class TestSubsample:
    def test_facteur_1_est_identite(self) -> None:
        dense = render_dense(snake(5))
        assert subsample_dense(dense, 1) is dense

    def test_reduit_les_dimensions(self) -> None:
        dense = render_dense(snake(10))  # 21 x 21
        assert subsample_dense(dense, 3).shape == (7, 7)

    def test_minimum_conserve_les_passages(self) -> None:
        bloc = np.array([[DENSE_WALL, DENSE_WALL], [DENSE_WALL, DENSE_FREE]], dtype=np.uint8)
        assert subsample_dense(bloc, 2, preserve_path=False)[0, 0] == DENSE_FREE

    def test_preserve_chemin(self) -> None:
        grid = snake(6)
        dense = render_dense(grid, _state(grid))
        reduit = subsample_dense(dense, 4)
        assert DENSE_PATH in np.unique(reduit)

    def test_facteur_trop_grand(self) -> None:
        with pytest.raises(ValueError):
            subsample_dense(np.zeros((3, 3), dtype=np.uint8), 5)


class TestToImage:
    def test_mode_couleur(self) -> None:
        image = to_image(render_dense(snake(3)))
        assert image.mode == "RGB"

    def test_taille(self) -> None:
        assert to_image(render_dense(snake(4))).size == (9, 9)


class TestWriteImage:
    def test_ecrit_un_jpeg_valide(self, tmp_path: Path) -> None:
        """Un JPEG non vide, en couleur, avec un masque d'état superposé."""
        grid = snake(6)
        chemin = write_image(grid, tmp_path / "maze.jpg", state=_state(grid))
        assert chemin.exists()
        assert chemin.stat().st_size > 0
        assert Image.open(chemin).mode == "RGB"

    def test_cree_les_repertoires(self, tmp_path: Path) -> None:
        chemin = write_image(snake(4), tmp_path / "sous" / "dossier" / "m.jpg")
        assert chemin.exists()

    def test_chemin_par_bandes(self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
        """Forcé en chemin par bandes, l'image JPEG est écrite avec la bonne taille."""
        grid = random_maze(10, RandomSource(7))
        state = _state(grid)

        monkeypatch.setattr(image_mod, "DENSE_MEMORY_BUDGET", 0)
        chemin = write_image(grid, tmp_path / "bandes.jpg", state=state)

        image = Image.open(chemin)
        assert image.mode == "RGB"
        assert image.size == (21, 21)  # 2 * 10 + 1

    def test_scale_reduit(self, tmp_path: Path) -> None:
        grid = snake(12)  # dense 25 x 25
        chemin = write_image(grid, tmp_path / "petit.jpg", scale=5)
        assert Image.open(chemin).size == (5, 5)

    def test_scale_invalide(self, tmp_path: Path) -> None:
        with pytest.raises(ValueError):
            write_image(snake(4), tmp_path / "x.jpg", scale=0)


class TestChooseFormat:
    def test_extensions_reconnues(self) -> None:
        assert choose_format("maze.jpg") == "JPEG"
        assert choose_format("maze.JPEG") == "JPEG"

    def test_extension_inconnue(self) -> None:
        for nom in ("maze.png", "maze.gif"):
            with pytest.raises(ValueError):
                choose_format(nom)


class TestImageStyle:
    def test_palette_couleur(self) -> None:
        palette = DEFAULT_STYLE.build_palette()
        assert palette.shape == (256, 3)
        assert palette[DENSE_WALL].tolist() == [0, 0, 0]
        assert palette[DENSE_FREE].tolist() == [255, 255, 255]
        assert palette[DENSE_PATH].tolist() == [220, 20, 60]

    def test_entier_devient_gris(self) -> None:
        palette = ImageStyle(path=200).build_palette()
        assert palette[DENSE_PATH].tolist() == [200, 200, 200]

    @pytest.mark.parametrize("couleur", [256, -1, (1, 2), (1, 2, 3, 4)])
    def test_couleur_invalide(self, couleur) -> None:
        with pytest.raises(ValueError):
            ImageStyle(wall=couleur).build_palette()
