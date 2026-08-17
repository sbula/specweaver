# mypy: ignore-errors
# Copyright (c) 2026 sbula. All rights reserved.
# Licensed under the Apache License, Version 2.0. See LICENSE file in the project root.

"""Mapping an AST dictionary onto graph nodes and edges.

Proves: B-SENS-02 FR-1

Cited under `specweaver-dev` §3.2c, from `INT-US-10-MIG`. `B-SENS-02` is `✅` and had **0 of 5 FRs
cited by any test** — a capability whose claims `check_fr_sweep.py` scores as perfect because there
is nothing to be uncited.

Mutant-verified before the citation was believed: forcing `map_ast_to_nodes` to read no children
(`children = []`) fails a test here. Without that check the tag would be a transcription rather than
a constraint, which §3.2c names as the thing to avoid.
"""

from specweaver.graph.core.builder.mapper import OntologyMapper
from specweaver.graph.core.engine.ontology import NodeKind


def test_mapper_happy_path_python_function():
    """[Happy Path] Maps Python function_definition to PROCEDURE."""
    mapper = OntologyMapper()
    ast_data = {
        "type": "module",
        "children": [
            {"type": "function_definition", "name": "my_func"},
            {"type": "class_definition", "name": "MyClass"},
        ],
    }
    nodes, edges = mapper.map_ast_to_nodes("src/foo.py", ast_data)
    # Expect 3 nodes: 1 FILE, 1 PROCEDURE, 1 DATA_STRUCTURE
    assert len(nodes) == 3
    assert len(edges) == 2  # 2 CONTAINS edges from FILE -> PROCEDURE and FILE -> DATA_STRUCTURE
    kinds = {n.kind for n in nodes}
    assert NodeKind.FILE in kinds
    assert NodeKind.PROCEDURE in kinds
    assert NodeKind.DATA_STRUCTURE in kinds


def test_mapper_graceful_unknown_types():
    """[Graceful Degradation] Safely ignores unknown AST node types."""
    mapper = OntologyMapper()
    ast_data = {
        "type": "module",
        "children": [{"type": "unknown_future_syntax_node", "name": "ignored"}],
    }
    nodes, edges = mapper.map_ast_to_nodes("src/foo.py", ast_data)
    # Only the FILE node should be created
    assert len(nodes) == 1
    assert len(edges) == 0
    assert nodes[0].kind == NodeKind.FILE


def test_mapper_hostile_inputs():
    """[Hostile] Handles None or malformed dicts safely."""
    mapper = OntologyMapper()

    nodes, edges = mapper.map_ast_to_nodes("src/foo.py", None)
    assert len(nodes) == 1  # still creates FILE node
    assert len(edges) == 0

    nodes, edges = mapper.map_ast_to_nodes("src/foo.py", {})
    assert len(nodes) == 1
    assert len(edges) == 0
