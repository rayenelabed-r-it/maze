"""Tests du budget mémoire des algorithmes.

Ce qu'on vérifie, et pourquoi
-----------------------------
Le budget décide si un calcul est lancé, avant toute allocation. Un modèle qui
sous-estime ne produit pas une erreur : il laisse le processus mourir en
``MemoryError``, sans message et sans rien avoir produit.
:class:`TestLeModeleMajoreLaMesure` compare donc chaque prédiction à un pic
réellement mesuré par ``tracemalloc``. Un modèle écrit à la main peut dériver de
l'algorithme qu'il décrit : si ``kruskal.py`` changeait de structure de données,
la prédiction resterait plausible et fausse, et ce test-là échouerait.

:class:`TestPasDeCollision` couvre ``recursive_backtracking``, qui figure dans
le registre des générateurs comme dans celui des solveurs, avec deux empreintes
qui n'ont rien à voir.
"""

from __future__ import annotations

import gc
import tracemalloc

import pytest

from mazes.budget import (
    BUDGET_ENV_VAR,
    MEMORY_BUDGET,
    estimate_generation,
    estimate_solving,
    fits_generation,
    fits_solving,
    memory_budget,
)
from mazes.core.rng import RandomSource
from mazes.generators import generator_choices, get_generator
from mazes.solvers import get_solver, solver_choices

SEED = 12345


def _pic_generation(generateur: str, n: int) -> int:
    """Pic mémoire réel d'une génération, en octets."""
    gc.collect()
    tracemalloc.start()
    try:
        grille = get_generator(generateur).generate(n, RandomSource(SEED))
        _, pic = tracemalloc.get_traced_memory()
    finally:
        tracemalloc.stop()
    del grille
    gc.collect()
    return pic


def _pic_resolution(solveur: str, n: int) -> int:
    """Pic mémoire réel d'une résolution, grille exclue de la mesure."""
    grille = get_generator("prim").generate(n, RandomSource(SEED))
    gc.collect()
    tracemalloc.start()
    try:
        get_solver(solveur).solve(grille, (0, 0), (n - 1, n - 1))
        _, pic = tracemalloc.get_traced_memory()
    finally:
        tracemalloc.stop()
    del grille
    gc.collect()
    return pic


class TestEstimateGeneration:
    """Les modèles des générateurs."""

    @pytest.mark.parametrize("generateur", ["kruskal", "prim", "recursive_backtracking"])
    def test_croit_avec_n(self, generateur: str) -> None:
        assert estimate_generation(generateur, 200) < estimate_generation(generateur, 1000)

    def test_kruskal_est_le_plus_gourmand(self) -> None:
        """Kruskal demande ~40 fois ce que demande Prim a ``n = 1000``.

        C'est ce qui justifie un modele par algorithme plutot qu'un plafond
        commun : un plafond unique refuserait au nom du pire, ou laisserait
        passer le pire au nom du meilleur.
        """
        n = 1000
        assert estimate_generation("kruskal", n) > 20 * estimate_generation("prim", n)

    @pytest.mark.parametrize(
        ("generateur", "attendu"),
        [
            ("kruskal", 230 * 100 * 100),
            ("recursive_backtracking", 30 * 100 * 100),
        ],
    )
    def test_formule_quadratique(self, generateur: str, attendu: int) -> None:
        assert estimate_generation(generateur, 100) == attendu

    def test_prim_ajoute_un_terme_lineaire(self) -> None:
        """La frontiere de Prim est en ``O(n)`` : elle ne doit pas etre oubliee."""
        assert estimate_generation("prim", 100) == int(2.5 * 100 * 100 + 3000 * 100)

    def test_generateur_inconnu(self) -> None:
        """Mieux vaut un echec explicite qu'une estimation silencieusement fausse."""
        with pytest.raises(ValueError):
            estimate_generation("inconnu", 100)


