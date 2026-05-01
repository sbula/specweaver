from specweaver.graph.builder.mapper import OntologyMapper
from specweaver.graph.engine.ontology import NodeKind


def test_mapper_happy_path_python_function():
    """[Happy Path] Maps Python function_definition to PROCEDURE."""
    mapper = OntologyMapper()
    ast_data = {
        "type": "module",
        "children": [
            {
                "type": "function_definition",
                "name": "my_func"
            },
            {
                "type": "class_definition",
                "name": "MyClass"
            }
        ]
    }
    nodes, edges = mapper.map_ast_to_nodes("src/foo.py", ast_data)
    # Expect 3 nodes: 1 FILE, 1 PROCEDURE, 1 DATA_STRUCTURE
    assert len(nodes) == 3
    assert len(edges) == 2 # 2 CONTAINS edges from FILE -> PROCEDURE and FILE -> DATA_STRUCTURE
    kinds = {n.kind for n in nodes}
    assert NodeKind.FILE in kinds
    assert NodeKind.PROCEDURE in kinds
    assert NodeKind.DATA_STRUCTURE in kinds

def test_mapper_graceful_unknown_types():
    """[Graceful Degradation] Safely ignores unknown AST node types."""
    mapper = OntologyMapper()
    ast_data = {
        "type": "module",
        "children": [
            {
                "type": "unknown_future_syntax_node",
                "name": "ignored"
            }
        ]
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
    assert len(nodes) == 1 # still creates FILE node
    assert len(edges) == 0

    nodes, edges = mapper.map_ast_to_nodes("src/foo.py", {})
    assert len(nodes) == 1
    assert len(edges) == 0
