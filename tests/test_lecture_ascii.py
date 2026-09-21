"""Tests de lecture ASCII : fichier texte -> ``WallGrid``.

Les fichiers de test se fabriquent avec :func:`~mazes.rendering.render_to_string`
pour écrire un labyrinthe, puis :func:`~mazes.rendering.read_ascii` pour le relire.

Le test le plus rentable du fichier
-----------------------------------
:func:`TestAllerRetour.test_ecrire_puis_relire` : ecrire une grille en ASCII, la
relire, et verifier qu'on retombe sur la meme. Il couvre d'un seul coup toutes les
erreurs de correspondance entre indices de cellules et positions dans le texte --
c'est-a-dire la source d'erreur principale de cette etape.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from mazes.core.grid import WallGrid
from mazes.core.rng import RandomSource
from mazes.core.validation import is_perfect
from mazes.rendering import parse_ascii, read_ascii, render_to_string
from tests.conftest import SIZES
from tests.fixtures import random_maze, snake


class TestGeometrie:
    """Format du texte, tel que l'enonce l'impose."""

    @pytest.mark.parametrize("n", (1, 2, 3, 5, 8))
    def test_nombre_de_lignes(self, n: int) -> None:
        """Il y a exactement ``2n + 1`` lignes."""
        assert len(render_to_string(snake(n)).splitlines()) == 2 * n + 1

    @pytest.mark.parametrize("n", (1, 2, 3, 5, 8))
    def test_largeur_des_lignes(self, n: int) -> None:
        """Chaque ligne fait exactement ``2n + 1`` caracteres."""
        for ligne in render_to_string(snake(n)).splitlines():
            assert len(ligne) == 2 * n + 1

    def test_caracteres_utilises(self) -> None:
        """Le rendu d'un labyrinthe ne contient que ``#`` et ``.``.

        Les sauts de ligne sont evidemment exclus du controle : on teste chaque
        ligne separement.
        """
        for ligne in render_to_string(snake(5)).splitlines():
            assert set(ligne) <= {"#", "."}

    def test_coins_sont_des_murs(self) -> None:
        """Les quatre coins du texte sont des murs."""
        lignes = render_to_string(snake(5)).splitlines()
        assert lignes[0][0] == "#"
        assert lignes[0][-1] == "#"
        assert lignes[-1][0] == "#"
        assert lignes[-1][-1] == "#"

    def test_un_seul_passage_en_haut(self) -> None:
        """Le bord superieur n'a qu'une ouverture : l'entree."""
        haut = render_to_string(snake(6)).splitlines()[0]
        ouvertures = [i for i, ch in enumerate(haut) if ch == "."]
        assert ouvertures == [1]

    def test_un_seul_passage_en_bas(self) -> None:
        """Le bord inferieur n'a qu'une ouverture : la sortie."""
        n = 6
        bas = render_to_string(snake(n)).splitlines()[-1]
        ouvertures = [i for i, ch in enumerate(bas) if ch == "."]
        assert ouvertures == [2 * n - 1]

    def test_bords_lateraux_fermes(self) -> None:
        """Les bords gauche et droit ne sont jamais perces."""
        for ligne in render_to_string(snake(6)).splitlines():
            assert ligne[0] == "#"
            assert ligne[-1] == "#"


class TestAllerRetour:
    """Ecrire puis relire doit redonner la meme grille."""

    @pytest.mark.parametrize("n", SIZES)
    def test_ecrire_puis_relire(self, n: int, rng: RandomSource) -> None:
        """Ecrire puis relire redonne exactement la meme grille.

        Le test le plus rentable du fichier : il couvre d'un coup toutes les
        erreurs de correspondance entre indices de cellules et positions dans le
        texte.
        """
        for grille in (snake(n), random_maze(n, rng)):
            assert parse_ascii(render_to_string(grille)) == grille

    def test_la_perfection_survit(self, rng: RandomSource) -> None:
        """Un labyrinthe parfait relu reste parfait."""
        grille = random_maze(13, rng)
        assert is_perfect(parse_ascii(render_to_string(grille)))

    def test_entree_et_sortie_conservees(self) -> None:
        """Les ouvertures d'entree et de sortie survivent a l'aller-retour."""
        grille = snake(8)
        relue = parse_ascii(render_to_string(grille))
        assert relue.entry_open == grille.entry_open
        assert relue.exit_open == grille.exit_open


class TestLectureFichier:
    """Lecture depuis le disque.

    Les trois variantes ne diffèrent que par les octets écrits : elles
    partagent le même corps, donc un seul test paramétré. Les séparer
    reviendrait à recopier trois fois la même assertion.
    """

    @pytest.mark.parametrize(
        "variante",
        ("telle_quelle", "saut_de_ligne_final", "fins_de_ligne_windows"),
    )
    def test_lit_le_fichier_ecrit(self, variante: str, tmp_path: Path, rng: RandomSource) -> None:
        """Le fichier se relit à l'identique, quelle que soit sa fin de ligne.

        Un fichier écrit sous Windows porte des ``\\r\\n``, et un éditeur de
        texte ajoute souvent un saut de ligne final : la lecture doit tolérer
        les deux, sinon un labyrinthe valide deviendrait illisible selon l'outil
        qui l'a écrit.
        """
        grille = random_maze(13, rng)
        texte = render_to_string(grille)
        if variante == "saut_de_ligne_final":
            texte += "\n"
        elif variante == "fins_de_ligne_windows":
            texte = texte.replace("\n", "\r\n")

        chemin = tmp_path / "maze.txt"
        chemin.write_bytes(texte.encode("ascii"))
        assert read_ascii(chemin) == grille

    def test_fichier_inexistant(self, tmp_path: Path) -> None:
        with pytest.raises(FileNotFoundError):
            read_ascii(tmp_path / "absent.txt")


class TestFichierMalforme:
    """Entrees invalides : erreur explicite, pas de plantage silencieux."""

    def test_texte_vide(self) -> None:
        with pytest.raises(ValueError):
            parse_ascii("")

    def test_largeur_paire(self) -> None:
        """Un rendu valide a toujours un nombre impair de colonnes."""
        with pytest.raises(ValueError):
            parse_ascii("####\n#..#\n####\n")

    def test_lignes_de_longueurs_differentes(self) -> None:
        with pytest.raises(ValueError):
            parse_ascii("###\n#.#\n#####\n")

    def test_nombre_de_lignes_pair(self) -> None:
        with pytest.raises(ValueError):
            parse_ascii("###\n#.#\n")


class TestFichierDeResolution:
    """Relire un fichier qui contient un parcours (des ``o`` et des ``*``)."""

    def test_les_marqueurs_sont_traites_comme_libres(self) -> None:
        """Les ``o`` et ``*`` sont relus comme des cellules libres.

        Ils decrivent un parcours, pas la structure du labyrinthe : relire une
        resolution doit redonner le meme labyrinthe que l'original.
        """
        grille = snake(5)
        texte = render_to_string(grille)
        # remplacer quelques cellules par des marqueurs de parcours
        marque = list(texte)
        marque[8] = "o"
        marque[10] = "*"
        marque[16] = "o"
        assert parse_ascii("".join(marque)) == grille
