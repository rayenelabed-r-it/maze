"""Tests de la lecture de ``outputs/`` et des mesures du benchmark.

Le dossier ``outputs/`` contient deux sortes de ``.txt`` : les labyrinthes et
les fichiers de statistiques. Les confondre a déjà fait planter le benchmark,
d'où le test de régression dans :class:`TestLireOutputs`.

Seules les fonctions pures sont testées ici : classement des noms, lecture,
médiane, agrégation. Le rendu graphique en est exclu, il demanderait matplotlib.
"""

from __future__ import annotations

from pathlib import Path

import pytest
from benchmarks.collecte import (
    ENTETE_STATS,
    Maze,
    agreger,
    classer,
    grouper,
    lire_outputs,
    mediane,
    mesurer_labyrinthe,
)

from mazes.budget import estimate_generation
from mazes.core.grid import WallGrid
from mazes.core.rng import RandomSource
from mazes.generators import get_generator
from mazes.metrics import Measurement
from mazes.rendering import write_ascii, write_refused

SEED = 12345


def _labyrinthe(n: int = 5) -> WallGrid:
    return get_generator("prim").generate(n, RandomSource(SEED))


class TestClasser:
    """Trois conventions de nom, et rien de deviné."""

    @pytest.mark.parametrize(
        ("nom", "attendu"),
        [
            ("kruskal_astar_100", ("kruskal", "astar", 100)),
            ("prim_dijkstra_5000", ("prim", "dijkstra", 5000)),
            ("maze_prim_20", ("prim", None, 20)),
            ("maze_kruskal_100", ("kruskal", None, 100)),
            ("solved_astar_10", (None, "astar", 10)),
        ],
    )
    def test_conventions(self, nom: str, attendu: tuple) -> None:
        assert classer(nom) == attendu

    def test_recursive_backtracking_est_un_seul_nom(self) -> None:
        """Un découpage sur les tirets bas en ferait deux."""
        assert classer("recursive_backtracking_astar_1000") == (
            "recursive_backtracking",
            "astar",
            1000,
        )
        assert classer("recursive_backtracking_recursive_backtracking_1000") == (
            "recursive_backtracking",
            "recursive_backtracking",
            1000,
        )

    def test_solveur_seul_en_fin_de_nom(self) -> None:
        assert classer("kruskal_recursive_backtracking_100") == (
            "kruskal",
            "recursive_backtracking",
            100,
        )

    def test_algorithme_inconnu(self) -> None:
        assert classer("inconnu_42") == (None, None, 42)

    def test_sans_entier_final(self) -> None:
        assert classer("pasdenombre") == (None, None, None)

    def test_suffixe_statistiques_non_reconnu(self) -> None:
        """Le suffixe masque le n : l'appelant doit le retirer avant."""
        assert classer("kruskal_astar_1000_statistiques") == (None, None, None)


class TestLireOutputs:
    """Le tri de ``outputs/``."""

    def test_un_fichier_de_statistiques_nest_pas_un_labyrinthe(
        self, tmp_path: Path
    ) -> None:
        """Régression : un fichier de statistiques faisait planter la lecture.

        Il ne fait que 7 lignes pour 23 colonnes, ce que ``read_ascii`` refuse.
        """
        write_refused(
            n=5000,
            destination=tmp_path / "kruskal_astar_5000_statistiques.txt",
            phase="generation",
            raison="kruskal demanderait 5.4 Gio pour 25000000 cellules",
        )
        inv = lire_outputs(tmp_path)

        assert inv.mazes == ()
        assert len(inv.refus) == 1
        assert inv.refus[0].n == 5000
        assert inv.refus[0].phase == "generation"

    def test_le_cout_vient_du_modele(self, tmp_path: Path) -> None:
        """Le fichier ne contient que « 5.4 Gio », qui n'est pas analysé."""
        write_refused(
            n=5000,
            destination=tmp_path / "kruskal_astar_5000_statistiques.txt",
            phase="generation",
            raison="peu importe le texte",
        )
        refus = lire_outputs(tmp_path).refus[0]
        assert refus.cout_bytes == estimate_generation("kruskal", 5000)

    def test_statistiques_reussies_gardent_leurs_mesures(self, tmp_path: Path) -> None:
        write_ascii(_labyrinthe(5), tmp_path / "kruskal_astar_5.txt")
        (tmp_path / "kruskal_astar_5_statistiques.txt").write_text(
            f"{ENTETE_STATS}\n"
            "n: 5\ncellules: 25\npassages: 24\nchemin_longueur: 17\n"
            "export_ascii: refuse\n",
            encoding="ascii",
        )
        inv = lire_outputs(tmp_path)

        assert len(inv.mazes) == 1
        assert len(inv.refus) == 1
        assert inv.refus[0].passages == 24
        assert inv.refus[0].chemin_longueur == 17
        assert inv.refus[0].phase is None

    def test_labyrinthe_lu_et_attribue(self, tmp_path: Path) -> None:
        write_ascii(_labyrinthe(6), tmp_path / "maze_prim_6.txt")
        inv = lire_outputs(tmp_path)

        assert len(inv.mazes) == 1
        assert inv.mazes[0].n == 6
        assert inv.mazes[0].generateur == "prim"

    def test_dossier_vide(self, tmp_path: Path) -> None:
        inv = lire_outputs(tmp_path)
        assert inv.mazes == () and inv.refus == () and inv.ignores == ()

    def test_fichier_illisible_est_ignore(self, tmp_path: Path) -> None:
        (tmp_path / "notes_12.txt").write_text("bonjour\n", encoding="ascii")
        inv = lire_outputs(tmp_path)

        assert inv.mazes == () and inv.refus == ()
        assert len(inv.ignores) == 1


