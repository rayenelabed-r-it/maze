"""Tests du fichier de statistiques.

Ce qu'on vérifie, et pourquoi
-----------------------------
Quand un export est refusé, ce fichier est tout ce qui reste. S'il est faux,
l'utilisateur n'a plus aucun moyen de savoir ce qui a été généré : on vérifie
donc ses chiffres, pas seulement son existence.

Le piège à éviter
-----------------
``count_passages`` compte les bits à 1 des tampons de murs, qui sont arrondis à
l'octet. Le dernier contient des bits de remplissage que ``WallGrid`` force à 1 :
les compter comme des murs fait dériver le total, jusqu'à donner -6 au lieu de 8
sur ``n = 3``. Passer à côté donnerait un nombre plausible et faux sur les
grandes grilles, indétectable à l'œil. Les valeurs attendues sont donc recoupées
par un comptage force brute, cellule par cellule.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from mazes.core.grid import EAST, SOUTH, WallGrid
from mazes.core.rng import RandomSource
from mazes.rendering import (
    count_passages,
    refused_lines,
    stats_lines,
    write_refused,
    write_stats,
)
from mazes.rendering.policy import ExportPolicy
from mazes.solvers import get_solver
from tests.conftest import SIZES
from tests.fixtures import cul_de_sac, random_maze, snake

SEED = 12345

#: Politique qui refuse l'ASCII : côté 11 > 3, sans sous-échantillonnage.
REFUSE_ASCII = ExportPolicy(max_ascii_side=3)

#: Politique qui réduit l'ASCII au lieu de le refuser.
REDUIT_ASCII = ExportPolicy(max_ascii_side=3, ascii_subsample=True)


def _brute(grid: WallGrid) -> int:
    """Comptage de référence : parcourt les cellules une à une."""
    n = grid.n
    total = 0
    for r in range(n):
        for c in range(n):
            if c + 1 < n and not grid.has_wall(r, c, EAST):
                total += 1
            if r + 1 < n and not grid.has_wall(r, c, SOUTH):
                total += 1
    return total


def _maze(n: int) -> WallGrid:
    """Labyrinthe parfait aléatoire reproductible."""
    return random_maze(n, RandomSource(SEED))


class TestPassages:
    """``count_passages`` est le seul calcul non trivial du module."""

    @pytest.mark.parametrize("n", SIZES)
    def test_snake_vaut_n2_moins_1(self, n: int) -> None:
        """Le serpentin est un arbre couvrant : exactement ``n² - 1`` arêtes."""
        assert count_passages(snake(n)) == n * n - 1

    @pytest.mark.parametrize("n", SIZES)
    def test_random_vaut_n2_moins_1(self, n: int) -> None:
        """Un labyrinthe parfait a la même propriété, quel que soit le tracé."""
        assert count_passages(_maze(n)) == n * n - 1

    @pytest.mark.parametrize("n", [1, 3, 8, 13])
    def test_grille_fermee_vaut_zero(self, n: int) -> None:
        """Aucun mur abattu : le compte doit être nul, pas négatif."""
        assert count_passages(WallGrid(n)) == 0

    def test_bits_de_remplissage_ignores(self) -> None:
        """``n = 3`` remplit 7 bits de trop dans chaque tampon : ils ne comptent pas.

        C'est le test le plus rentable du module. Sans la correction, la formule
        naïve rend ``-6`` ici, et un nombre faux mais plausible sur les grandes
        grilles.
        """
        grid = snake(3)
        remplissage = 8 * len(grid.east) - grid.n**2
        assert remplissage == 7, "le cas perdrait son sens si n² etait multiple de 8"
        assert count_passages(grid) == 8

    @pytest.mark.parametrize("band_bytes", [1, 2, 7, 64, 1 << 20])
    def test_le_decoupage_en_bandes_ne_change_rien(self, band_bytes: int) -> None:
        """Le résultat doit être indépendant de la taille des bandes."""
        grid = _maze(48)
        assert count_passages(grid, band_bytes=band_bytes) == count_passages(grid)

    def test_band_bytes_invalide(self) -> None:
        with pytest.raises(ValueError):
            count_passages(WallGrid(4), band_bytes=0)

    @pytest.mark.parametrize(
        "nom", ["ferme 3", "snake 3", "cul_de_sac", "random 16", "random 33"]
    )
    def test_recoupe_par_comptage_brut(self, nom: str) -> None:
        """Le comptage vectorisé doit valoir le parcours cellule par cellule."""
        grilles = {
            "ferme 3": WallGrid(3),
            "snake 3": snake(3),
            "cul_de_sac": cul_de_sac(),
            "random 16": _maze(16),
            "random 33": _maze(33),
        }
        grid = grilles[nom]
        assert count_passages(grid) == _brute(grid)


class TestLignes:
    """Le contenu et l'ordre des lignes du format."""

    def _lignes(
        self,
        n: int,
        politique: ExportPolicy | None = None,
        **kw: object,
    ) -> list[str]:
        """Lignes pour un labyrinthe de ``n``, sous une politique donnée.

        La grille et la politique portent le même ``n`` : les mélanger
        produirait un fichier où ``n: 5`` côtoierait un export décrit pour
        100000, et le test validerait une incohérence.
        """
        politique = politique if politique is not None else ExportPolicy()
        return list(stats_lines(_maze(n), politique.plan(n), **kw))

    def test_entete(self) -> None:
        assert self._lignes(5)[0] == "labyrinthe_statistiques"

    def test_n_et_cellules(self) -> None:
        lignes = self._lignes(5)
        assert "n: 5" in lignes
        assert "cellules: 25" in lignes

    def test_passages(self) -> None:
        assert "passages: 24" in self._lignes(5)

    def test_chemin_longueur_sans_resultat(self) -> None:
        """``generate`` n'a pas de parcours : la ligne doit exister quand même."""
        assert "chemin_longueur: inconnu" in self._lignes(5)

    def test_chemin_longueur_avec_resultat(self) -> None:
        result = get_solver("astar").solve(_maze(8), (0, 0), (7, 7))
        lignes = self._lignes(8, result=result)
        assert f"chemin_longueur: {result.path_length}" in lignes

    def test_resultat_de_type_incorrect(self) -> None:
        with pytest.raises(TypeError):
            self._lignes(5, result=object())

    def test_export_ascii_oui(self) -> None:
        lignes = self._lignes(5)
        assert "export_ascii: oui" in lignes
        assert not any(ligne.startswith("export_ascii_raison") for ligne in lignes)

    def test_export_ascii_refuse(self) -> None:
        """Au-delà de la limite, la raison doit accompagner le refus."""
        lignes = self._lignes(5, REFUSE_ASCII)
        assert "export_ascii: refuse" in lignes
        raison = [ligne for ligne in lignes if ligne.startswith("export_ascii_raison")]
        assert len(raison) == 1

    def test_export_ascii_refuse_par_l_utilisateur(self) -> None:
        """Sans ``ascii_ecrit``, le fichier annoncerait un export qui n'a pas eu lieu."""
        lignes = self._lignes(5, ascii_ecrit=False)
        assert "export_ascii: refuse" in lignes
        assert "export_ascii_raison: refuse par l'utilisateur" in lignes

    def test_export_ascii_reduit_est_bien_ecrit(self) -> None:
        """Un ASCII réduit est **écrit** : le compter comme refusé serait un mensonge."""
        lignes = self._lignes(5, REDUIT_ASCII)
        assert "export_ascii: reduit x4" in lignes

    def test_export_image_pleine_resolution(self) -> None:
        assert "export_image: pleine resolution" in self._lignes(5)

    def test_export_image_reduite(self) -> None:
        """Côté 11 réduit x4 sous une limite d'image de 3 : il reste 2 pixels."""
        assert "export_image: reduite x4 -> 2x2" in self._lignes(5, ExportPolicy(max_image_side=3))

    def test_ordre_des_lignes_conforme_au_modele(self) -> None:
        """L'ordre suit ``doc/05-export.md`` : un lecteur peut s'y fier."""
        cles = [ligne.split(":")[0] for ligne in self._lignes(5, REFUSE_ASCII)]
        assert cles == [
            "labyrinthe_statistiques",
            "n",
            "cellules",
            "passages",
            "chemin_longueur",
            "export_ascii",
            "export_ascii_raison",
            "export_image",
        ]

    def test_fichier_pur_ascii(self) -> None:
        """Le fichier est encodé en ASCII strict : un accent ferait échouer l'écriture."""
        for politique in (ExportPolicy(), REFUSE_ASCII, REDUIT_ASCII):
            assert all(ligne.isascii() for ligne in self._lignes(5, politique))


