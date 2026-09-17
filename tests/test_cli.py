"""Tests de la ligne de commande.

Ce qu'on vérifie, et pourquoi
-----------------------------
Le CLI est le point d'entrée du livrable : c'est lui qui enchaîne
``générer -> résoudre -> exporter en JPEG``. Les tests de solveurs vérifient les
algorithmes, pas ce câblage : une commande mal dispatchée, un chemin de sortie
mal calculé ou une extension mal choisie passeraient inaperçus.

``main(argv)`` prend ses arguments en paramètre et **retourne** un code au lieu
d'appeler ``sys.exit`` : les commandes se testent donc en process, sans
sous-shell, et ``capsys`` peut inspecter ce qui a été affiché.

Le piège à éviter
-----------------
Sans ``--output``, les commandes écrivent dans ``outputs/`` **relatif au
répertoire courant**. Chaque test passe donc un chemin explicite sous
``tmp_path`` : sans cela il polluerait le dépôt.

Codes de retour
---------------
``0`` succès, ``1`` échec métier (chemin absent, labyrinthe non parfait),
``2`` erreur d'entrée (fichier manquant, extension inconnue).
"""

from __future__ import annotations

from pathlib import Path

import pytest

from mazes.cli import main
from mazes.core.grid import WallGrid
from mazes.generators import generator_choices
from mazes.rendering import read_ascii, write_ascii
from mazes.solvers import solver_choices

GENERATEURS = generator_choices()
SOLVEURS = solver_choices()


def _generer(destination: Path, n: int = 10, seed: int = 1) -> Path:
    """Fabrique un labyrinthe ASCII via le CLI, et le renvoie."""
    assert main(["generate", "--n", str(n), "--seed", str(seed), "--output", str(destination)]) == 0
    return destination


class TestList:
    """``mazes list`` expose tout ce que les registres contiennent."""

    def test_liste_les_generateurs_et_les_solveurs(self, capsys: pytest.CaptureFixture) -> None:
        """Chaque nom enregistré apparaît : le CLI ne code rien en dur."""
        assert main(["list"]) == 0
        sortie = capsys.readouterr().out
        for nom in GENERATEURS + SOLVEURS:
            assert nom in sortie, f"{nom} manque dans `mazes list`"


