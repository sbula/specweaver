# Copyright (c) 2026 sbula. All rights reserved.
# Licensed under the Apache License, Version 2.0. See LICENSE file in the project root.

"""Change a run's `GraphContext` in a test, validated like the run setup's own."""

from __future__ import annotations

from typing import Any

from specweaver.core.flow.run_state.run_context import GraphContext


def with_graph(context: Any, fields: dict[str, Any]) -> None:
    """Rebind `context.graph` with `fields` changed; a wrong shape raises here, not in a reader."""
    kept = {name: getattr(context.graph, name) for name in GraphContext.model_fields}
    context.graph = GraphContext.model_validate({**kept, **fields})
