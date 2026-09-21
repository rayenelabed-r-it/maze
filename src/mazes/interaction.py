"""Confirmation avant d'écrire un gros fichier.

Un labyrinthe de ``n = 100000`` produit un ASCII de ``200001 x 200001``
caractères, soit ~37 Gio. Écrire ça sans rien demander est une façon efficace de
remplir un disque. Ce module pose la question, et laisse l'utilisateur décider.

Trois états, pas deux
---------------------
:func:`confirm` renvoie ``True``, ``False``, ou ``None``. ``None`` n'est pas
``False`` : le premier dit « aucun moyen de demander », le second « l'utilisateur
a dit non ». Les confondre ferait écrire en silence dans un cas et refuser dans
l'autre. :func:`should_write` propage cette distinction.

Où poser la question
--------------------
:func:`sources` les essaie dans l'ordre :

1. **``stdin``**, toujours en premier. Un tube ou un fichier redirigé peut porter
   la réponse : ``echo o | mazes run ...`` doit fonctionner, et lire ailleurs
   perdrait la réponse de l'utilisateur.
2. **La console du système** (``CONIN$``/``CONOUT$`` sous Windows, ``/dev/tty``
   ailleurs), si ``stdin`` s'est révélé épuisé. Elle reste attachée au processus
   même quand les flux sont redirigés, ce qui permet à ``mazes run > log.txt``
   d'afficher quand même la question.
3. Rien : l'appelant applique alors la politique d'export, qui sait réduire ou
   refuser sans personne pour répondre.

Ce module ne dépend d'aucun autre module du projet : c'est une feuille du graphe.
"""

from __future__ import annotations

import os
import sys
from collections.abc import Iterator
from typing import TextIO

__all__ = [
    "CONFIRM_THRESHOLD_BYTES",
    "MAX_ESSAIS",
    "NO_PROMPT_ENV_VAR",
    "OUI",
    "confirm",
    "console",
    "should_write",
    "sources",
]

#: Au-delà de cette taille estimée, l'écriture demande confirmation (256 Mio).
#:
#: **Lue dans le corps des fonctions, jamais en valeur par défaut.** Une
#: constante placée en défaut d'argument serait liée à l'import : la patcher
#: après coup n'aurait plus aucun effet, et les tests ne pourraient plus
#: déclencher le seuil sans écrire des fichiers de plusieurs centaines de Mio.
CONFIRM_THRESHOLD_BYTES = 256 * 1024 * 1024

#: Variable d'environnement qui fait taire la question (scripts, CI, hôte).
NO_PROMPT_ENV_VAR = "MAZES_NO_PROMPT"

#: Réponses acceptées, en minuscules.
OUI = frozenset({"o", "oui", "y", "yes"})
NON = frozenset({"n", "non", "no"})

#: Nombre de réponses incomprises avant de retenir le défaut.
MAX_ESSAIS = 3

#: Variable que pytest positionne pendant un test. Sa seule présence interdit de
#: chercher une console : voir :func:`sources`.
_PYTEST_ENV_VAR = "PYTEST_CURRENT_TEST"


def _isatty(flux: object) -> bool:
    """``flux`` est-il un terminal ? Ne lève jamais."""
    try:
        return bool(flux.isatty())  # type: ignore[attr-defined]
    except (AttributeError, ValueError, OSError):
        return False


def _a_un_fileno(flux: object) -> bool:
    """``flux`` est-il adossé à un descripteur de fichier réel ?

    Distingue un vrai flux redirigé (tube, fichier) d'un objet de test. Sous
    pytest, ``sys.stdin`` est un ``DontReadFromInput`` dont ``fileno()`` lève
    ``io.UnsupportedOperation`` -- sous-classe d'``OSError`` *et* de
    ``ValueError``, donc attrapée ici.
    """
    try:
        flux.fileno()  # type: ignore[attr-defined]
    except (AttributeError, ValueError, OSError):
        return False
    return True


def _ouvrir_terminal_de_controle() -> tuple[TextIO, TextIO] | None:
    """Ouvre le périphérique de console du système, ou ``None`` s'il n'existe pas.

    Les descripteurs restent ouverts : ils sont rendus à l'appelant, qui s'en
    sert pour poser la question. Un ``with`` les refermerait aussitôt.
    """
    try:
        if os.name == "nt":
            entree = open("CONIN$", encoding="utf-8", errors="replace")  # noqa: SIM115
            sortie = open("CONOUT$", "w", encoding="utf-8", errors="replace")  # noqa: SIM115
            return entree, sortie
        flux = open("/dev/tty", "r+", encoding="utf-8", errors="replace")  # noqa: SIM115
        return flux, flux
    except OSError:
        # Aucune console attachée : service, tâche planifiée, conteneur.
        return None


