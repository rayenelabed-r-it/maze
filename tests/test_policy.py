"""Tests de la politique d'export.

Ce qu'on vérifie, et pourquoi
-----------------------------
``ExportPolicy`` a longtemps été du code mort : implémenté et documenté, mais
appelé nulle part. Ces tests le figent **avant** de le brancher sur le CLI, pour
que le câblage s'appuie sur quelque chose de vérifié plutôt que sur du code
jamais exécuté.

Le piège à éviter
-----------------
Les deux régimes mémoire de l'image ne se ressemblent pas : à pleine résolution
un JPEG de labyrinthe pèse ~1.14 octet par pixel, mais dès que la réduction
s'applique la quasi-totalité de l'image devient blanche et le poids tombe à
~0.03. Se tromper de branche, c'est annoncer 930 Mio là où le fichier en fait
27. Les tests de :class:`TestEstimation` verrouillent la bascule.

La falaise de ``n = 16383`` à ``n = 16384``
-------------------------------------------
``image_scale`` passe de 1 à 2 quand le côté dépasse 32768, et l'estimation
chute d'un facteur ~90. Ce n'est pas un artefact du modèle : c'est le
comportement réel de ``subsample_dense``, qui réduit par minimum de bloc.
"""

from __future__ import annotations

import pytest

from mazes.rendering.policy import (
    IMAGE_BYTES_PER_PIXEL,
    IMAGE_BYTES_PER_PIXEL_REDUCED,
    MAX_ASCII_SIDE,
    MAX_IMAGE_SIDE,
    STATS_ALWAYS_ABOVE,
    ExportPolicy,
    format_bytes,
    subsample_factor,
)

#: Côté dense au-delà duquel ``write_image`` réduit l'image.
SEUIL_IMAGE_SIDE = MAX_IMAGE_SIDE + 1  # 32769, soit n = 16384


class TestSubsampleFactor:
    """``subsample_factor`` est la brique de toutes les décisions de réduction."""

    def test_sous_la_limite_est_identite(self) -> None:
        assert subsample_factor(20001, 32768) == 1

    def test_juste_a_la_limite_est_identite(self) -> None:
        """L'égalité ne réduit pas : « sous la limite » est inclusif."""
        assert subsample_factor(32768, 32768) == 1

    def test_juste_au_dessus_arrondit_a_deux(self) -> None:
        assert subsample_factor(32769, 32768) == 2

    @pytest.mark.parametrize(
        ("side", "limit", "attendu"),
        [(20001, 8000, 3), (200001, 32768, 7), (100, 3, 34)],
    )
    def test_arrondit_au_superieur(self, side: int, limit: int, attendu: int) -> None:
        """``ceil`` et non ``floor`` : sous-estimer la réduction dépasserait la limite."""
        assert subsample_factor(side, limit) == attendu

    def test_limite_invalide(self) -> None:
        with pytest.raises(ValueError):
            subsample_factor(10, 0)


class TestPlan:
    """``plan(n)`` décide de ce qui sera écrit, avant tout calcul."""

    def test_petit_labyrinthe_est_complet(self) -> None:
        plan = ExportPolicy().plan(10)
        assert plan.ascii_full
        assert not plan.ascii_refused
        assert plan.ascii_scale == 1
        assert plan.image_scale == 1
        assert not plan.write_stats

    def test_juste_sous_la_limite_ascii(self) -> None:
        """``n = 3999`` donne un côté de 7999, encore sous la limite de 8000."""
        plan = ExportPolicy().plan(3999)
        assert plan.grid_side == MAX_ASCII_SIDE - 1
        assert plan.ascii_full
        assert not plan.ascii_refused

    def test_ascii_refuse_juste_au_dessus(self) -> None:
        """``n = 4000`` donne un côté de 8001 : l'ASCII 1:1 est refusé, pas réduit."""
        plan = ExportPolicy().plan(4000)
        assert plan.grid_side == MAX_ASCII_SIDE + 1
        assert not plan.ascii_full
        assert plan.ascii_refused, "sans ascii_subsample, rien ne doit etre ecrit"

    def test_ascii_reduit_quand_le_sous_echantillonnage_est_autorise(self) -> None:
        """Avec ``ascii_subsample``, le même ``n`` donne une réduction et non un refus."""
        plan = ExportPolicy(ascii_subsample=True).plan(4000)
        assert not plan.ascii_full
        assert not plan.ascii_refused
        assert plan.ascii_scale > 1
        assert plan.projected_ascii_side <= MAX_ASCII_SIDE

    def test_image_reduite_a_cent_mille(self) -> None:
        """``n = 100000`` : côté 200001, réduit x7 pour retomber sous 32768."""
        plan = ExportPolicy().plan(100000)
        assert plan.grid_side == 200001
        assert plan.image_scale == 7
        assert plan.projected_image_side == 200001 // 7

    def test_statistiques_au_dela_du_seuil(self) -> None:
        """Le seuil porte sur le **côté**, pas sur ``n`` : il bascule entre 999 et 1000."""
        assert ExportPolicy().plan(999).grid_side == STATS_ALWAYS_ABOVE - 1
        assert not ExportPolicy().plan(999).write_stats
        assert ExportPolicy().plan(1000).grid_side == STATS_ALWAYS_ABOVE + 1
        assert ExportPolicy().plan(1000).write_stats

    @pytest.mark.parametrize("n", [0, -1])
    def test_n_invalide(self, n: int) -> None:
        with pytest.raises(ValueError):
            ExportPolicy().plan(n)

    def test_taille_ascii_est_le_plein_1_1(self) -> None:
        """``ascii_bytes`` décrit toujours l'ASCII 1:1, même refusé.

        C'est ce que la politique ne veut pas écrire : le chiffre sert à prévenir
        l'utilisateur, pas à décrire le fichier réduit.
        """
        plan = ExportPolicy().plan(100000)
        assert plan.ascii_bytes == 200001 * 200002


