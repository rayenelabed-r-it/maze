"""Tests de la confirmation interactive.

Ce qu'on vérifie, et pourquoi
-----------------------------
Ce module touche à ``stdin`` : c'est le seul endroit du projet où un bug produit
un blocage plutôt qu'une erreur, et une suite qui attend une frappe ne se voit
pas. Sous pytest, ``sys.stdin`` est un objet dont ``fileno()`` lève, ce dont une
détection naïve déduirait « entrée redirigée », avant d'ouvrir ``CONIN$`` et
d'attendre indéfiniment.
``test_stdin_sans_fileno_ne_cherche_pas_de_console`` remplace l'ouvreur par une
fonction qui échoue si on l'appelle, et verrouille l'ordre des vérifications.

Deux états à ne pas confondre
-----------------------------
``confirm`` renvoie ``None`` quand aucune source n'existe, et ``False`` quand
l'utilisateur a dit non. Plusieurs tests vérifient que les deux restent
distincts jusqu'au bout de la chaîne.
"""

from __future__ import annotations

import sys
from pathlib import Path

import pytest

from mazes import interaction
from mazes.interaction import (
    MAX_ESSAIS,
    NO_PROMPT_ENV_VAR,
    confirm,
    console,
    should_write,
    sources,
)


class _Entree:
    """Entrée scriptée : rend les réponses fournies, puis épuise le flux."""

    def __init__(self, *reponses: str) -> None:
        self._lignes = list(reponses)

    def readline(self) -> str:
        return self._lignes.pop(0) if self._lignes else ""


class _EntreeEnPanne:
    """Entrée qui échoue à la lecture, comme un tube cassé."""

    def readline(self) -> str:
        raise OSError("tube ferme")


class _Sortie:
    """Sortie en mémoire, pour inspecter ce qui a été affiché."""

    def __init__(self) -> None:
        self.texte = ""

    def write(self, texte: str) -> None:
        self.texte += texte

    def flush(self) -> None:
        pass


class _StdinSansFileno:
    """Reproduit le ``DontReadFromInput`` de pytest."""

    def isatty(self) -> bool:
        return False

    def fileno(self) -> int:
        raise OSError("redirected stdin is pseudofile, has no fileno()")


class _StdinTerminal:
    """Un ``stdin`` qui se déclare terminal."""

    def __init__(self, *reponses: str) -> None:
        self._entree = _Entree(*reponses)

    def isatty(self) -> bool:
        return True

    def fileno(self) -> int:
        return 0

    def readline(self) -> str:
        return self._entree.readline()


def _explose(*args: object, **kw: object) -> bool:
    """Ouvreur de secours qui échoue : appelé, c'est que la détection est fausse."""
    raise AssertionError("le terminal de controle ne doit pas etre ouvert ici")