class TestEstimateSolving:
    """Les modèles des solveurs."""

    @pytest.mark.parametrize("solveur", ["astar", "dijkstra", "recursive_backtracking"])
    def test_croit_avec_n(self, solveur: str) -> None:
        assert estimate_solving(solveur, 200) < estimate_solving(solveur, 1000)

    def test_astar_et_dijkstra_se_valent(self) -> None:
        """Memes structures : deux tableaux ``int32`` et deux ``bytearray``."""
        assert estimate_solving("astar", 1000) == estimate_solving("dijkstra", 1000)

    def test_le_backtracking_est_bien_plus_sobre(self) -> None:
        """Il ne garde qu'un ``bytearray`` d'etat et une pile courte."""
        n = 1000
        assert estimate_solving("recursive_backtracking", n) * 4 < estimate_solving("astar", n)

    def test_solveur_inconnu(self) -> None:
        with pytest.raises(ValueError):
            estimate_solving("inconnu", 100)


class TestPasDeCollision:
    """``recursive_backtracking`` est des deux cotes, avec deux modeles distincts."""

    def test_meme_nom_deux_empreintes(self) -> None:
        """Une table unique aurait ecrase l'un des deux modeles."""
        n = 1000
        assert estimate_generation("recursive_backtracking", n) != estimate_solving(
            "recursive_backtracking", n
        )

    def test_les_deux_modeles_sont_presents(self) -> None:
        for nom in generator_choices():
            assert estimate_generation(nom, 10) > 0
        for nom in solver_choices():
            assert estimate_solving(nom, 10) > 0


class TestNInvalide:
    """Les deux familles partagent la validation de ``n``."""

    @pytest.mark.parametrize("estimateur", [estimate_generation, estimate_solving])
    @pytest.mark.parametrize("n", [0, -1])
    def test_n_invalide(self, estimateur, n: int) -> None:
        with pytest.raises(ValueError):
            estimateur("astar" if estimateur is estimate_solving else "prim", n)

    @pytest.mark.parametrize("estimateur", [estimate_generation, estimate_solving])
    def test_n_non_entier(self, estimateur) -> None:
        with pytest.raises(TypeError):
            estimateur("prim" if estimateur is estimate_generation else "astar", 10.5)