class TestGenerate:
    """``mazes generate`` écrit un labyrinthe ASCII sur le disque."""

    def test_ecrit_un_labyrinthe_parfait(self, tmp_path: Path) -> None:
        """``--check`` valide la perfection : le code 0 en est la preuve."""
        fichier = _generer(tmp_path / "maze.txt", n=10)
        assert read_ascii(fichier).n == 10

    @pytest.mark.parametrize("algorithme", GENERATEURS)
    def test_tous_les_generateurs(self, algorithme: str, tmp_path: Path) -> None:
        """Chaque générateur du registre produit un labyrinthe parfait."""
        fichier = tmp_path / f"{algorithme}.txt"
        code = main(
            [
                "generate", "--n", "12", "--algorithm", algorithme, "--seed", "3",
                "--check", "--output", str(fichier),
            ]
        )
        assert code == 0

    def test_print_affiche_dans_le_terminal(
        self, tmp_path: Path, capsys: pytest.CaptureFixture
    ) -> None:
        """``--print`` envoie le labyrinthe sur la sortie standard."""
        main(["generate", "--n", "5", "--seed", "1", "--print", "--output", str(tmp_path / "m.txt")])
        assert "#" in capsys.readouterr().out

    def test_check_detecte_un_labyrinthe_imparfait(
        self, tmp_path: Path, capsys: pytest.CaptureFixture, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """``--check`` échoue en code 1 si la grille n'est pas parfaite.

        Aucun générateur du registre ne produit de grille imparfaite : on force
        donc la réponse de ``is_perfect``. Ce qui est testé ici n'est pas la
        détection -- elle est couverte par les tests de générateurs -- mais que
        le CLI la branche bien sur ``--check`` et renvoie le bon code.
        """
        monkeypatch.setattr("mazes.cli.is_perfect", lambda grille: False)
        code = main(["generate", "--n", "5", "--check", "--output", str(tmp_path / "m.txt")])
        assert code == 1
        assert "parfait" in capsys.readouterr().err

    def test_sortie_par_defaut(self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
        """Sans ``--output``, le fichier va dans ``outputs/`` du répertoire courant.

        Le nom par défaut reprend l'algorithme et la taille. Le test se place
        dans ``tmp_path`` : sans cela il écrirait dans le ``outputs/`` du dépôt,
        qui est ignoré par git mais bien réel -- et le polluerait à chaque run.
        """
        monkeypatch.chdir(tmp_path)
        assert main(["generate", "--n", "5", "--seed", "1"]) == 0
        defaut = tmp_path / "outputs" / f"maze_{GENERATEURS[0]}_5.txt"
        assert defaut.exists()


class TestSolve:
    """``mazes solve`` relit un labyrinthe et écrit le parcours."""

    @pytest.fixture
    def labyrinthe(self, tmp_path: Path) -> Path:
        return _generer(tmp_path / "maze.txt", n=10)

    def test_ecrit_le_chemin_en_ascii(self, labyrinthe: Path, tmp_path: Path) -> None:
        base = tmp_path / "solved"
        assert main(["solve", "--input", str(labyrinthe), "--output", str(base)]) == 0
        assert "o" in base.with_suffix(".txt").read_text(encoding="utf-8")

    def test_ecrit_aussi_une_image(self, labyrinthe: Path, tmp_path: Path) -> None:
        """Le pipeline de la consigne exporte en JPEG, pas seulement en ASCII."""
        base = tmp_path / "solved"
        assert main(["solve", "--input", str(labyrinthe), "--output", str(base)]) == 0
        assert base.with_suffix(".jpg").stat().st_size > 0

    @pytest.mark.parametrize("solveur", SOLVEURS)
    def test_tous_les_solveurs(self, solveur: str, labyrinthe: Path, tmp_path: Path) -> None:
        base = tmp_path / f"solved_{solveur}"
        code = main(
            ["solve", "--input", str(labyrinthe), "--algorithm", solveur, "--output", str(base)]
        )
        assert code == 0

    def test_fichier_inexistant(self, tmp_path: Path, capsys: pytest.CaptureFixture) -> None:
        """Fichier absent : code 2 et message lisible, pas de trace Python."""
        code = main(["solve", "--input", str(tmp_path / "absent.txt"), "--output", str(tmp_path / "x")])
        assert code == 2
        assert "Erreur" in capsys.readouterr().err

    def test_sortie_injoignable(self, tmp_path: Path, capsys: pytest.CaptureFixture) -> None:
        """Sortie inatteignable : code 1 et message, sans écrire de fichier.

        ``WallGrid(3)`` est entièrement close : l'entrée et la sortie existent
        mais rien ne les relie. C'est le cas d'un fichier ASCII valide dont le
        labyrinthe n'est pas parfait -- la résolution doit le signaler, pas
        produire une image trompeuse.
        """
        fichier = tmp_path / "ferme.txt"
        write_ascii(WallGrid(3), fichier)

        code = main(["solve", "--input", str(fichier), "--output", str(tmp_path / "x")])
        assert code == 1
        assert "Aucun chemin" in capsys.readouterr().err


class TestRun:
    """``mazes run`` enchaîne les trois étapes en une commande."""

    def test_pipeline_complet(self, tmp_path: Path) -> None:
        base = tmp_path / "pipeline"
        assert main(["run", "--n", "12", "--seed", "5", "--output", str(base)]) == 0
        assert "o" in base.with_suffix(".txt").read_text(encoding="utf-8")
        assert base.with_suffix(".jpg").stat().st_size > 0


class TestConvert:
    """``mazes convert`` choisit le format d'après l'extension."""

    @pytest.fixture
    def source(self, tmp_path: Path) -> Path:
        return _generer(tmp_path / "maze.txt", n=6)

    def test_vers_texte(self, source: Path, tmp_path: Path) -> None:
        """La grille relue est identique : la conversion ne perd rien."""
        cible = tmp_path / "copie.txt"
        assert main(["convert", "--input", str(source), "--output", str(cible)]) == 0
        assert read_ascii(cible) == read_ascii(source)

    def test_vers_image(self, source: Path, tmp_path: Path) -> None:
        cible = tmp_path / "image.jpg"
        assert main(["convert", "--input", str(source), "--output", str(cible)]) == 0
        assert cible.stat().st_size > 0

    def test_extension_inconnue(self, source: Path, tmp_path: Path, capsys: pytest.CaptureFixture) -> None:
        """``.png`` n'est pas géré : code 2 plutôt qu'une image silencieusement fausse."""
        code = main(["convert", "--input", str(source), "--output", str(tmp_path / "x.png")])
        assert code == 2
        assert "Erreur" in capsys.readouterr().err


class TestArgumentsInvalides:
    """C'est ``argparse`` qui refuse, pas le code métier : il sort en ``SystemExit``."""

    def test_algorithme_inconnu(self, tmp_path: Path) -> None:
        with pytest.raises(SystemExit) as erreur:
            main(["generate", "--algorithm", "inconnu", "--output", str(tmp_path / "x.txt")])
        assert erreur.value.code == 2

    def test_sous_commande_absente(self) -> None:
        with pytest.raises(SystemExit):
            main([])
