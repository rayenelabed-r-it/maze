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
from PIL import Image

from mazes import cli as cli_mod
from mazes import interaction as interaction_mod
from mazes.budget import BUDGET_ENV_VAR
from mazes.cli import main
from mazes.core.grid import WallGrid
from mazes.generators import generator_choices
from mazes.rendering import ExportPolicy, read_ascii, write_ascii
from mazes.rendering import policy as policy_mod
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


def _explose(*args: object, **kw: object) -> bool:
    """Remplace ``confirm`` : appelé, c'est que la question n'aurait pas dû être posée."""
    raise AssertionError("aucune question ne doit etre posee ici")


def _stats_de(tmp_path: Path, base: str) -> Path:
    return tmp_path / f"{base}_statistiques.txt"


class TestPolitiqueBranchee:
    """La politique d'export agit réellement sur ce qui est écrit.

    C'est le point que ces tests protègent : ``ExportPolicy`` a longtemps été du
    code mort, documenté mais appelé nulle part. Un test qui se contenterait de
    vérifier que les fichiers attendus existent passerait aussi bien avec la
    politique débranchée.
    """

    def test_ascii_refuse_au_dela_de_la_limite(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """Sans la politique, ``run`` écrirait l'ASCII pleine résolution quoi qu'il arrive."""
        monkeypatch.setattr(
            cli_mod, "_politique_export", lambda: ExportPolicy(max_ascii_side=3)
        )
        base = tmp_path / "petit"
        assert main(["run", "--n", "5", "--seed", "1", "--output", str(base)]) == 0

        assert not base.with_suffix(".txt").exists()
        stats = _stats_de(tmp_path, "petit")
        assert stats.exists()
        assert "export_ascii: refuse" in stats.read_text(encoding="ascii")

    def test_image_reduite_par_la_politique(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """Le facteur de la politique doit atteindre ``write_image``, pas être ignoré.

        Côté 25 réduit sous une limite de 7 : facteur 4, soit 6 pixels de côté.
        """
        monkeypatch.setattr(
            cli_mod, "_politique_export", lambda: ExportPolicy(max_image_side=7)
        )
        base = tmp_path / "reduite"
        assert main(["run", "--n", "12", "--seed", "1", "--output", str(base)]) == 0
        with Image.open(base.with_suffix(".jpg")) as image:
            assert image.size == (6, 6)

    def test_statistiques_ecrites_au_dela_du_seuil(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """Les statistiques s'ajoutent aux sorties normales, elles ne les remplacent pas."""
        monkeypatch.setattr(policy_mod, "STATS_ALWAYS_ABOVE", 5)
        base = tmp_path / "seuil"
        assert main(["run", "--n", "5", "--seed", "1", "--output", str(base)]) == 0
        assert base.with_suffix(".txt").exists()
        assert base.with_suffix(".jpg").exists()
        assert _stats_de(tmp_path, "seuil").exists()

    def test_pas_de_statistiques_pour_un_petit_labyrinthe(self, tmp_path: Path) -> None:
        """Sous tous les seuils, aucune sortie parasite ne doit apparaitre."""
        base = tmp_path / "ok"
        assert main(["run", "--n", "5", "--seed", "1", "--output", str(base)]) == 0
        assert base.with_suffix(".txt").exists()
        assert not _stats_de(tmp_path, "ok").exists()

    def test_generate_refuse_aussi(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """``generate`` applique la meme politique que ``run``."""
        monkeypatch.setattr(
            cli_mod, "_politique_export", lambda: ExportPolicy(max_ascii_side=3)
        )
        cible = tmp_path / "gen.txt"
        assert main(["generate", "--n", "5", "--seed", "1", "--output", str(cible)]) == 0
        assert not cible.exists()
        assert (tmp_path / "gen_statistiques.txt").exists()

    def test_convert_refuse_aussi(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        source = _generer(tmp_path / "maze.txt", n=5)
        monkeypatch.setattr(
            cli_mod, "_politique_export", lambda: ExportPolicy(max_ascii_side=3)
        )
        cible = tmp_path / "copie.txt"
        assert main(["convert", "--input", str(source), "--output", str(cible)]) == 0
        assert not cible.exists()
        assert (tmp_path / "copie_statistiques.txt").exists()


class TestConfirmation:
    """La question n'est posée que si elle sert, et jamais dans un test."""

    def test_petit_labyrinthe_ne_pose_aucune_question(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """Sous le seuil, pas d'interruption : les fichiers courants restent fluides."""
        monkeypatch.setattr(interaction_mod, "confirm", _explose)
        base = tmp_path / "fluide"
        assert main(["run", "--n", "5", "--seed", "1", "--output", str(base)]) == 0
        assert base.with_suffix(".txt").exists()

    def test_la_question_est_posee_au_dessus_du_seuil(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        monkeypatch.setattr(interaction_mod, "CONFIRM_THRESHOLD_BYTES", 0)
        messages: list[str] = []
        monkeypatch.setattr(
            interaction_mod,
            "confirm",
            lambda message, **kw: (messages.append(message), False)[1],
        )
        base = tmp_path / "gros"
        main(["run", "--n", "12", "--seed", "1", "--output", str(base)])

        assert messages, "la question aurait du etre posee"
        assert all("enregistrer" in message for message in messages)

    def test_repondre_non_ecrit_les_statistiques(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """Répondre « non » est un choix, pas une erreur : le code reste 0.

        Et il reste une trace : c'est tout l'intérêt du fichier de statistiques.
        """
        monkeypatch.setattr(interaction_mod, "CONFIRM_THRESHOLD_BYTES", 0)
        monkeypatch.setattr(interaction_mod, "confirm", lambda message, **kw: False)
        base = tmp_path / "refuse"
        assert main(["run", "--n", "12", "--seed", "1", "--output", str(base)]) == 0

        assert not base.with_suffix(".txt").exists()
        assert not base.with_suffix(".jpg").exists()
        stats = _stats_de(tmp_path, "refuse").read_text(encoding="ascii")
        assert "export_ascii: refuse" in stats
        assert "refuse par l'utilisateur" in stats

    def test_yes_ecrit_sans_demander(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """``--yes`` : l'utilisateur a répondu d'avance, on ne redemande pas."""
        monkeypatch.setattr(interaction_mod, "CONFIRM_THRESHOLD_BYTES", 0)
        monkeypatch.setattr(interaction_mod, "confirm", _explose)
        base = tmp_path / "force"
        assert main(["run", "--n", "12", "--seed", "1", "--yes", "--output", str(base)]) == 0
        assert base.with_suffix(".txt").exists()
        assert base.with_suffix(".jpg").exists()

    def test_stats_only_n_ecrit_que_les_statistiques(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        monkeypatch.setattr(interaction_mod, "confirm", _explose)
        base = tmp_path / "leger"
        assert main(
            ["run", "--n", "12", "--seed", "1", "--stats-only", "--output", str(base)]
        ) == 0
        assert not base.with_suffix(".txt").exists()
        assert not base.with_suffix(".jpg").exists()
        assert _stats_de(tmp_path, "leger").exists()

    def test_aucun_terminal_ecrit_quand_meme(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """Sans terminal joignable, on applique la politique au lieu de bloquer.

        Une tâche planifiée doit continuer de produire ses fichiers : elle ne
        peut pas répondre, mais la dimension du fichier ne posait pas problème.
        """
        monkeypatch.setattr(interaction_mod, "CONFIRM_THRESHOLD_BYTES", 0)
        monkeypatch.setattr(interaction_mod, "confirm", lambda message, **kw: None)
        base = tmp_path / "muet"
        assert main(["run", "--n", "12", "--seed", "1", "--output", str(base)]) == 0
        assert base.with_suffix(".txt").exists()
        assert base.with_suffix(".jpg").exists()

    def test_refus_utilisateur_et_refus_politique_se_distinguent(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """Deux causes de refus, deux raisons différentes dans le fichier."""
        monkeypatch.setattr(interaction_mod, "CONFIRM_THRESHOLD_BYTES", 0)
        monkeypatch.setattr(interaction_mod, "confirm", lambda message, **kw: False)
        main(["run", "--n", "12", "--seed", "1", "--output", str(tmp_path / "a")])
        utilisateur = _stats_de(tmp_path, "a").read_text(encoding="ascii")

        monkeypatch.setattr(
            cli_mod, "_politique_export", lambda: ExportPolicy(max_ascii_side=3)
        )
        main(["run", "--n", "12", "--seed", "1", "--output", str(tmp_path / "b")])
        politique = _stats_de(tmp_path, "b").read_text(encoding="ascii")

        assert "refuse par l'utilisateur" in utilisateur
        assert "refuse par l'utilisateur" not in politique


class TestGenerationRefusee:
    """Le cas qui plantait : un labyrinthe hors budget mémoire.

    Avant ce garde-fou, ``mazes run --n 100000`` mourait en ``MemoryError``
    après plusieurs minutes, sans message utile et sans rien avoir produit.
    """

    @pytest.fixture
    def budget_serre(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """Budget d'un octet : toute génération est hors budget, et rien n'est alloué."""
        monkeypatch.setenv(BUDGET_ENV_VAR, "1")

    def test_refuse_et_ecrit_les_statistiques(
        self, tmp_path: Path, budget_serre: None
    ) -> None:
        base = tmp_path / "trop_gros"
        assert main(["run", "--n", "12", "--seed", "1", "--output", str(base)]) == 1

        assert not base.with_suffix(".txt").exists()
        assert not base.with_suffix(".jpg").exists()
        stats = _stats_de(tmp_path, "trop_gros").read_text(encoding="ascii")
        assert "generation: refusee" in stats
        assert "generation_raison" in stats

    def test_le_message_dit_comment_faire_autrement(
        self, tmp_path: Path, capsys: pytest.CaptureFixture, budget_serre: None
    ) -> None:
        """Un refus sans issue est une impasse : le message doit en proposer une."""
        main(["run", "--n", "12", "--seed", "1", "--output", str(tmp_path / "x")])
        err = capsys.readouterr().err
        assert "budget" in err.lower()
        assert BUDGET_ENV_VAR in err
        assert "--n" in err

    def test_ne_conseille_pas_un_generateur_qui_echoue_aussi(
        self, tmp_path: Path, capsys: pytest.CaptureFixture, budget_serre: None
    ) -> None:
        """Avec un budget d'un octet, aucun generateur ne passe.

        Conseiller « essayez prim, le plus sobre » quand prim echoue lui aussi
        enverrait l'utilisateur dans le mur.
        """
        main(["run", "--n", "12", "--seed", "1", "--output", str(tmp_path / "x")])
        assert "Aucun générateur" in capsys.readouterr().err

    def test_conseille_un_generateur_qui_passe_vraiment(
        self, tmp_path: Path, capsys: pytest.CaptureFixture, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """Budget qui laisse passer prim et le backtracking, mais pas kruskal."""
        monkeypatch.setenv(BUDGET_ENV_VAR, str(200 * 1024 * 1024))
        main(
            [
                "run", "--n", "3000", "--generator", "kruskal", "--seed", "1",
                "--output", str(tmp_path / "x"),
            ]
        )
        err = capsys.readouterr().err
        assert "prim" in err or "recursive_backtracking" in err

    def test_generate_est_refuse_aussi(
        self, tmp_path: Path, budget_serre: None
    ) -> None:
        cible = tmp_path / "gen.txt"
        assert main(["generate", "--n", "12", "--output", str(cible)]) == 1
        assert not cible.exists()
        assert (tmp_path / "gen_statistiques.txt").exists()

    def test_le_refus_ne_laisse_pas_de_traceback(
        self, tmp_path: Path, capsys: pytest.CaptureFixture, budget_serre: None
    ) -> None:
        """Le code de retour doit venir du CLI, pas d'une exception echappee."""
        code = main(["run", "--n", "12", "--seed", "1", "--output", str(tmp_path / "x")])
        assert code == 1
        assert "Traceback" not in capsys.readouterr().err

    def test_un_budget_suffisant_laisse_passer(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """Le garde-fou ne doit pas refuser ce qui tient : sinon il ne sert a rien."""
        monkeypatch.setenv(BUDGET_ENV_VAR, str(64 * 1024**3))
        base = tmp_path / "ok"
        assert main(["run", "--n", "12", "--seed", "1", "--output", str(base)]) == 0
        assert base.with_suffix(".txt").exists()

    def test_kruskal_est_refuse_avant_prim(self) -> None:
        """Le modele n'est pas le meme pour tous : c'est tout l'interet du budget.

        A taille egale, Kruskal demande ~40 fois ce que demande Prim.
        """
        from mazes.budget import estimate_generation

        assert estimate_generation("kruskal", 5000) > 20 * estimate_generation(
            "prim", 5000
        )

    def test_resolution_refusee_avant_de_generer(self, tmp_path: Path) -> None:
        """Generer pendant des heures pour mourir dans le solveur serait absurde.

        Sous 2 Gio, Prim genere jusqu'a ``n = 28714`` mais A* ne resout que
        jusqu'a ``n = 13377`` : a ``n = 20000`` la commande doit refuser tout de
        suite, avant la moindre allocation.
        """
        base = tmp_path / "trop_grand"
        assert main(
            [
                "run", "--n", "20000", "--generator", "prim", "--solver", "astar",
                "--seed", "1", "--output", str(base),
            ]
        ) == 1

        assert not base.with_suffix(".txt").exists()
        stats = _stats_de(tmp_path, "trop_grand").read_text(encoding="ascii")
        assert "resolution: refusee" in stats
        assert "astar" in stats

    def test_le_message_de_resolution_propose_un_solveur_sobre(
        self, tmp_path: Path, capsys: pytest.CaptureFixture
    ) -> None:
        main(
            [
                "run", "--n", "20000", "--generator", "prim", "--solver", "astar",
                "--seed", "1", "--output", str(tmp_path / "x"),
            ]
        )
        err = capsys.readouterr().err
        assert "Résolution refusée" in err
        assert "recursive_backtracking" in err

    def test_budget_invalide_sort_en_code_2(
        self, tmp_path: Path, capsys: pytest.CaptureFixture, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        monkeypatch.setenv(BUDGET_ENV_VAR, "beaucoup")
        code = main(["generate", "--n", "12", "--output", str(tmp_path / "x.txt")])
        assert code == 2
        assert "Erreur" in capsys.readouterr().err
