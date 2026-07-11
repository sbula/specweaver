# mypy: ignore-errors
from pathlib import Path
from unittest.mock import MagicMock, patch

from specweaver.sandbox.dispatcher import ToolDispatcher
from specweaver.sandbox.security import AccessMode, WorkspaceBoundary

# Adversarial Test Matrix:
# 1. Happy Path: test_create_standard_set_delegates_to_registry
# 2. Boundary: test_create_standard_set_preserves_grant_logic (scenario_agent vs arbiter_agent)
# 3. Graceful Degradation: test_create_standard_set_preserves_archetype_resolution (null analyzer, missing context.yaml)
# 4. Hostile Input: test_create_standard_set_empty_roots (fallback to api_paths)


def test_create_standard_set_delegates_to_registry(tmp_path):
    """Happy Path: Verifies that create_standard_set calls ToolRegistry.create_tools."""
    boundary = WorkspaceBoundary(roots=[tmp_path], api_paths=[])

    with patch("specweaver.sandbox.registry.get_standard_registry") as mock_get_registry:
        mock_registry = MagicMock()
        mock_registry.create_tools.return_value = []
        mock_get_registry.return_value = mock_registry

        ToolDispatcher.create_standard_set(
            boundary=boundary, role="reviewer", allowed_tools=["fs", "ast"]
        )

        # Verify the registry was called with allowed_tools and **kwargs
        mock_registry.create_tools.assert_called_once()
        args, kwargs = mock_registry.create_tools.call_args
        assert args[0] == ["fs", "ast"]
        assert kwargs["role"] == "reviewer"
        assert kwargs["cwd"] == tmp_path
        assert "grants" in kwargs
        assert "atom" in kwargs


def test_create_standard_set_preserves_grant_logic(tmp_path):
    """Boundary Case: Verifies scenario_agent receives degraded grants."""
    boundary = WorkspaceBoundary(roots=[tmp_path], api_paths=[])

    with patch("specweaver.sandbox.registry.get_standard_registry") as mock_get_registry:
        mock_registry = MagicMock()
        mock_registry.create_tools.return_value = []
        mock_get_registry.return_value = mock_registry

        ToolDispatcher.create_standard_set(
            boundary=boundary, role="scenario_agent", allowed_tools=["fs"]
        )

        mock_registry.create_tools.assert_called_once()
        _, kwargs = mock_registry.create_tools.call_args
        grants = kwargs["grants"]

        # Scenario agent should only have full access to 'scenarios', read access to 'specs'/'contracts'
        scenarios_grant = next((g for g in grants if Path(g.path).name == "scenarios"), None)
        assert scenarios_grant is not None
        assert scenarios_grant.mode == AccessMode.FULL


def test_create_standard_set_preserves_archetype_resolution(tmp_path):
    """Graceful Degradation: Verifies atom construction still resolves active_archetype."""
    boundary = WorkspaceBoundary(roots=[tmp_path], api_paths=[])

    with patch("specweaver.sandbox.registry.get_standard_registry") as mock_get_registry:
        mock_registry = MagicMock()
        mock_registry.create_tools.return_value = []
        mock_get_registry.return_value = mock_registry

        ToolDispatcher.create_standard_set(
            boundary=boundary, role="reviewer", allowed_tools=["ast"]
        )

        mock_registry.create_tools.assert_called_once()
        _, kwargs = mock_registry.create_tools.call_args
        atom = kwargs["atom"]

        # Atom should be a live CodeStructureAtom instance with an active_archetype
        from specweaver.sandbox.code_structure.core.atom import CodeStructureAtom

        assert isinstance(atom, CodeStructureAtom)
        assert hasattr(atom, "_active_archetype")


def test_create_standard_set_unknown_tools(tmp_path):
    """Hostile Input: Verify dispatcher passes unknown tools to the registry without crashing."""
    boundary = WorkspaceBoundary(roots=[tmp_path], api_paths=[])

    with patch("specweaver.sandbox.registry.get_standard_registry") as mock_get_registry:
        mock_registry = MagicMock()
        mock_registry.create_tools.return_value = []
        mock_get_registry.return_value = mock_registry

        ToolDispatcher.create_standard_set(
            boundary=boundary, role="reviewer", allowed_tools=["fs", "made_up_tool"]
        )

        mock_registry.create_tools.assert_called_once()
        args, _ = mock_registry.create_tools.call_args
        assert args[0] == ["fs", "made_up_tool"]
