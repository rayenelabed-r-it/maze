"""Demande de confirmation avant d'écrire un gros fichier.

Au-delà de :data:`CONFIRM_THRESHOLD_BYTES`, le CLI demande l'accord de
l'utilisateur. La question est posée sur ``stdin`` s'il est utilisable, sinon
sur le périphérique de console du système (``CONIN$`` sous Windows, ``/dev/tty``
ailleurs), qui reste attaché même quand les flux sont redirigés.
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
#: Lue dans le corps des fonctions, pour que les tests puissent la ramener à zéro.
CONFIRM_THRESHOLD_BYTES = 256 * 1024 * 1024

#: Variable d'environnement qui fait taire la question (scripts, CI).
NO_PROMPT_ENV_VAR = "MAZES_NO_PROMPT"

OUI = frozenset({"o", "oui", "y", "yes"})
NON = frozenset({"n", "non", "no"})

#: Nombre de réponses incomprises avant de retenir le défaut.
MAX_ESSAIS = 3

#: Positionnée par pytest pendant un test.
_PYTEST_ENV_VAR = "PYTEST_CURRENT_TEST"


def _isatty(flux: object) -> bool:
    """``flux`` est-il un terminal ? Ne lève jamais."""
    try:
        return bool(flux.isatty())  # type: ignore[attr-defined]
    except (AttributeError, ValueError, OSError):
        return False


def _a_un_fileno(flux: object) -> bool:
    """``flux`` est-il adossé à un descripteur de fichier réel ?

    Sous pytest, ``sys.stdin`` est un objet dont ``fileno()`` lève
    ``io.UnsupportedOperation``, sous-classe d'``OSError`` et de ``ValueError``.
    """
    try:
        flux.fileno()  # type: ignore[attr-defined]
    except (AttributeError, ValueError, OSError):
        return False
    return True


def _ouvrir_terminal_de_controle() -> tuple[TextIO, TextIO] | None:
    """Ouvre le périphérique de console, ou ``None`` s'il n'y en a pas.

    Les descripteurs restent ouverts : ils sont rendus à l'appelant.
    """
    try:
        if os.name == "nt":
            entree = open("CONIN$", encoding="utf-8", errors="replace")  # noqa: SIM115
            sortie = open("CONOUT$", "w", encoding="utf-8", errors="replace")  # noqa: SIM115
            return entree, sortie
        flux = open("/dev/tty", "r+", encoding="utf-8", errors="replace")  # noqa: SIM115
        return flux, flux
    except OSError:
        return None


def console() -> tuple[TextIO, TextIO] | None:
    """Console du système, ou ``None``. Ne consulte pas ``stdin``."""
    if os.environ.get(NO_PROMPT_ENV_VAR) or os.environ.get(_PYTEST_ENV_VAR):
        return None
    return _ouvrir_terminal_de_controle()


def sources() -> Iterator[tuple[TextIO, TextIO]]:
    """Sources d'entrée à essayer, ``stdin`` d'abord puis la console.

    L'ordre compte : aller chercher la console avant d'écouter ``stdin``
    perdrait une réponse envoyée par tube. La console n'est tentée que si
    ``stdin`` est un vrai flux et non un objet de test.
    """
    if os.environ.get(NO_PROMPT_ENV_VAR) or os.environ.get(_PYTEST_ENV_VAR):
        return

    yield sys.stdin, sys.stderr

    if not (_isatty(sys.stdin) or _a_un_fileno(sys.stdin)):
        return

    paire = _ouvrir_terminal_de_controle()
    if paire is not None:
        yield paire


def _etiquette(defaut: bool) -> str:
    """Invite entre crochets, la majuscule marquant le défaut."""
    return "O/n" if defaut else "o/N"


def _demander(
    message: str,
    stream_in: TextIO,
    stream_out: TextIO,
    defaut: bool,
) -> bool | None:
    """Boucle de saisie sur une source. ``None`` quand le flux est épuisé."""
    for _ in range(MAX_ESSAIS):
        stream_out.write(f"{message} [{_etiquette(defaut)}] ")
        stream_out.flush()

        try:
            ligne = stream_in.readline()
        except (OSError, ValueError):
            return None

        if ligne == "":
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
    """Pose une question oui/non.

    ``None`` signifie qu'aucune source n'est disponible, ce qui n'est pas la même
    chose que ``False``. ``defaut`` vaut ``False`` : une touche Entrée
    accidentelle ne doit pas déclencher l'écriture de plusieurs gigaoctets.

    Fournir les deux flux court-circuite :func:`sources` et n'essaie qu'eux.
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

    ``True`` écrire, ``False`` ne pas écrire, ``None`` aucun moyen de demander
    et l'appelant applique la politique d'export.
    """
    if stats_only:
        return False
    if force:
        return True
    if octets <= CONFIRM_THRESHOLD_BYTES:
        return True
    return confirm(message)
