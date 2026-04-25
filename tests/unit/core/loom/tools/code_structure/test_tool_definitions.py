# Copyright (c) 2026 sbula. All rights reserved.
# Licensed under the Apache License, Version 2.0. See LICENSE file in the project root.

from unittest.mock import MagicMock

from specweaver.core.loom.tools.code_structure.tool import CodeStructureTool


def test_code_structure_tool_respects_hidden_intents() -> None:
    """FR-3 Edge Case: tool definitions cleanly isolate schema rejection via internal list comprehension."""
    mock_atom = MagicMock()
    mock_atom.get_supported_capabilities.return_value = (
        {"skeleton", "symbol", "symbol_body", "list", "replace", "add", "delete", "replace_body", "framework_markers"},
        {"list_symbols": {"visibility", "decorator_filter"}},
    )

    # Empty hidden
    tool = CodeStructureTool(atom=mock_atom, role="implementer", grants=[], hidden_intents=[])
    defs_all = tool.definitions()
    assert len(defs_all) > 5
    names = [d.name for d in defs_all]
    assert "list_symbols" in names

    # Hide list_symbols
    tool_hidden = CodeStructureTool(
        atom=mock_atom,
        role="implementer",
        grants=[],
        hidden_intents=["list_symbols", "not_real_tool"],
    )
    defs_hidden = tool_hidden.definitions()
    names_hidden = [d.name for d in defs_hidden]

    assert "list_symbols" not in names_hidden
    # Shouldn't fail matching against fake tools it doesn't own
    assert len(names_hidden) == len(names) - 1


def test_code_structure_tool_handles_none_intents() -> None:
    """FR-3 Edge Case: internal init transforms None hidden_intents to safe array gracefully."""
    mock_atom = MagicMock()
    mock_atom.get_supported_capabilities.return_value = (
        {"skeleton", "symbol", "symbol_body", "list", "replace", "add", "delete", "replace_body", "framework_markers"},
        {"list_symbols": {"visibility", "decorator_filter"}},
    )
    tool = CodeStructureTool(atom=mock_atom, role="implementer", grants=[], hidden_intents=None)
    assert tool._hidden_intents == []

    # Smoke test definitions shouldn't crash
    definitions = tool.definitions()
    assert len(definitions) > 0
