"""WallGrid <-> image (Pillow).

Le prototype traçait un trait par mur, soit ~2n² appels à `line` : à
n = 1000 c'est très lent. Ici on écrit directement dans un buffer de
pixels noir et blanc (mode "1"), ce qui tient la charge, et le chemin
est rendu en couleur seulement si la taille de cellule le permet.
"""

from __future__ import annotations

from mazes.core.grid import Cell, WallGrid

try:
    from PIL import Image, ImageDraw
except ImportError:  # Pillow est optionnel tant qu'on reste en ASCII
    Image = None
    ImageDraw = None

WHITE = (255, 255, 255)
BLACK = (0, 0, 0)
RED = (220, 40, 40)


def _require_pillow() -> None:
    if Image is None:
        raise RuntimeError("Pillow n'est pas installé : pip install pillow")


def to_image(
    grid: WallGrid,
    path: list[Cell] | None = None,
    cell_size: int = 10,
    wall: int = 1,
):
    """Construit l'image du labyrinthe. `cell_size` = côté d'une cellule en px."""
    _require_pillow()
    n = grid.n
    pas = cell_size + wall
    largeur = n * pas + wall

    image = Image.new("RGB", (largeur, largeur), BLACK)
    dessin = ImageDraw.Draw(image)

    # On part d'une image entièrement noire (les murs), puis on "creuse"
    # chaque cellule et chaque passage en blanc : une seule passe.
    for r in range(n):
        for c in range(n):
            x = wall + c * pas
            y = wall + r * pas
            dessin.rectangle([x, y, x + cell_size - 1, y + cell_size - 1], fill=WHITE)
            if c + 1 < n and grid.is_open((r, c), (r, c + 1)):
                dessin.rectangle(
                    [x + cell_size, y, x + cell_size + wall - 1, y + cell_size - 1],
                    fill=WHITE,
                )
            if r + 1 < n and grid.is_open((r, c), (r + 1, c)):
                dessin.rectangle(
                    [x, y + cell_size, x + cell_size - 1, y + cell_size + wall - 1],
                    fill=WHITE,
                )

    # entrée et sortie
    dessin.rectangle([wall, 0, wall + cell_size - 1, wall - 1], fill=WHITE)
    x_sortie = wall + (n - 1) * pas
    dessin.rectangle(
        [x_sortie, largeur - wall, x_sortie + cell_size - 1, largeur - 1], fill=WHITE
    )

    if path:
        centre = lambda i: wall + i * pas + cell_size // 2  # noqa: E731
        points = [(centre(c), centre(r)) for r, c in path]
        epaisseur = max(1, cell_size // 3)
        if len(points) > 1:
            dessin.line(points, fill=RED, width=epaisseur)
        else:
            dessin.point(points, fill=RED)

    return image


def save_image(
    path_fichier: str,
    grid: WallGrid,
    path: list[Cell] | None = None,
    cell_size: int = 10,
) -> str:
    image = to_image(grid, path, cell_size=cell_size)
    if path_fichier.lower().endswith((".jpg", ".jpeg")):
        image = image.convert("RGB")
        image.save(path_fichier, quality=90)
    else:
        image.save(path_fichier)
    return path_fichier


def from_image(path_fichier: str, cell_size: int = 10, wall: int = 1) -> WallGrid:
    """Relit une image produite par `to_image` (mêmes paramètres)."""
    _require_pillow()
    image = Image.open(path_fichier).convert("L")
    largeur, _ = image.size
    pas = cell_size + wall
    n = (largeur - wall) // pas
    pixels = image.load()

    grid = WallGrid(n)
    seuil = 128
    for r in range(n):
        for c in range(n):
            x = wall + c * pas
            y = wall + r * pas
            if c + 1 < n and pixels[x + cell_size, y] > seuil:
                grid.carve((r, c), (r, c + 1))
            if r + 1 < n and pixels[x, y + cell_size] > seuil:
                grid.carve((r, c), (r + 1, c))
    return grid
