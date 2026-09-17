"""Générateur de secours en ligne de commande, sans dépendance au paquet.

Utile pour produire un fichier de test si le paquet n'est pas encore
installé : python tools/maze_stub.py 20 > maze.txt
"""

import random
import sys


def generer(n: int, seed: int | None = None) -> list[tuple[tuple[int, int], tuple[int, int]]]:
    rng = random.Random(seed)
    parent = {(i, j): (i, j) for i in range(n) for j in range(n)}

    def find(x):
        while parent[x] != x:
            parent[x] = parent[parent[x]]
            x = parent[x]
        return x

    murs = []
    for i in range(n):
        for j in range(n):
            if j + 1 < n:
                murs.append(((i, j), (i, j + 1)))
            if i + 1 < n:
                murs.append(((i, j), (i + 1, j)))
    rng.shuffle(murs)

    passages = []
    for a, b in murs:
        ra, rb = find(a), find(b)
        if ra != rb:
            parent[ra] = rb
            passages.append((a, b))
    return passages


def afficher(n: int, passages) -> str:
    ouverts = set(passages) | {(b, a) for a, b in passages}
    grille = [["#"] * (2 * n + 1) for _ in range(2 * n + 1)]
    for i in range(n):
        for j in range(n):
            grille[2 * i + 1][2 * j + 1] = " "
            if ((i, j), (i, j + 1)) in ouverts:
                grille[2 * i + 1][2 * j + 2] = " "
            if ((i, j), (i + 1, j)) in ouverts:
                grille[2 * i + 2][2 * j + 1] = " "
    grille[0][1] = " "
    grille[2 * n][2 * n - 1] = " "
    return "\n".join("".join(ligne) for ligne in grille)


if __name__ == "__main__":
    taille = int(sys.argv[1]) if len(sys.argv) > 1 else 20
    graine = int(sys.argv[2]) if len(sys.argv) > 2 else None
    print(afficher(taille, generer(taille, graine)))
