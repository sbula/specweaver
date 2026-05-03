# Copyright (c) 2026 sbula. All rights reserved.
# Licensed under the Apache License, Version 2.0. See LICENSE file in the project root.

"""Integration tests for dynamic loading of Sandbox tools by the ToolDispatcher."""

from __future__ import annotations

import pytest

from specweaver.sandbox.dispatcher import ToolDispatcher
from specweaver.sandbox.security import WorkspaceBoundary


@pytest.mark.integration
def test_dispatcher_resolves_all_sandbox_domains(tmp_path) -> None:
    """
    [Happy Path] Integration:
    Ensures that the sandbox domain interfaces can be dynamically loaded and routed
    without ModuleNotFoundError, proving no path breakage post-migration.
    """
    boundary = WorkspaceBoundary(roots=[tmp_path])

    # Prove that the interfaces from the new sandbox domains resolve correctly

    # We use create_standard_set which handles complex instantiations internally
    # and validates that the intent mapping logic still works.
    dispatcher = ToolDispatcher.create_standard_set(
        boundary=boundary,
        role="implementer",
        allowed_tools=["fs", "ast", "web"]
    )

    loaded_intents = list(dispatcher._registry.keys())

    # Verify the ones we successfully loaded through the dispatcher
    for intent in ["read_file", "read_file_structure", "web_search"]:
        assert intent in loaded_intents, f"Intent '{intent}' was not loaded by ToolDispatcher"
