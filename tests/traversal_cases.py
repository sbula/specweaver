# Copyright (c) 2026 sbula. All rights reserved.
# Licensed under the Apache License, Version 2.0. See LICENSE file in the project root.

"""The traversal cases every graph engine must pass, as plain data. `A-SENS-02` FR-2.

The in-memory engines run them now; the database traversal runs the same cases later and compares
node sets and depths. Edges are directed, the walk is not: a neighbourhood goes both ways.

Each expected depth is written from the shape, never computed by an engine.
"""

from __future__ import annotations

from dataclasses import dataclass
from itertools import pairwise


@dataclass(frozen=True)
class Case:
    name: str
    edges: list[tuple[str, str]]
    start: str
    #: `node -> its shortest depth from start`, start included at 0.
    depths: dict[str, int]


def _chain(n: int) -> Case:
    nodes = [f"c{i}" for i in range(n)]
    return Case(
        f"chain of {n}",
        list(pairwise(nodes)),
        "c0",
        {node: i for i, node in enumerate(nodes)},
    )


def _cycle(n: int) -> Case:
    nodes = [f"r{i}" for i in range(n)]
    edges = [(nodes[i], nodes[(i + 1) % n]) for i in range(n)]
    return Case(f"cycle of {n}", edges, "r0", {node: min(i, n - i) for i, node in enumerate(nodes)})


def _fan_out(width: int, levels: int) -> Case:
    """The root links to every node of level 1; node i links to i and (i+1) mod width a level down.

    Most nodes have two paths to them, so a walk without a visited set counts them twice.
    """
    edges = [("root", f"L1_{i}") for i in range(width)]
    for level in range(1, levels):
        for i in range(width):
            edges.append((f"L{level}_{i}", f"L{level + 1}_{i}"))
            edges.append((f"L{level}_{i}", f"L{level + 1}_{(i + 1) % width}"))
    depths = {"root": 0}
    depths.update({f"L{lv}_{i}": lv for lv in range(1, levels + 1) for i in range(width)})
    return Case(f"fan-out {width} over {levels} levels", edges, "root", depths)


def _cycle_with_fan_out(ring: int, width: int) -> Case:
    """A ring of `ring`; its start fans out to `width` leaves, and every leaf links to the far side."""
    far = ring // 2
    nodes = [f"k{i}" for i in range(ring)]
    edges = [(nodes[i], nodes[(i + 1) % ring]) for i in range(ring)]
    edges += [("k0", f"leaf{j}") for j in range(width)]
    edges += [(f"leaf{j}", f"k{far}") for j in range(width)]

    def around(a: int, b: int) -> int:
        return min(abs(a - b), ring - abs(a - b))

    depths = {node: min(around(0, i), 2 + around(far, i)) for i, node in enumerate(nodes)}
    depths.update({f"leaf{j}": 1 for j in range(width)})
    return Case(f"cycle of {ring} with fan-out {width}", edges, "k0", depths)


CASES: list[Case] = [
    _chain(7),
    _chain(10_000),
    _fan_out(1_000, 4),
    Case("self-recursion", [("a", "a"), ("a", "b")], "a", {"a": 0, "b": 1}),
    Case("mutual recursion", [("a", "b"), ("b", "a"), ("b", "c")], "a", {"a": 0, "b": 1, "c": 2}),
    _cycle(10_000),
    _cycle_with_fan_out(10, 1_000),
]
