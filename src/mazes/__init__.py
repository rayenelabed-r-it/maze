"""Amazing-Mazes : generation et resolution de labyrinthes parfaits.

Ce paquet regroupe tout le projet :

* :mod:`mazes.core`       -- modele memoire compact et structures de base ;
* :mod:`mazes.generators` -- algorithmes de generation (Recursive Backtracking, Kruskal) ;
* :mod:`mazes.solvers`    -- algorithmes de resolution (Recursive Backtracking, A*) ;
* :mod:`mazes.rendering`  -- export ASCII et image, politique de taille, statistiques ;
* :mod:`mazes.budget`     -- budget memoire : refuse un calcul hors de portee ;
* :mod:`mazes.interaction` -- confirmation avant d'ecrire un gros fichier ;
* :mod:`mazes.metrics`    -- mesure du temps et de la memoire ;
* :mod:`mazes.cli`        -- interface en ligne de commande.

Exemple minimal
---------------
::

    from mazes.core import RandomSource, WallGrid
    from mazes.generators import get_generator
    from mazes.solvers import get_solver
    from mazes.rendering import write_ascii

    n = 20
    rng = RandomSource(seed=42)
    grid = get_generator("recursive_backtracking").generate(n, rng)

    result = get_solver("astar").solve(grid, (0, 0), (n - 1, n - 1))
    write_ascii(grid, "labyrinthe.txt", state=result.state)
"""

__version__ = "0.1.0"

__all__ = ["__version__"]
