from typing import Any

from specweaver.graph.core.builder.orchestrator import GraphBuilder
from specweaver.graph.core.engine.core import InMemoryGraphEngine


def fake_java_parser(filepath: str) -> dict[str, Any]:
    """
    Reads a Java file from disk.
    Simulates a Tree-Sitter AST extractor purely for integration testing delta logic.
    """
    children = []

    # Fake simple name hashing to find target hashes for simulated calls
    # In reality, the parser extracts the name and the engine cross-references it,
    # or the AST provides a fully qualified name.

    with open(filepath, encoding="utf-8") as f:
        for line in f:
            if "class " in line:
                name = line.split("class ")[1].split()[0]
                children.append({"type": "class_declaration", "name": name})
            elif "public void " in line:
                name = line.split("public void ")[1].split("(")[0]
                children.append({"type": "method_declaration", "name": name})

    return {
        "type": "module",
        "children": children
    }

def test_real_file_system_integration(tmp_path):
    """
    [Integration] Verifies that creating, updating, and deleting real files
    correctly synchronizes with the InMemoryGraphEngine via the builder pipeline,
    including edge delta detection.
    """
    engine = InMemoryGraphEngine()
    builder = GraphBuilder(engine, parser=fake_java_parser)

    user_service = tmp_path / "UserService.java"

    # 1. CREATE UserService
    user_service.write_text(
        "public class UserService {\n"
        "    public void createUser() {}\n"
        "}\n",
        encoding="utf-8"
    )
    builder.ingest_file(str(user_service))

    # Verify graph populated: 1 FILE, 1 DATA_STRUCTURE, 1 PROCEDURE
    assert len(engine._graph.nodes) == 3
    node_names = {data["name"] for _, data in engine._graph.nodes(data=True)}
    assert "createUser" in node_names

    # 2. UPDATE UserService (Add comments / whitespace -> Should be IDEMPOTENT)
    user_service.write_text(
        "// Some new comments\n"
        "public class UserService {\n"
        "    public void createUser() {}\n"
        "}\n",
        encoding="utf-8"
    )
    builder.ingest_file(str(user_service))
    # Still 3 nodes. Nothing duplicated, nothing lost.
    assert len(engine._graph.nodes) == 3

    # 3. UPDATE file (Add new method, remove old method)
    user_service.write_text(
        "public class UserService {\n"
        "    public void deleteUser() {}\n"
        "}\n",
        encoding="utf-8"
    )
    builder.ingest_file(str(user_service))

    # Verify graph delta applied: 'createUser' removed, 'deleteUser' added.
    assert len(engine._graph.nodes) == 3
    node_names = {data["name"] for _, data in engine._graph.nodes(data=True)}
    assert "createUser" not in node_names
    assert "deleteUser" in node_names

    # Verify edges: The new PROCEDURE 'deleteUser' must have a CONTAINS edge from the FILE
    edges = list(engine._graph.edges(data=True))
    assert len(edges) == 2 # FILE -> UserService, FILE -> deleteUser

    # 4. DELETE file
    user_service.unlink()
    builder.ingest_file(str(user_service))

    # Verify graph delta applied: child nodes removed!
    assert len(engine._graph.nodes) == 1
    node_names = {data["name"] for _, data in engine._graph.nodes(data=True)}
    assert "UserService.java" in node_names
    # And edges removed!
    edges = list(engine._graph.edges(data=True))
    assert len(edges) == 0
