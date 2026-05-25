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


def resolve_service_name(topology: TopologyGraph | None, target_path: Path) -> str:
    """Resolve the logical service name for a given file path based on the topology graph.

    If no topology is present or no matching node is found, returns 'default'.
    """
    if topology is None or getattr(topology, "nodes", None) is None or not topology.nodes:
        return "default"

    target_str = str(target_path.resolve()).replace("\\", "/")

    for node in topology.nodes.values():
        if getattr(node, "path", None):
            node_path_str = str(Path(node.path).resolve()).replace("\\", "/")  # type: ignore[attr-defined]
            if target_str.startswith(node_path_str):
                return node.name

    return "default"


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
    logger.debug("Topology: %d related module(s) via %s selector.", len(contexts), selector_name)
    return contexts
