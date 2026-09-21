"""Tests du chronométrage et de la mesure mémoire.

Ce qu'on vérifie, et pourquoi
-----------------------------
:func:`~mazes.metrics.measure` est l'outil de mesure des benchmarks. Un outil de
mesure faux ne plante pas : il renvoie des chiffres plausibles. Le résultat du
benchmark serait alors faux sans que rien ne le signale — d'où ces quelques
tests, qui portent sur les propriétés vérifiables (une durée positive, un pic
non nul quand on alloue) et non sur des valeurs exactes, qui dépendraient de la
machine.

Ce qui est testé ici n'est pas la précision de ``perf_counter`` ou de
``tracemalloc`` — c'est que ``measure`` les branche correctement.
"""

from __future__ import annotations

from mazes.metrics import measure


class TestMeasure:
    """``measure`` exécute, chronomètre, et n'oublie pas le résultat."""

    def test_renvoie_le_resultat(self) -> None:
        """La fonction mesurée n'est pas perdue : sans cela ``measure`` serait inutilisable."""
        assert measure(lambda: 6 * 7).result == 42

    def test_duree_positive(self) -> None:
        assert measure(lambda: sum(range(1000))).elapsed_s > 0.0

    def test_pic_memoire_voit_une_allocation(self) -> None:
        """Un mégaoctet alloué doit apparaître dans le pic.

        On alloue plus gros que la marge d'erreur de ``tracemalloc`` pour que
        le test porte sur le branchement, pas sur la précision de l'outil.
        """
        mesure = measure(lambda: bytearray(1 << 20))  # 1 Mio
        assert mesure.peak_kib >= 1024

    def test_pic_nul_sans_tracage(self) -> None:
        """``trace_memory=False`` ne mesure pas la mémoire : le champ vaut 0.

        C'est le mode des benchmarks de temps pur, où ``tracemalloc`` fausserait
        la mesure en ralentissant le code chronométré.
        """
        assert measure(lambda: bytearray(1 << 20), trace_memory=False).peak_kib == 0.0

    def test_affichage_lisible(self) -> None:
        """``str(mesure)`` sert dans les rapports de benchmark."""
        assert "ms" in str(measure(lambda: None))
