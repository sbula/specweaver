# Copyright (c) 2026 sbula. All rights reserved.
# Licensed under the Apache License, Version 2.0. See LICENSE file in the project root.

from pathlib import Path
from unittest.mock import MagicMock

from specweaver.sandbox.dispatcher import ToolDispatcher
from specweaver.sandbox.security import WorkspaceBoundary
from specweaver.sandbox.code_structure.interfaces.tool import CodeStructureTool


def test_dispatcher_handles_null_intents(tmp_path: Path) -> None:
    """FR-3/FR-4 Edge Case: Dispatcher gracefully defaults to empty list if intents is physically null."""
    boundary = WorkspaceBoundary(roots=[tmp_path])

    # Mocking atom logic because create_standard_set uses local imports and instantiates Atoms internally.
    # To test extraction natively, we can mock the loader that returns the evaluator schemas.
    import specweaver.workflows.evaluators.loader as loader_module

    original_load = loader_module.load_evaluator_schemas

    try:
        loader_module.load_evaluator_schemas = MagicMock(
            return_value={"generic": {"intents": None}}
        )

        # Write stub to trick resolver
        context = tmp_path / "context.yaml"
        context.write_text("archetype: generic")

        dispatcher = ToolDispatcher.create_standard_set(
            boundary, role="implementer", allowed_tools=["ast"]
        )

        ast_tool = next(t for t in dispatcher._interfaces if isinstance(t, CodeStructureTool))
        assert ast_tool._hidden_intents == []
    finally:
        loader_module.load_evaluator_schemas = original_load


def test_dispatcher_handles_intents_scalar_value(tmp_path: Path) -> None:
    """FR-3/FR-4 Edge Case: Dispatcher wraps scalar hide intents cleanly in a list."""
    boundary = WorkspaceBoundary(roots=[tmp_path])
    import specweaver.workflows.evaluators.loader as loader_module

    original_load = loader_module.load_evaluator_schemas

    try:
        loader_module.load_evaluator_schemas = MagicMock(
            return_value={"generic": {"intents": {"hide": "evil_string"}}}
        )

        context = tmp_path / "context.yaml"
        context.write_text("archetype: generic")

        dispatcher = ToolDispatcher.create_standard_set(
            boundary, role="implementer", allowed_tools=["ast"]
        )

        ast_tool = next(t for t in dispatcher._interfaces if isinstance(t, CodeStructureTool))
        assert ast_tool._hidden_intents == ["evil_string"]
    finally:
        loader_module.load_evaluator_schemas = original_load