class TestMemoryBudget:
    """Le budget, et la facon de le relever."""

    def test_defaut(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.delenv(BUDGET_ENV_VAR, raising=False)
        assert memory_budget() == MEMORY_BUDGET

    def test_variable_d_environnement(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """C'est ce qui permet d'exploiter une machine plus large sans toucher au code."""
        monkeypatch.setenv(BUDGET_ENV_VAR, str(64 * 1024**3))
        assert memory_budget() == 64 * 1024**3

    def test_variable_relue_a_chaque_appel(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setenv(BUDGET_ENV_VAR, "1024")
        assert memory_budget() == 1024
        monkeypatch.setenv(BUDGET_ENV_VAR, "2048")
        assert memory_budget() == 2048

    @pytest.mark.parametrize("valeur", ["beaucoup", "", "1.5"])
    def test_variable_invalide(self, valeur: str, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setenv(BUDGET_ENV_VAR, valeur)
        with pytest.raises(ValueError):
            memory_budget()

    def test_variable_negative(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setenv(BUDGET_ENV_VAR, "-5")
        with pytest.raises(ValueError):
            memory_budget()

    def test_le_budget_sert_aux_deux_phases(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """Un seul plafond, verifie pour la generation comme pour la resolution."""
        monkeypatch.setenv(BUDGET_ENV_VAR, str(1024**3))
        assert fits_generation("prim", 10)
        assert fits_solving("astar", 10)
        monkeypatch.setenv(BUDGET_ENV_VAR, "1")
        assert not fits_generation("prim", 10)
        assert not fits_solving("astar", 10)


class TestFits:
    """Les seuils de refus, sous le budget par defaut (2 Gio)."""

    def test_kruskal_echoue_a_cent_mille(self) -> None:
        """Le cas qui a motive ce module : ~2 Tio demandes."""
        assert not fits_generation("kruskal", 100_000)

    def test_petit_labyrinthe_passe_toujours(self) -> None:
        for nom in generator_choices():
            assert fits_generation(nom, 100)
        for nom in solver_choices():
            assert fits_solving(nom, 100)

    @pytest.mark.parametrize(
        ("generateur", "passe", "refuse"),
        [
            ("kruskal", 3_000, 6_000),
            ("recursive_backtracking", 8_000, 16_000),
            ("prim", 28_000, 56_000),
        ],
    )
    def test_plafond_de_generation(self, generateur: str, passe: int, refuse: int) -> None:
        """Sous 2 Gio : Kruskal s'arrete vers ``n = 3055``, le backtracking vers
        ``n = 8460``, Prim vers ``n = 28714``.
        """
        assert fits_generation(generateur, passe)
        assert not fits_generation(generateur, refuse)

    @pytest.mark.parametrize(
        ("solveur", "passe", "refuse"),
        [
            ("astar", 13_000, 26_000),
            ("dijkstra", 13_000, 26_000),
            ("recursive_backtracking", 32_000, 64_000),
        ],
    )
    def test_plafond_de_resolution(self, solveur: str, passe: int, refuse: int) -> None:
        """Sous 2 Gio : A* et Dijkstra vers ``n = 13377``, le backtracking vers
        ``n = 32767``.
        """
        assert fits_solving(solveur, passe)
        assert not fits_solving(solveur, refuse)

    def test_un_budget_releve_laisse_passer(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """Sur une machine plus large, le meme calcul doit devenir possible."""
        assert not fits_generation("kruskal", 20_000)
        monkeypatch.setenv(BUDGET_ENV_VAR, str(256 * 1024**3))
        assert fits_generation("kruskal", 20_000)

    def test_generer_ne_suffit_pas_a_resoudre(self) -> None:
        """Le cas que le garde-fou de generation seul laissait passer.

        Sous 2 Gio, Prim genere jusqu'a ``n = 28714`` mais A* ne resout que
        jusqu'a ``n = 13377``. Entre les deux, on genererait pendant des heures
        pour mourir ensuite dans le solveur -- d'ou la verification des deux
        phases *avant* la moindre allocation.
        """
        n = 20_000
        assert fits_generation("prim", n)
        assert not fits_solving("astar", n)


class TestLeModeleMajoreLaMesure:
    """Le test qui compte : la prediction ne doit jamais passer sous la realite.

    Un modele qui sous-estime ne leve pas d'erreur : il laisse le processus
    partir en ``MemoryError``. On mesure donc pour de vrai, et on compare.
    """

    @pytest.mark.parametrize("generateur", ["kruskal", "prim", "recursive_backtracking"])
    @pytest.mark.parametrize("n", [300, 600])
    def test_generation_majore_le_pic_mesure(self, generateur: str, n: int) -> None:
        mesure = _pic_generation(generateur, n)
        estimation = estimate_generation(generateur, n)
        assert estimation >= mesure, (
            f"{generateur} n={n} : estime {estimation} octets mais consomme "
            f"{mesure} -- le modele sous-estime, le processus mourrait"
        )

    @pytest.mark.parametrize("solveur", ["astar", "dijkstra", "recursive_backtracking"])
    @pytest.mark.parametrize("n", [300, 600])
    def test_resolution_majore_le_pic_mesure(self, solveur: str, n: int) -> None:
        mesure = _pic_resolution(solveur, n)
        estimation = estimate_solving(solveur, n)
        assert estimation >= mesure, (
            f"{solveur} n={n} : estime {estimation} octets mais consomme "
            f"{mesure} -- le modele sous-estime, le processus mourrait"
        )

    def test_generation_reste_dans_un_facteur_4(self) -> None:
        """Majore, mais sans exagerer : sinon le modele refuserait tout."""
        for generateur in ("kruskal", "prim", "recursive_backtracking"):
            mesure = _pic_generation(generateur, 500)
            estimation = estimate_generation(generateur, 500)
            assert estimation < 4 * mesure, f"{generateur} : {estimation} vs {mesure}"

    def test_resolution_reste_dans_un_facteur_4(self) -> None:
        for solveur in ("astar", "dijkstra", "recursive_backtracking"):
            mesure = _pic_resolution(solveur, 500)
            estimation = estimate_solving(solveur, 500)
            assert estimation < 4 * mesure, f"{solveur} : {estimation} vs {mesure}"