class TestSources:
    """L'ordre des sources d'entrée, et les gardes qui empêchent tout blocage."""

    def test_sous_pytest_aucune_source(self) -> None:
        """Sous pytest, aucune question ne doit etre posee, meme avec ``-s``.

        Avec ``-s``, pytest laisse le vrai ``stdin`` en place : sans le verrou
        ``PYTEST_CURRENT_TEST``, la question serait posee et la suite
        attendrait une frappe.
        """
        assert list(sources()) == []
        assert console() is None

    def test_variable_d_environnement(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """``MAZES_NO_PROMPT`` fait taire la question : l'echappatoire des scripts."""
        monkeypatch.setenv(NO_PROMPT_ENV_VAR, "1")
        monkeypatch.setattr(sys, "stdin", _StdinTerminal("o\n"))
        assert list(sources()) == []

    def test_stdin_interactif_est_la_premiere_source(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """Cas courant : ``stdin`` est le terminal, on s'en sert directement."""
        monkeypatch.delenv("PYTEST_CURRENT_TEST", raising=False)
        faux = _StdinTerminal("o\n")
        monkeypatch.setattr(sys, "stdin", faux)
        assert next(iter(sources()))[0] is faux

    def test_stdin_sans_fileno_ne_cherche_pas_de_console(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """LE test anti-blocage.

        ``stdin`` non terminal et sans descripteur reel : c'est un objet de test.
        Chercher ``CONIN$`` derriere bloquerait la suite indefiniment.
        """
        monkeypatch.delenv("PYTEST_CURRENT_TEST", raising=False)
        monkeypatch.setattr(sys, "stdin", _StdinSansFileno())
        monkeypatch.setattr(interaction, "_ouvrir_terminal_de_controle", _explose)
        assert len(list(sources())) == 1

    def test_la_console_vient_apres_stdin(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """Entree redirigee depuis un vrai fichier : la console reste joignable."""
        monkeypatch.delenv("PYTEST_CURRENT_TEST", raising=False)
        fausse = (_Entree("o\n"), _Sortie())
        monkeypatch.setattr(interaction, "_ouvrir_terminal_de_controle", lambda: fausse)
        with open(__file__, encoding="utf-8") as vrai_fichier:
            monkeypatch.setattr(sys, "stdin", vrai_fichier)
            liste = list(sources())
            assert len(liste) == 2
            assert liste[0][0] is vrai_fichier
            assert liste[1] is fausse

    def test_aucune_console_renvoie_stdin_seul(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """Sans console attachee (service, conteneur), l'ouverture echoue proprement."""
        monkeypatch.setattr(interaction, "_ouvrir_terminal_de_controle", lambda: None)
        monkeypatch.delenv("PYTEST_CURRENT_TEST", raising=False)
        with open(__file__, encoding="utf-8") as vrai_fichier:
            monkeypatch.setattr(sys, "stdin", vrai_fichier)
            assert len(list(sources())) == 1


class TestConfirm:
    """La boucle de saisie, avec des flux injectes."""

    @pytest.mark.parametrize("reponse", ["o", "O", "oui", "y", "yes", " oui "])
    def test_reponses_oui(self, reponse: str) -> None:
        sortie = _Sortie()
        assert confirm("Question ?", stream_in=_Entree(reponse + "\n"), stream_out=sortie) is True

    @pytest.mark.parametrize("reponse", ["n", "N", "non", "no", " NON "])
    def test_reponses_non(self, reponse: str) -> None:
        sortie = _Sortie()
        assert confirm("Question ?", stream_in=_Entree(reponse + "\n"), stream_out=sortie) is False

    def test_reponse_vide_retient_le_defaut(self) -> None:
        """Entree seule : on retient le defaut, sans reposer la question."""
        sortie = _Sortie()
        assert confirm("Q ?", stream_in=_Entree("\n"), stream_out=sortie) is False
        assert sortie.texte.count("Q ?") == 1

    def test_defaut_vrai(self) -> None:
        assert confirm("Q ?", stream_in=_Entree("\n"), stream_out=_Sortie(), defaut=True)

    def test_entree_epuisee_retient_le_defaut(self) -> None:
        """Flux epuise : insister bouclerait a l'infini."""
        sortie = _Sortie()
        assert confirm("Q ?", stream_in=_Entree(), stream_out=sortie) is False
        assert sortie.texte.count("Q ?") == 1

    def test_entree_en_erreur_retient_le_defaut(self) -> None:
        """Tube casse : on ne fait pas planter la commande pour une question."""
        assert confirm("Q ?", stream_in=_EntreeEnPanne(), stream_out=_Sortie()) is False

    def test_reponse_invalide_puis_valide(self) -> None:
        """Une reponse incomprise est signalee, puis la question est reposee."""
        sortie = _Sortie()
        resultat = confirm("Q ?", stream_in=_Entree("peut-etre\nn\n"), stream_out=sortie)
        assert resultat is False
        assert "Reponse attendue" in sortie.texte
        assert sortie.texte.count("Q ?") == 2

    def test_essais_epuises_retient_le_defaut(self) -> None:
        """Apres ``MAX_ESSAIS`` reponses incomprises, on abandonne au defaut."""
        sortie = _Sortie()
        # Des lignes distinctes : une seule chaine serait rendue d'un bloc par
        # ``readline`` et le compte d'essais ne voudrait plus rien dire.
        reponses = ["bof\n"] * (MAX_ESSAIS + 2)
        assert confirm("Q ?", stream_in=_Entree(*reponses), stream_out=sortie) is False
        assert sortie.texte.count("Q ?") == MAX_ESSAIS

    def test_le_message_est_affiche(self) -> None:
        sortie = _Sortie()
        confirm("Enregistrer ce fichier ?", stream_in=_Entree("o\n"), stream_out=sortie)
        assert "Enregistrer ce fichier ?" in sortie.texte

    def test_un_seul_flux_leve(self) -> None:
        """Fournir l'entree sans la sortie n'a pas de sens : erreur explicite."""
        with pytest.raises(ValueError):
            confirm("Q ?", stream_in=_Entree("o\n"))
        with pytest.raises(ValueError):
            confirm("Q ?", stream_out=_Sortie())

    def test_sans_source_renvoie_none(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """``None`` dit « on ne peut pas demander », et non « non »."""
        monkeypatch.setattr(interaction, "sources", lambda: iter(()))
        assert confirm("Q ?") is None

    def test_la_reponse_d_un_tube_gagne_sur_la_console(
        self, monkeypatch: pytest.MonkeyPatch, tmp_path: Path
    ) -> None:
        """``echo n | mazes run ...`` : la reponse fournie ne doit pas etre perdue.

        C'est le defaut que ce test verrouille. Chercher la console avant
        d'ecouter ``stdin`` ignorerait le tube : l'utilisateur aurait repondu
        « non » et le fichier serait ecrit quand meme.
        """
        monkeypatch.delenv("PYTEST_CURRENT_TEST", raising=False)
        reponses = tmp_path / "reponses.txt"
        reponses.write_text("n\n", encoding="utf-8")
        # Si la console etait consultee, ce test echouerait au lieu de repondre.
        monkeypatch.setattr(interaction, "_ouvrir_terminal_de_controle", _explose)
        with open(reponses, encoding="utf-8") as flux:
            monkeypatch.setattr(sys, "stdin", flux)
            assert confirm("Q ?") is False


class TestShouldWrite:
    """``should_write`` combine seuil, drapeaux et question."""

    def test_sous_le_seuil_ne_demande_rien(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setattr(interaction, "confirm", _explose)
        assert should_write(1024, "Q ?") is True

    def test_juste_au_seuil_ne_demande_rien(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setattr(interaction, "confirm", _explose)
        assert should_write(interaction.CONFIRM_THRESHOLD_BYTES, "Q ?") is True

    def test_au_dessus_du_seuil_demande(self, monkeypatch: pytest.MonkeyPatch) -> None:
        recu: list[str] = []
        monkeypatch.setattr(
            interaction, "confirm", lambda message, **kw: recu.append(message) or True
        )
        assert should_write(interaction.CONFIRM_THRESHOLD_BYTES + 1, "Q ?") is True
        assert recu == ["Q ?"]

    def test_seuil_relu_a_chaque_appel(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """Le seuil est lu dans le corps : patche a zero, il declenche la question.

        Une constante en valeur par defaut serait liee a l'import et ce test
        n'aurait aucun effet.
        """
        monkeypatch.setattr(interaction, "CONFIRM_THRESHOLD_BYTES", 0)
        monkeypatch.setattr(interaction, "confirm", lambda message, **kw: False)
        assert should_write(1, "Q ?") is False

    def test_reponse_non(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setattr(interaction, "CONFIRM_THRESHOLD_BYTES", 0)
        monkeypatch.setattr(interaction, "confirm", lambda message, **kw: False)
        assert should_write(1024, "Q ?") is False

    def test_force_ne_demande_rien(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """``--yes`` : l'utilisateur a deja repondu, on ne redemande pas."""
        monkeypatch.setattr(interaction, "CONFIRM_THRESHOLD_BYTES", 0)
        monkeypatch.setattr(interaction, "confirm", _explose)
        assert should_write(10**12, "Q ?", force=True) is True

    def test_stats_only_ne_demande_rien(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setattr(interaction, "CONFIRM_THRESHOLD_BYTES", 0)
        monkeypatch.setattr(interaction, "confirm", _explose)
        assert should_write(10**12, "Q ?", stats_only=True) is False

    def test_stats_only_prime_sur_force(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """``--stats-only`` veut dire « seulement les stats », meme avec ``--yes``."""
        monkeypatch.setattr(interaction, "CONFIRM_THRESHOLD_BYTES", 0)
        assert should_write(10**12, "Q ?", force=True, stats_only=True) is False

    def test_sans_terminal_propage_none(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """``None`` doit remonter tel quel : l'appelant appliquera la politique."""
        monkeypatch.setattr(interaction, "CONFIRM_THRESHOLD_BYTES", 0)
        monkeypatch.setattr(interaction, "confirm", lambda message, **kw: None)
        assert should_write(10**12, "Q ?") is None
