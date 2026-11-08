# Copyright (c) 2026 sbula. All rights reserved.
# Licensed under the Apache License, Version 2.0. See LICENSE file in the project root.

"""The module graph's engine protocol says what the engine really takes.

Proves: TECH-088 FR-8

The protocol said `traverse(start, forward)` and `neighbors_within(start, max_depth)` while the
engine took `traverse(start, forward=True)` and `neighbors_within(module, depth=1)`: a caller
following the protocol by keyword would have broken at run time.

| Bucket | Case |
|---|---|
| Happy | every protocol method has the engine's own signature: names, kinds, defaults |
| Boundary | the protocol names no method the engine lacks |
| Degradation | — a signature has no dependency to fail |
| Hostile | the engine passes as the protocol where mypy checks the assignment below |
"""

from __future__ import annotations

import inspect

import pytest

from specweaver.graph.topology.engine import TopologyEngine
from specweaver.graph.topology.topology import TopologyEngineProtocol

_METHODS = sorted(
    name
    for name, member in vars(TopologyEngineProtocol).items()
    if callable(member) and not name.startswith("_")
)

# mypy checks this line on every `cb`: the engine must satisfy the protocol.
_ENGINE: TopologyEngineProtocol = TopologyEngine()


def test_the_protocol_names_methods() -> None:
    assert "traverse" in _METHODS
    assert "neighbors_within" in _METHODS


@pytest.mark.parametrize("name", _METHODS)
def test_each_method_has_the_engines_signature(name: str) -> None:
    protocol = inspect.signature(getattr(TopologyEngineProtocol, name))
    engine = inspect.signature(getattr(TopologyEngine, name))

    assert [(p.name, p.kind, p.default) for p in protocol.parameters.values()] == [
        (p.name, p.kind, p.default) for p in engine.parameters.values()
    ]
