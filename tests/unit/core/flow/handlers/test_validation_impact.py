from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from specweaver.core.flow.handlers.base import RunContext
from specweaver.core.flow.handlers.validation import ValidateTestsHandler


@pytest.fixture
def mock_run_context(tmp_path: Path):
    return RunContext(
        project_path=tmp_path / "project",
        spec_path=tmp_path / "project" / "spec.yaml",
        stale_nodes={"flow", "graph"},
    )


@patch("specweaver.assurance.graph.topology.TopologyGraph.from_project")
def test_validate_tests_handler_resolves_topology_targets(
    mock_from_project, mock_run_context: RunContext
):
    """Test that ValidateTestsHandler correctly maps topology nodes to explicit test paths."""

    # Mock TopologyGraph
    mock_graph = MagicMock()
    mock_from_project.return_value = mock_graph

    # Mock TopologyNode.yaml_path
    node_flow = MagicMock()
    node_flow.yaml_path = (
        mock_run_context.project_path / "src" / "specweaver" / "core" / "flow" / "context.yaml"
    )

    node_graph = MagicMock()
    node_graph.yaml_path = (
        mock_run_context.project_path
        / "src"
        / "specweaver"
        / "assurance"
        / "graph"
        / "context.yaml"
    )

    mock_graph.nodes = {"flow": node_flow, "graph": node_graph}

    # We must pretend the test directories exist so they aren't pruned to fallback
    def mock_exists(*args, **kwargs):
        return True

    with patch("specweaver.core.flow.handlers.validation.Path.exists", side_effect=mock_exists):
        handler = ValidateTestsHandler()
        # Resolve targets for unit tests
        targets = handler._resolve_targets(mock_run_context, "tests/", "unit")

    # On Windows, paths use \, so we construct them safely
    expected_flow = str(Path("tests") / "unit" / "core" / "flow")
    expected_graph = str(Path("tests") / "unit" / "assurance" / "graph")

    assert expected_flow in targets
    assert expected_graph in targets
    assert len(targets) == 2


@patch("specweaver.assurance.graph.topology.TopologyGraph.from_project")
def test_validate_tests_handler_fallback_when_path_not_exists(
    mock_from_project, mock_run_context: RunContext
):
    """Test that ValidateTestsHandler falls back to tests/<kind> when the exact path doesn't exist."""

    mock_graph = MagicMock()
    mock_from_project.return_value = mock_graph

    node_flow = MagicMock()
    node_flow.yaml_path = (
        mock_run_context.project_path / "src" / "specweaver" / "core" / "flow" / "context.yaml"
    )

    mock_graph.nodes = {"flow": node_flow}

    # Mock exists to always return False for targeted paths
    with patch("specweaver.core.flow.handlers.validation.Path.exists", return_value=False):
        handler = ValidateTestsHandler()
        targets = handler._resolve_targets(mock_run_context, "tests/", "unit")

    expected_fallback = str(Path("tests") / "unit")
    assert expected_fallback in targets
    assert len(targets) == 1