def console() -> tuple[TextIO, TextIO] | None:
    """Console du système, ou ``None``. Ne consulte pas ``stdin``.

    Voir :func:`sources` pour l'ordre complet des sources.
    """
    if os.environ.get(NO_PROMPT_ENV_VAR) or os.environ.get(_PYTEST_ENV_VAR):
        return None
    return _ouvrir_terminal_de_controle()


def sources() -> Iterator[tuple[TextIO, TextIO]]:
    """Sources d'entrée à essayer, dans l'ordre. Vide s'il ne faut pas demander.

    **L'ordre et les gardes ne sont pas négociables.** Chercher la console avant
    d'avoir écouté ``stdin`` perdrait une réponse envoyée par tube ; la chercher
    sous pytest ouvrirait ``CONIN$`` et bloquerait la suite de tests
    indéfiniment, faute de frappe qui viendrait jamais.
    """
    if os.environ.get(NO_PROMPT_ENV_VAR) or os.environ.get(_PYTEST_ENV_VAR):
        return

    yield sys.stdin, sys.stderr

    # ``stdin`` sans descripteur réel : objet de test, flux en mémoire. Il n'y a
    # aucune console légitime à chercher derrière -- et en chercher une serait le
    # seul moyen de bloquer un appelant qui a remplacé ``sys.stdin``.
    if not (_isatty(sys.stdin) or _a_un_fileno(sys.stdin)):
        return

    paire = _ouvrir_terminal_de_controle()
    if paire is not None:
        yield paire


def _etiquette(defaut: bool) -> str:
    """Invite affichée entre crochets, la majuscule marquant le défaut."""
    return "O/n" if defaut else "o/N"


def _demander(
    message: str,
    stream_in: TextIO,
    stream_out: TextIO,
    defaut: bool,
) -> bool | None:
    """Boucle de saisie bornée sur une source.

    Renvoie ``None`` quand le flux est épuisé : c'est le signal pour passer à la
    source suivante, et non une réponse.
    """
    for _ in range(MAX_ESSAIS):
        stream_out.write(f"{message} [{_etiquette(defaut)}] ")
        stream_out.flush()

        try:
            ligne = stream_in.readline()
        except (OSError, ValueError):
            return None

        if ligne == "":
            # Flux épuisé : redirection depuis /dev/null, tube fermé, ou rien
            # n'a été fourni. Insister bouclerait indéfiniment.
            stream_out.write("\n")
            return None

        reponse = ligne.strip().lower()
        if reponse in OUI:
            return True
        if reponse in NON:
            return False
        if not reponse:
            return defaut
        stream_out.write("Reponse attendue : o (oui) ou n (non).\n")

    return defaut


def confirm(
    message: str,
    *,
    stream_in: TextIO | None = None,
    stream_out: TextIO | None = None,
    defaut: bool = False,
) -> bool | None:
    """Pose une question oui/non. ``None`` quand aucun moyen de demander.

    ``defaut`` est la réponse retenue si l'utilisateur tape Entrée sans rien
    écrire. Il vaut ``False`` par défaut : une touche Entrée accidentelle ne doit
    pas déclencher l'écriture de plusieurs gigaoctets.

    Les flux sont injectables pour les tests. Les fournir court-circuite
    :func:`sources` : un flux explicite est la seule source consultée, et son
    épuisement retombe sur ``defaut`` au lieu d'aller chercher une console.
    """
    if (stream_in is None) != (stream_out is None):
        raise ValueError("stream_in et stream_out doivent etre fournis ensemble")

    if stream_in is not None and stream_out is not None:
        verdict = _demander(message, stream_in, stream_out, defaut)
        return defaut if verdict is None else verdict

    for entree, sortie in sources():
        verdict = _demander(message, entree, sortie, defaut)
        if verdict is not None:
            return verdict
    return None


def should_write(
    octets: int,
    message: str,
    *,
    force: bool = False,
    stats_only: bool = False,
) -> bool | None:
    """Faut-il écrire un fichier de ``octets`` octets ?

    * ``True`` -- écrire ;
    * ``False`` -- ne pas écrire ;
    * ``None`` -- aucun moyen de demander : à l'appelant d'appliquer la politique
      d'export, qui sait réduire ou refuser sans personne pour répondre.
    """
    if stats_only:
        return False
    if force:
        return True
    # Seuil relu ici pour que les tests puissent le ramener à zéro.
    if octets <= CONFIRM_THRESHOLD_BYTES:
        return True
    return confirm(message)
