# Copyright (c) 2026 sbula. All rights reserved.
# Licensed under the Apache License, Version 2.0. See LICENSE file in the project root.

from pathlib import Path
from unittest.mock import MagicMock, patch

from specweaver.core.flow._review import _build_tool_dispatcher
from specweaver.core.loom.tools.filesystem.models import AccessMode, FolderGrant


def test_dispatcher_ast_injection() -> None:
    """Verify that AST tools securely inject into the Review Spec Pipeline loop via ToolDispatcher boundary."""
    grants = [FolderGrant(path="/", mode=AccessMode.FULL, recursive=True)]

    context = MagicMock()
    context.llm.generate_with_tools = True
    context.workspace.uri = "file://C:/workspace"

    with patch("specweaver.core.loom.security.WorkspaceBoundary.from_run_context") as mock_bounds:
        mock_boundary = MagicMock()
        mock_boundary.roots = [Path.cwd()]
        mock_boundary.to_folder_grants.return_value = grants
        mock_bounds.return_value = mock_boundary

        # 1. Reviewer role (requires AST access)
        dispatcher_reviewer = _build_tool_dispatcher(context, "reviewer")
        assert dispatcher_reviewer is not None
        schema_reviewer = dispatcher_reviewer.available_tools()

        tool_names_reviewer = [t.name for t in schema_reviewer]
        assert "read_file_structure" in tool_names_reviewer
        assert "list_symbols" in tool_names_reviewer
        assert "read_symbol" in tool_names_reviewer
        assert "read_symbol_body" in tool_names_reviewer

        # 2. Drafter role (only read_file_structure permitted in standard setups, or sometimes none)
        context_drafter = MagicMock()
        context_drafter.llm.generate_with_tools = True
        context_drafter.workspace.uri = "file://C:/workspace"
        dispatcher_drafter = _build_tool_dispatcher(context_drafter, "drafter")
        assert dispatcher_drafter is not None
        schema_drafter = dispatcher_drafter.available_tools()

        tool_names_drafter = [t.name for t in schema_drafter]
        assert "read_file_structure" in tool_names_drafter
        assert "read_symbol_body" not in tool_names_drafter
        assert "read_symbol" not in tool_names_drafter
