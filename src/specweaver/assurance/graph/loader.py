"""Public facade for topology loading and context selection.

Extracted from ``graph/interfaces/cli.py`` so that CLI and API can
load topology without importing from a CLI module.
"""

from __future__ import annotations

import logging
from pathlib import Path
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from specweaver.assurance.graph.topology import TopologyContext, TopologyGraph

logger = logging.getLogger(__name__)

_SELECTOR_MAP: dict[str, type] = {}


def _get_selector_map() -> dict[str, type]:
    if not _SELECTOR_MAP:
        from specweaver.assurance.graph.selectors import (
            ConstraintOnlySelector,
            DirectNeighborSelector,
            ImpactWeightedSelector,
            NHopConstraintSelector,
        )

        _SELECTOR_MAP.update(
            {
                "direct": DirectNeighborSelector,
                "nhop": NHopConstraintSelector,
                "constraint": ConstraintOnlySelector,
                "impact": ImpactWeightedSelector,
            }
        )
    return _SELECTOR_MAP


def load_topology(project_path: Path) -> TopologyGraph | None:
    """Load the project topology graph from context.yaml files.

    Returns None if no context.yaml files are found.
    Callers are responsible for any user-facing console output.
    """
    from specweaver.assurance.graph.topology import TopologyGraph
    from specweaver.graph.topology.engine import TopologyEngine

    engine = TopologyEngine()
    graph = TopologyGraph.from_project(project_path, engine, auto_infer=False)
    if not graph.nodes:
        logger.debug("No context.yaml files found — topology context disabled.")
        return None
    logger.debug("Loaded topology: %d modules.", len(graph.nodes))
    return graph


def select_topology_contexts(
    graph: TopologyGraph | None,
    module_name: str,
    *,
    selector_name: str = "direct",
) -> list[TopologyContext] | None:
    """Run a selector and return topology contexts, or None.

    Callers are responsible for any user-facing console output.
    """
    if graph is None:
        return None

    selector_map = _get_selector_map()
    selector_cls = selector_map.get(selector_name)
    if selector_cls is None:
        logger.warning("Unknown selector '%s', falling back to 'direct'.", selector_name)
        from specweaver.assurance.graph.selectors import DirectNeighborSelector

        selector_cls = DirectNeighborSelector

    selector = selector_cls()
    related = selector.select(graph, module_name)
    if not related:
        return None

    contexts = graph.format_context_summary(module_name, related)
    logger.debug(
        "Topology: %d related module(s) via %s selector.", len(contexts), selector_name
    )
    return contexts
