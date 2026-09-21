"""Tests des générateurs.

Ce qu'on vérifie, et pourquoi
-----------------------------
Un générateur doit produire un **labyrinthe parfait**, c'est-à-dire un arbre
couvrant : la grille est entièrement connectée et ne contient aucun cycle. De
cette propriété découle tout le reste du projet — le chemin entre deux cellules
est unique, donc les solveurs doivent tous renvoyer le même, et les tests de
solveurs peuvent se comparer à un BFS de référence.

Un générateur qui produit un cycle reste « utilisable » : il génère un
labyrinthe, il se dessine, il se résout. C'est ce qui rend l'erreur invisible
sans test dédié.

Le test le plus rentable
------------------------
:func:`TestLabyrintheParfait.test_nombre_de_passages` : exactement ``n² - 1``
passages ouverts, ni plus ni moins. C'est la formulation la plus stricte de
« parfait » — le comptage attrape d'un coup le cycle (trop de passages) et
l'îlot isolé (pas assez), là où un simple test de connexité n'en verrait qu'un.

Les tests portent sur le **registre**, pas sur chaque classe : ils sont
paramétrés par :func:`~mazes.generators.generator_choices`, donc ajouter un
générateur l'inclut automatiquement dans toute la suite.
"""

from __future__ import annotations

import pytest

from mazes.core.rng import RandomSource
from mazes.core.validation import count_open_passages, is_perfect
from mazes.generators import generator_choices, get_generator
from tests.conftest import SIZES
from tests.fixtures import cul_de_sac, random_maze, snake

GENERATEURS = generator_choices()


class TestLabyrintheParfait:
    """L'invariant central : la grille engendrée est un arbre couvrant."""

    @pytest.mark.parametrize("nom", GENERATEURS)
    @pytest.mark.parametrize("n", SIZES)
    def test_parfait_a_toutes_les_tailles(self, nom: str, n: int, rng: RandomSource) -> None:
        """Connecté et sans cycle, de ``n = 1`` à ``n = 21``.

        ``n = 1`` est un cas limite à part entière : la grille n'a aucune
        cellule voisine, donc aucun passage à percer. Un générateur qui suppose
        ``n >= 2`` s'y casse.
        """
        grille = get_generator(nom).generate(n, rng)
        assert is_perfect(grille), f"{nom} produit un labyrinthe imparfait en n={n}"

    @pytest.mark.parametrize("nom", GENERATEURS)
    def test_nombre_de_passages(self, nom: str, rng: RandomSource) -> None:
        """Exactement ``n² - 1`` passages ouverts.

        Un arbre couvrant a ``n² - 1`` arêtes : pas une de plus (sinon un
        cycle), pas une de moins (sinon un îlot injoignable).
        """
        for n in (1, 2, 5, 13):
            grille = get_generator(nom).generate(n, rng)
            assert count_open_passages(grille) == n * n - 1, f"{nom} en n={n}"

    @pytest.mark.parametrize("nom", GENERATEURS)
    def test_entree_et_sortie_ouvertes(self, nom: str, rng: RandomSource) -> None:
        """Les ouvertures d'entrée et de sortie sont percées, même en ``n = 1``."""
        grille = get_generator(nom).generate(5, rng)
        assert grille.entry_open
        assert grille.exit_open


class TestReproductibilite:
    """Une graine fixe doit donner le même labyrinthe, sinon rien n'est comparable."""

    @pytest.mark.parametrize("nom", GENERATEURS)
    def test_meme_graine_meme_labyrinthe(self, nom: str) -> None:
        a = get_generator(nom).generate(13, RandomSource(7))
        b = get_generator(nom).generate(13, RandomSource(7))
        assert a == b

    @pytest.mark.parametrize("nom", GENERATEURS)
    def test_graines_differentes_labyrinthes_differents(self, nom: str) -> None:
        """La graine pilote vraiment le tirage, elle n'est pas ignorée.

        Un générateur purement déterministe passerait le test précédent sans
        rien mélanger : celui-ci vérifie que l'aléatoire dépend bien de la
        graine.
        """
        a = get_generator(nom).generate(13, RandomSource(1))
        b = get_generator(nom).generate(13, RandomSource(2))
        assert a != b


class TestRegistre:
    """Le registre est peuplé à l'import, et échoue proprement sinon."""

    def test_generateurs_attendus(self) -> None:
        assert set(GENERATEURS) == {"kruskal", "prim", "recursive_backtracking"}

    def test_nom_inconnu(self) -> None:
        with pytest.raises(KeyError):
            get_generator("inconnu")


class TestFixtures:
    """Les labyrinthes de référence doivent eux-mêmes être corrects.

    :func:`~tests.fixtures.snake`, :func:`~tests.fixtures.cul_de_sac` et
    :func:`~tests.fixtures.random_maze` servent de socle à toute la suite : s'ils
    produisaient un labyrinthe imparfait, les tests de solveurs passeraient ou
    échoueraient pour de mauvaises raisons — un test faux est pire qu'un test
    absent.
    """

    @pytest.mark.parametrize("n", (1, 2, 3, 5, 8, 21))
    def test_snake_est_parfait(self, n: int) -> None:
        """``snake`` est le pire cas des solveurs : il doit être valide."""
        grille = snake(n)
        assert is_perfect(grille)
        assert count_open_passages(grille) == n * n - 1

    @pytest.mark.parametrize("n", (1, 2, 5, 13))
    def test_random_maze_est_parfait(self, n: int, rng: RandomSource) -> None:
        assert is_perfect(random_maze(n, rng))

    def test_cul_de_sac_est_parfait(self) -> None:
        """Le labyrinthe à impasse garantie reste un vrai labyrinthe."""
        assert is_perfect(cul_de_sac())

    def test_snake_refuse_n_invalide(self) -> None:
        """``n = 0`` n'a pas de sens : erreur explicite plutôt qu'une grille vide."""
        with pytest.raises(ValueError):
            snake(0)
