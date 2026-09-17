"""Union-Find avec compression de chemin et union par rang.

La version du prototype faisait `parent[racine_a] = racine_b` sans rang :
correct, mais les arbres peuvent dégénérer. Le rang garantit une
complexité quasi constante par opération.
"""

from __future__ import annotations


class UnionFind:
    __slots__ = ("_groups", "_parent", "_rank")

    def __init__(self, size: int) -> None:
        self._parent = list(range(size))
        self._rank = [0] * size
        self._groups = size

    def find(self, x: int) -> int:
        parent = self._parent
        while parent[x] != x:
            parent[x] = parent[parent[x]]  # compression de chemin
            x = parent[x]
        return x

    def union(self, a: int, b: int) -> bool:
        """Fusionne les deux groupes. Renvoie False s'ils étaient déjà liés."""
        ra, rb = self.find(a), self.find(b)
        if ra == rb:
            return False
        if self._rank[ra] < self._rank[rb]:
            ra, rb = rb, ra
        self._parent[rb] = ra
        if self._rank[ra] == self._rank[rb]:
            self._rank[ra] += 1
        self._groups -= 1
        return True

    def connected(self, a: int, b: int) -> bool:
        return self.find(a) == self.find(b)

    @property
    def groups(self) -> int:
        return self._groups
