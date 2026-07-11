# mypy: ignore-errors
from pathlib import Path
from unittest.mock import MagicMock

from specweaver.assurance.graph.loader import resolve_service_name


def test_resolve_service_name_no_topology():
    """[Boundary] None topology -> default"""
    name = resolve_service_name(None, Path("/src"))
    assert name == "default"


def test_resolve_service_name_matching_node():
    """[Happy Path] Matching path prefix -> node name"""
    # Create a mock topology graph
    topology = MagicMock()

    mock_node = MagicMock()
    mock_node.name = "my_service"
    mock_node.path = "/workspace/src/my_service"

    topology.nodes = {"n1": mock_node}

    name = resolve_service_name(topology, Path("/workspace/src/my_service/foo.py"))
    assert name == "my_service"


def test_resolve_service_name_no_match():
    """[Boundary] No node path matches -> default"""
    topology = MagicMock()

    mock_node = MagicMock()
    mock_node.name = "my_service"
    mock_node.path = "/workspace/src/my_service"

    topology.nodes = {"n1": mock_node}

    name = resolve_service_name(topology, Path("/workspace/src/other/foo.py"))
    assert name == "default"


def test_resolve_service_name_empty_nodes():
    """[Boundary] Empty nodes dict -> default"""
    topology = MagicMock()
    topology.nodes = {}

    name = resolve_service_name(topology, Path("/workspace/src/foo.py"))
    assert name == "default"
