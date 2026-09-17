"""ExportPolicy : ce qu'on s'autorise à écrire, et à quelle taille.

Sans garde-fou, `mazes generate --n 5000 --image` produit une image de
plusieurs gigaoctets ou remplit le terminal de 10 001 lignes. La politique
décide à la place de l'utilisateur, et explique son choix.
"""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class ExportPolicy:
    max_ascii_print: int = 60        # au-delà, on écrit un fichier plutôt qu'afficher
    max_image_pixels: int = 12_000   # côté max de l'image produite
    min_cell_size: int = 1

    def should_print(self, n: int) -> bool:
        return n <= self.max_ascii_print

    def cell_size(self, n: int, demande: int | None = None) -> int:
        """Taille de cellule tenant dans la limite de pixels."""
        taille = demande if demande is not None else max(1, 800 // max(n, 1))
        while taille > self.min_cell_size and n * (taille + 1) + 1 > self.max_image_pixels:
            taille -= 1
        return max(self.min_cell_size, taille)

    def explain(self, n: int) -> str:
        if self.should_print(n):
            return f"n = {n} : affichage direct possible."
        return (
            f"n = {n} : {2 * n + 1} lignes à l'écran, on écrit un fichier à la place."
        )


DEFAULT_POLICY = ExportPolicy()