class TestEstimation:
    """Les estimations de taille, et la bascule entre les deux régimes d'image."""

    def test_estimate_ascii_bytes(self) -> None:
        assert ExportPolicy().estimate_ascii_bytes(1000) == 2001 * 2002

    def test_estimate_dense_bytes(self) -> None:
        assert ExportPolicy().estimate_dense_bytes(1000) == 2001**2

    def test_image_pleine_resolution_est_mesuree(self) -> None:
        """À ``image_scale == 1``, l'image garde ses murs : ~1.14 octet/pixel."""
        politique = ExportPolicy()
        attendu = int(201 * 201 * IMAGE_BYTES_PER_PIXEL)
        assert politique.estimate_image_bytes(100) == attendu

    def test_image_reduite_bascule_de_regime(self) -> None:
        """À ``image_scale > 1``, l'image blanchit : ~0.05 octet/pixel."""
        politique = ExportPolicy()
        cote_reduit = 32769 // 2
        attendu = int(cote_reduit * cote_reduit * IMAGE_BYTES_PER_PIXEL_REDUCED)
        assert politique.estimate_image_bytes(16384) == attendu

    def test_la_falaise_au_passage_du_seuil(self) -> None:
        """Passer de 16383 à 16384 fait chuter l'image estimée d'un facteur ~12.

        Contre-intuitif : un labyrinthe deux fois plus grand donne une image
        bien plus légère. C'est réel, et c'est ce que le modèle doit refléter.
        """
        politique = ExportPolicy()
        cote_limite = SEUIL_IMAGE_SIDE - 2  # 32767, encore en pleine résolution
        pleine = politique.plan(16383)
        reduite = politique.plan(16384)

        assert pleine.grid_side == cote_limite
        assert pleine.image_scale == 1
        assert reduite.image_scale == 2
        assert reduite.image_bytes * 5 < pleine.image_bytes

    def test_written_bytes_ignore_l_ascii_refuse(self) -> None:
        """L'ASCII refusé ne compte pas : ``written_bytes`` décrit ce qui sera écrit."""
        plan = ExportPolicy().plan(100000)
        assert plan.ascii_refused
        assert plan.written_bytes == plan.image_bytes

    def test_written_bytes_somme_les_deux(self) -> None:
        plan = ExportPolicy().plan(10)
        assert plan.written_bytes == plan.ascii_bytes + plan.image_bytes


class TestFormatBytes:
    """``format_bytes`` alimente les messages affichés à l'utilisateur."""

    @pytest.mark.parametrize(
        ("octets", "attendu"),
        [
            (0, "0 o"),
            (999, "999 o"),
            (1024, "1.0 Kio"),
            (1536, "1.5 Kio"),
            (1024**2, "1.0 Mio"),
            (61_000_000, "58.2 Mio"),
            (1024**3, "1.0 Gio"),
            (40_000_000_000, "37.3 Gio"),
        ],
    )
    def test_unites(self, octets: int, attendu: str) -> None:
        assert format_bytes(octets) == attendu

    def test_taille_negative(self) -> None:
        with pytest.raises(ValueError):
            format_bytes(-1)


class TestDescribe:
    """``describe()`` finit dans le fichier de statistiques : il doit être ASCII pur."""

    def test_pas_d_accent(self) -> None:
        """Un accent ajouté ici planterait à l'écriture en production, pas dans les tests.

        ``write_stats`` encode en ASCII strict (``rendering/ascii.ENCODING``).
        """
        for n in (10, 4000, 100000):
            assert ExportPolicy().plan(n).describe().isascii()

    def test_distingue_refuse_de_reduit(self) -> None:
        """Les deux cas où ``ascii_full`` est faux ne doivent pas être confondus.

        Sans cette distinction, la console annonçait « ASCII réduit x26 » alors
        qu'aucun fichier ASCII n'était écrit.
        """
        refuse = ExportPolicy().plan(100000).describe()
        reduit = ExportPolicy(ascii_subsample=True).plan(100000).describe()
        assert "refuse" in refuse
        assert "reduit x" in reduit
        assert "refuse" not in reduit