class TestGrouper:
    """Le regroupement réunit les labyrinthes de même taille et même générateur."""

    def test_regroupe_par_generateur_et_n(self) -> None:
        mazes = tuple(
            Maze(chemin=Path(f"{g}_{n}.txt"), grille=_labyrinthe(3), generateur=g, n=n)
            for g, n in (("prim", 5), ("prim", 5), ("kruskal", 5), ("prim", 9))
        )
        groupes = grouper(mazes)

        assert len(groupes[("prim", 5)]) == 2
        assert len(groupes[("kruskal", 5)]) == 1
        assert len(groupes[("prim", 9)]) == 1

    def test_ordre_stable(self) -> None:
        """Pour que les sections du rapport ne changent pas d'ordre d'un run à l'autre."""
        mazes = tuple(
            Maze(chemin=Path(f"{g}_{n}.txt"), grille=_labyrinthe(3), generateur=g, n=n)
            for g, n in (("prim", 9), ("kruskal", 5), ("prim", 5))
        )
        assert list(grouper(mazes)) == [("kruskal", 5), ("prim", 5), ("prim", 9)]


class TestMediane:
    """La médiane, retenue par le protocole à la place de la moyenne."""

    @pytest.mark.parametrize(
        ("valeurs", "attendu"),
        [([3.0], 3.0), ([1.0, 3.0, 2.0], 2.0), ([1.0, 2.0, 3.0, 4.0], 2.5)],
    )
    def test_valeurs(self, valeurs: list[float], attendu: float) -> None:
        assert mediane(valeurs) == attendu

    def test_ignore_une_valeur_aberrante(self) -> None:
        assert mediane([10.0, 11.0, 12.0, 10_000.0]) == 11.5

    def test_liste_vide(self) -> None:
        with pytest.raises(ValueError):
            mediane([])


class TestAgreger:
    """La médiane sur plusieurs labyrinthes, et la validité."""

    def _mesure(self, temps: float, valide: bool = True) -> dict:
        from benchmarks.collecte import Metriques

        return {
            "astar": Metriques(
                solveur="astar",
                temps_s=temps,
                pic_kio=temps * 10,
                developpees=int(temps * 100),
                frontiere=int(temps),
                chemin=5,
                efficacite=0.5,
                valide=valide,
            )
        }

    def test_mediane_sur_les_labyrinthes(self) -> None:
        agreges = agreger([self._mesure(1.0), self._mesure(2.0), self._mesure(3.0)])
        assert agreges["astar"].temps_s == 2.0

    def test_validite_conjonctive(self) -> None:
        """Un chemin qui traverse un mur est un bug, pas une valeur à écarter."""
        agreges = agreger([self._mesure(1.0), self._mesure(2.0, valide=False)])
        assert not agreges["astar"].valide

    def test_sans_labyrinthe(self) -> None:
        with pytest.raises(ValueError):
            agreger([])


class TestMesurerLabyrinthe:
    """Le protocole appliqué à une grille."""

    def test_mesure_les_trois_solveurs(self) -> None:
        mesures = mesurer_labyrinthe(_labyrinthe(6))
        assert set(mesures) == {"astar", "dijkstra", "recursive_backtracking"}

    def test_temps_et_memoire_sont_mesures(self) -> None:
        """Les deux passes doivent aboutir : sans la seconde, le pic serait nul."""
        mesures = mesurer_labyrinthe(_labyrinthe(9))
        for metriques in mesures.values():
            assert metriques.temps_s > 0.0
            assert metriques.pic_kio > 0.0

    def test_meme_labyrinthe_pour_tous(self) -> None:
        """Tous les solveurs voient la même grille, donc trouvent le même chemin."""
        mesures = mesurer_labyrinthe(_labyrinthe(7))
        assert len({m.chemin for m in mesures.values()}) == 1

    def test_tous_valides(self) -> None:
        assert all(m.valide for m in mesurer_labyrinthe(_labyrinthe(8)).values())


class TestMeasurement:
    """Le branchement sur ``metrics.measure``."""

    def test_deux_passes_par_solveur(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """Une passe sans traçage pour le temps, une avec pour la mémoire."""
        appels: list[bool] = []

        def espion(fn, trace_memory=True):
            appels.append(trace_memory)
            return Measurement(result=fn(), elapsed_s=0.01, peak_kib=1.0)

        monkeypatch.setattr("benchmarks.collecte.measure", espion)
        mesurer_labyrinthe(_labyrinthe(5), ["astar"], echauffement=False)

        assert appels == [False, True]
