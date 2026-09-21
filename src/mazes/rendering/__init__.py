"""Rendu d'un labyrinthe : texte ASCII, image, et politique d'export.

* :mod:`mazes.rendering.ascii`  -- grille <-> texte ;
* :mod:`mazes.rendering.image`  -- grille <-> image ;
* :mod:`mazes.rendering.policy` -- que peut-on écrire, à quelle taille.
"""

from mazes.rendering.ascii import (
    DEFAULT_CHARSET,
    ENCODING,
    Charset,
    iter_ascii_lines,
    parse_ascii,
    print_preview,
    read_ascii,
    render_to_string,
    write_ascii,
)
from mazes.rendering.image import (
    BAND_HEIGHT,
    DEFAULT_STYLE,
    DENSE_MEMORY_BUDGET,
    EXPLORED_MARK,
    FREE,
    PATH_MARK,
    WALL,
    Couleur,
    ImageStyle,
    choose_format,
    render_dense,
    render_dense_banded,
    subsample_dense,
    to_image,
    write_image,
)
from mazes.rendering.policy import (
    MAX_ASCII_SIDE,
    MAX_IMAGE_SIDE,
    ExportPlan,
    ExportPolicy,
    subsample_factor,
)

__all__ = [
    "BAND_HEIGHT",
    "DEFAULT_CHARSET",
    "DEFAULT_STYLE",
    "DENSE_MEMORY_BUDGET",
    "ENCODING",
    "EXPLORED_MARK",
    "FREE",
    "MAX_ASCII_SIDE",
    "MAX_IMAGE_SIDE",
    "PATH_MARK",
    "WALL",
    "Charset",
    "Couleur",
    "ExportPlan",
    "ExportPolicy",
    "ImageStyle",
    "choose_format",
    "iter_ascii_lines",
    "parse_ascii",
    "print_preview",
    "read_ascii",
    "render_dense",
    "render_dense_banded",
    "render_to_string",
    "subsample_dense",
    "subsample_factor",
    "to_image",
    "write_ascii",
    "write_image",
]