class TestEcriture:
    """``write_stats`` écrit sur le disque, en flux."""

    def test_ecrit_le_fichier(self, tmp_path: Path) -> None:
        chemin = write_stats(_maze(5), tmp_path / "s.txt", ExportPolicy().plan(5))
        assert chemin == tmp_path / "s.txt"
        contenu = chemin.read_text(encoding="ascii")
        assert contenu.startswith("labyrinthe_statistiques\n")
        assert "cellules: 25" in contenu

    def test_cree_les_repertoires(self, tmp_path: Path) -> None:
        cible = tmp_path / "sous" / "dossier" / "s.txt"
        write_stats(_maze(5), cible, ExportPolicy().plan(5))
        assert cible.exists()

    def test_chemin_renvoye_est_celui_ecrit(self, tmp_path: Path) -> None:
        cible = tmp_path / "s.txt"
        assert write_stats(_maze(5), cible, ExportPolicy().plan(5)) == cible


class TestCalculRefuse:
    """Le fichier de statistiques quand un calcul a été refusé faute de budget.

    Il n'y a alors aucune grille : ``passages`` et ``chemin_longueur`` ne peuvent
    pas être calculés. Le fichier ne doit donc pas laisser croire à un labyrinthe
    vide -- c'est le seul cas où ces deux lignes n'ont pas de valeur.
    """

    RAISON = "kruskal demanderait 2.1 Tio pour 10000000000 cellules (budget 2.0 Gio)"

    def _lignes(self, phase: str = "generation", n: int = 100000) -> list[str]:
        return list(refused_lines(n, phase=phase, raison=self.RAISON))

    def test_n_et_cellules(self) -> None:
        lignes = self._lignes()
        assert "n: 100000" in lignes
        assert "cellules: 10000000000" in lignes

    def test_passages_et_chemin_inconnus(self) -> None:
        """``inconnu`` et non ``0`` : un zero se lirait « labyrinthe sans passage »."""
        lignes = self._lignes()
        assert "passages: inconnu" in lignes
        assert "chemin_longueur: inconnu" in lignes

    @pytest.mark.parametrize("phase", ["generation", "resolution"])
    def test_annonce_la_phase_refusee(self, phase: str) -> None:
        """Les deux phases sont refusables, et le fichier doit dire laquelle."""
        lignes = self._lignes(phase)
        assert f"{phase}: refusee" in lignes
        assert f"{phase}_raison: {self.RAISON}" in lignes

    def test_aucune_ligne_d_export(self) -> None:
        """Rien n'a ete produit, donc rien n'a ete refuse a l'export.

        Annoncer un refus d'export decrirait une decision qui n'a jamais eu lieu.
        """
        lignes = self._lignes()
        assert not any(ligne.startswith("export_") for ligne in lignes)

    @pytest.mark.parametrize("phase", ["generation", "resolution"])
    def test_ordre_des_lignes(self, phase: str) -> None:
        cles = [ligne.split(":")[0] for ligne in self._lignes(phase)]
        assert cles == [
            "labyrinthe_statistiques",
            "n",
            "cellules",
            "passages",
            "chemin_longueur",
            phase,
            f"{phase}_raison",
        ]

    def test_fichier_pur_ascii(self) -> None:
        assert all(ligne.isascii() for ligne in self._lignes())

    @pytest.mark.parametrize("n", [0, -1])
    def test_n_invalide(self, n: int) -> None:
        with pytest.raises(ValueError):
            list(refused_lines(n, phase="generation", raison="peu importe"))

    def test_ecrit_le_fichier(self, tmp_path: Path) -> None:
        cible = tmp_path / "refuse_statistiques.txt"
        assert write_refused(
            100000, cible, phase="resolution", raison=self.RAISON
        ) == cible
        contenu = cible.read_text(encoding="ascii")
        assert contenu.startswith("labyrinthe_statistiques\n")
        assert "resolution: refusee" in contenu
