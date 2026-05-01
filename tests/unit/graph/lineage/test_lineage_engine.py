import pytest
from unittest.mock import MagicMock

from specweaver.graph.lineage.engine import LineageEngine


@pytest.fixture
def mock_repo():
    repo = MagicMock()
    repo.get_artifact_history.return_value = []
    repo.get_children.return_value = []
    return repo


@pytest.fixture
def engine(mock_repo):
    return LineageEngine(repo=mock_repo)


class TestLineageEngine:
    def test_find_root_no_history(self, engine, mock_repo):
        """If history is empty, it is the root."""
        assert engine.find_root("node-1") == "node-1"

    def test_find_root_walks_up(self, engine, mock_repo):
        """Walks up the parent chain."""
        def mock_history(uid):
            if uid == "child":
                return [{"parent_id": "parent"}]
            if uid == "parent":
                return [{"parent_id": "root"}]
            if uid == "root":
                return [{"parent_id": None}]
            return []
        
        mock_repo.get_artifact_history.side_effect = mock_history
        assert engine.find_root("child") == "root"

    def test_find_root_circular_reference(self, engine, mock_repo):
        """Breaks out of circular references gracefully."""
        def mock_history(uid):
            if uid == "node-a":
                return [{"parent_id": "node-b"}]
            if uid == "node-b":
                return [{"parent_id": "node-a"}]
            return []

        mock_repo.get_artifact_history.side_effect = mock_history
        root = engine.find_root("node-a")
        # Should stop at either node-a or node-b depending on set traversal
        assert root in ("node-a", "node-b")

    def test_build_tree_single_node(self, engine, mock_repo):
        mock_repo.get_artifact_history.return_value = [{"event": "created"}]
        tree = engine.build_tree("root-1")
        assert tree["id"] == "root-1"
        assert len(tree["history"]) == 1
        assert tree["children"] == []
        assert not tree["circular"]

    def test_build_tree_nested(self, engine, mock_repo):
        def mock_history(uid):
            return [{"event": uid}]

        def mock_children(uid):
            if uid == "root":
                return [{"artifact_id": "child-1"}, {"artifact_id": "child-2"}]
            if uid == "child-1":
                return [{"artifact_id": "leaf"}]
            return []

        mock_repo.get_artifact_history.side_effect = mock_history
        mock_repo.get_children.side_effect = mock_children

        tree = engine.build_tree("root")
        assert tree["id"] == "root"
        assert len(tree["children"]) == 2
        
        c1 = next(c for c in tree["children"] if c["id"] == "child-1")
        c2 = next(c for c in tree["children"] if c["id"] == "child-2")
        
        assert len(c1["children"]) == 1
        assert c1["children"][0]["id"] == "leaf"
        assert len(c2["children"]) == 0

    def test_build_tree_circular_reference(self, engine, mock_repo):
        """Aborts recursive rendering on circular graph links to prevent stack overflow."""
        def mock_history(uid):
            return [{"event": "manual"}]

        def mock_children(uid):
            if uid == "loop-a":
                return [{"artifact_id": "loop-b"}]
            if uid == "loop-b":
                return [{"artifact_id": "loop-a"}]
            return []

        mock_repo.get_artifact_history.side_effect = mock_history
        mock_repo.get_children.side_effect = mock_children

        tree = engine.build_tree("loop-a")
        assert tree["id"] == "loop-a"
        assert len(tree["children"]) == 1
        
        b = tree["children"][0]
        assert b["id"] == "loop-b"
        assert len(b["children"]) == 1
        
        a_again = b["children"][0]
        assert a_again["id"] == "loop-a"
        assert a_again["circular"] is True
        assert len(a_again["children"]) == 0
