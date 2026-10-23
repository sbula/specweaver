# Copyright (c) 2026 sbula. All rights reserved.
# Licensed under the Apache License, Version 2.0. See LICENSE file in the project root.

"""Give a run the topology slice around the spec's module, when the project has a topology."""

from __future__ import annotations

from typing import TYPE_CHECKING

from specweaver.assurance.graph.loader import load_topology, select_topology_contexts
from specweaver.commons.spec_names import module_stem

if TYPE_CHECKING:
    from pathlib import Path

    from specweaver.core.flow.handlers.run_context import RunContext


def attach_topology(
    context: RunContext, project_path: Path, spec_path: Path, selector: str
) -> None:
    """Set `context.graph.topology` from the project's topology; unchanged when it has none."""
    topo_graph = load_topology(project_path)
    if topo_graph:
        topo_contexts = select_topology_contexts(
            topo_graph,
            module_stem(spec_path),
            selector_name=selector,
        )
        context.graph = context.graph.model_copy(update={"topology": topo_contexts})
