# Copyright (c) 2026 sbula. All rights reserved.
# Licensed under the Apache License, Version 2.0. See LICENSE file in the project root.

"""Context selectors — strategies for choosing which modules to include.

Each selector implements a different heuristic for deciding which
neighbouring modules should be surfaced to the LLM when reviewing,
drafting, or implementing a given target module.

Usage::

    from specweaver.assurance.graph.selectors import DirectNeighborSelector

    selector = DirectNeighborSelector()
    related = selector.select(graph, "my_module")
    contexts = graph.format_context_summary("my_module", related)
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from specweaver.assurance.graph.topology import TopologyGraph


class ContextSelector(ABC):
    """Abstract base class for context selection strategies.

    Subclasses implement ``select()`` to return a set of module names
    that should be included as context for a given target module.
    """

    @abstractmethod
    def select(
        self,
        graph: TopologyGraph,
        module: str,
    ) -> set[str]:
        """Return module names to include as context for *module*.

        Args:
            graph: The project's topology graph.
            module: The target module being reviewed/drafted.

        Returns:
            Set of module names to include in the prompt context.
        """


# ---------------------------------------------------------------------------
# Concrete selectors
# ---------------------------------------------------------------------------


class DirectNeighborSelector(ContextSelector):
    """Select only direct dependencies and consumers (1-hop).

    The simplest selector — fast, low token cost, good for focused
    reviews where only immediate neighbours matter.
    """

    def select(
        self,
        graph: TopologyGraph,
        module: str,
    ) -> set[str]:
        return graph.neighbors_within(module, depth=1)


class NHopConstraintSelector(ContextSelector):
    """Select N-hop neighbours plus modules sharing constraints.

    Combines structural proximity (N-hop BFS) with semantic proximity
    (shared constraints).  Good for reviews where constraint propagation
    matters.

    Args:
        depth: Number of hops to traverse.  Default 2.
    """

    def __init__(self, depth: int = 2) -> None:
        self._depth = max(1, depth)

    def select(
        self,
        graph: TopologyGraph,
        module: str,
    ) -> set[str]:
        neighbours = graph.neighbors_within(module, depth=self._depth)
        shared = graph.modules_sharing_constraints(module)
        return neighbours | shared


class ConstraintOnlySelector(ContextSelector):
    """Select only modules that share at least one constraint.

    Ignores graph topology entirely — purely semantic matching.
    Good for constraint-focused reviews where structural proximity
    is less important than shared rules.
    """

    def select(
        self,
        graph: TopologyGraph,
        module: str,
    ) -> set[str]:
        return graph.modules_sharing_constraints(module)


class ImpactWeightedSelector(ContextSelector):
    """Select modules weighted by transitive impact (stub).

    Future: will rank modules by how much they are affected by
    changes to the target module, using the transitive impact set
    and optional weighting by constraint overlap.

    Current implementation: falls back to 2-hop neighbours + impact set.
    """

    def select(
        self,
        graph: TopologyGraph,
        module: str,
    ) -> set[str]:
        neighbours = graph.neighbors_within(module, depth=2)
        impact = graph.impact_of(module)
        return neighbours | impact
