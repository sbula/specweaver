import pytest

from specweaver.graph.lineage.engine import LineageEngine
from specweaver.graph_store.lineage_repository import LineageRepository


@pytest.fixture
def repo(tmp_path):
    db_path = tmp_path / "lineage_test.db"
    return LineageRepository(str(db_path))

@pytest.fixture
def engine(repo):
    return LineageEngine(repo)

def test_engine_builds_nested_tree_with_real_sqlite(engine, repo):
    # Setup happy path nested tree
    repo.log_artifact_event("root-1", None, "run-1", "CREATED", "model")
    repo.log_artifact_event("child-1", "root-1", "run-2", "MODIFIED", "model")
    repo.log_artifact_event("child-2", "root-1", "run-2", "MODIFIED", "model")
    repo.log_artifact_event("leaf-1", "child-1", "run-3", "MODIFIED", "model")

    root_id = engine.find_root("leaf-1")
    assert root_id == "root-1"

    tree = engine.build_tree("root-1")
    assert tree["id"] == "root-1"
    assert len(tree["children"]) == 2

    # Check children
    child_ids = {c["id"] for c in tree["children"]}
    assert child_ids == {"child-1", "child-2"}

    # Check deeper nesting
    c1 = next(c for c in tree["children"] if c["id"] == "child-1")
    assert len(c1["children"]) == 1
    assert c1["children"][0]["id"] == "leaf-1"

def test_engine_handles_circular_reference(engine, repo):
    # Setup boundary edge case: circular reference
    repo.log_artifact_event("node-a", "node-b", "run-1", "MODIFIED", "model")
    repo.log_artifact_event("node-b", "node-a", "run-2", "MODIFIED", "model")

    # engine should break the loop gracefully without RecursionError
    root = engine.find_root("node-a")
    assert root in ("node-a", "node-b")

    tree = engine.build_tree("node-a")
    assert tree["id"] == "node-a"
    b = tree["children"][0]
    assert b["id"] == "node-b"
    a_again = b["children"][0]
    assert a_again["id"] == "node-a"
    assert a_again["circular"] is True
    assert len(a_again["children"]) == 0

def test_engine_handles_missing_uuid_gracefully(engine, repo):
    # Graceful degradation
    root = engine.find_root("unknown-uuid")
    assert root == "unknown-uuid"

    tree = engine.build_tree("unknown-uuid")
    assert tree["id"] == "unknown-uuid"
    assert tree["children"] == []
    assert not tree["circular"]


def test_engine_handles_broken_repository(engine, repo, monkeypatch):
    # Hostile/Wrong Input: repository connection fails
    def mock_broken(*args, **kwargs):
        import sqlite3
        raise sqlite3.OperationalError("disk I/O error")

    monkeypatch.setattr(repo, "get_artifact_history", mock_broken)
    monkeypatch.setattr(repo, "get_children", mock_broken)

    # Engine should not crash, it should return gracefully
    root = engine.find_root("some-node")
    assert root == "some-node"

    tree = engine.build_tree("some-node")
    assert tree["id"] == "some-node"
    assert tree["children"] == []
    assert not tree["circular"]
