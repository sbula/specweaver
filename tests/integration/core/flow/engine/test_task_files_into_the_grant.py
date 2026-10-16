# Copyright (c) 2026 sbula. All rights reserved.
# Licensed under the Apache License, Version 2.0. See LICENSE file in the project root.

"""A run's task files reach the coder's grant, with session isolation on or off.

Proves: E-SENS-03 FR-1
Proves: E-SENS-03 NFR-1

A real `RunContext`, the real session policy, the real dispatcher and code-structure tool.

| Bucket | Case |
|---|---|
| Happy | isolation on with a settings list (a glob): the grant follows it |
| Boundary | isolation on with no list, and isolation off: both give the files named from the spec |
| Degradation | a settings list with an empty entry stops the grant rather than widening it |
| Hostile | a file the settings list leaves out is refused, though the spec would name it |
"""

from __future__ import annotations

import asyncio
import logging
from types import SimpleNamespace
from typing import TYPE_CHECKING, Any

import pytest

from specweaver.core.flow.engine.isolation import apply_session_policy, task_files
from specweaver.core.flow.handlers.run_context import RunContext
from specweaver.sandbox.dispatcher import ToolDispatcher
from specweaver.sandbox.security import WorkspaceBoundary

if TYPE_CHECKING:
    from pathlib import Path

pytestmark = pytest.mark.integration

_LOG = logging.getLogger(__name__)


def _context(root: Path, *, session: bool, listed: list[str]) -> RunContext:
    context = RunContext(project_path=root, spec_path=root / "specs" / "greeter_spec.md")
    sandbox = SimpleNamespace(enforce_session_isolation=session, session_allowed_paths=listed)
    apply_session_policy(context, SimpleNamespace(sandbox=sandbox), _LOG)
    return context


def _create(context: RunContext, path: str) -> dict[str, Any]:
    dispatcher = ToolDispatcher.create_standard_set(
        WorkspaceBoundary(roots=[context.project_path]),
        role="implementer",
        allowed_tools=["ast"],
        task_files=task_files(context),
    )
    return asyncio.run(dispatcher.execute("create_module", {"path": path, "code": "x = 1\n"}))


def test_isolation_on_with_a_settings_list_follows_the_list(tmp_path: Path) -> None:
    context = _context(tmp_path, session=True, listed=["lib/**"])

    assert task_files(context) == ["lib/**"]
    assert "error" not in _create(context, "lib/deep/greeter.py")
    assert "src/greeter.py" in _create(context, "src/greeter.py")["error"]


@pytest.mark.parametrize("session", [True, False], ids=["isolation-on", "isolation-off"])
def test_without_a_list_the_files_are_named_from_the_spec(tmp_path: Path, session: bool) -> None:
    context = _context(tmp_path, session=session, listed=[])

    assert task_files(context) == ["src/greeter.py", "tests/test_greeter.py"]
    assert "error" not in _create(context, "src/greeter.py")
    assert "src/other.py" in _create(context, "src/other.py")["error"]


def test_an_empty_entry_in_the_settings_list_stops_the_grant(tmp_path: Path) -> None:
    context = _context(tmp_path, session=True, listed=["src/greeter.py", " "])

    with pytest.raises(ValueError, match="task file"):
        _create(context, "src/greeter.py")
