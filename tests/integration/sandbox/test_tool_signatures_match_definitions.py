# Copyright (c) 2026 sbula. All rights reserved.
# Licensed under the Apache License, Version 2.0. See LICENSE file in the project root.

"""What a tool's definition tells the model is what the tool accepts.

Proves: E-SENS-01 FR-5

A parameter the definition marks optional must have a default in the method the dispatcher calls;
otherwise a model that leaves it out, as told it may, gets an error instead of a result. Found live
2026-10-13: Gemini called `find_files(pattern="*")` and every file role refused it.

| Bucket | Case |
|---|---|
| Happy | every offered tool, for every role, accepts its required parameters by name |
| Boundary | an optional parameter left out still calls the tool |
| Degradation | not applicable: no service is called |
| Hostile | not applicable: the definitions are the repo's own |
"""

from __future__ import annotations

import inspect
from typing import TYPE_CHECKING

import pytest

from specweaver.core.flow.handlers.run_context import RunContext
from specweaver.sandbox.dispatcher import ToolDispatcher
from specweaver.sandbox.security import WorkspaceBoundary

if TYPE_CHECKING:
    from pathlib import Path

_ROLES = ["reviewer", "implementer", "planner", "drafter"]


def _dispatcher(tmp_path: Path, role: str) -> ToolDispatcher:
    boundary = WorkspaceBoundary.from_run_context(
        RunContext(project_path=tmp_path, spec_path=tmp_path / "s.md")
    )
    return ToolDispatcher.create_standard_set(
        boundary, role=role, allowed_tools=["fs", "ast", "web"], search_key="k"
    )


@pytest.mark.parametrize("role", _ROLES)
def test_an_optional_parameter_has_a_default(tmp_path: Path, role: str) -> None:
    # Proves: E-SENS-01 FR-5
    try:
        dispatcher = _dispatcher(tmp_path, role)
    except ValueError:
        pytest.fail(f"no standard tool set for role {role!r}")
    problems = []
    for definition in dispatcher.available_tools():
        handler = dispatcher._registry[definition.name]
        params = inspect.signature(handler).parameters
        takes_rest = any(p.kind is p.VAR_KEYWORD for p in params.values())
        for param in definition.parameters:
            accepted = params.get(param.name)
            if accepted is None and not takes_rest:
                problems.append(f"{definition.name}: no parameter {param.name!r}")
            elif accepted is not None and not param.required and accepted.default is accepted.empty:
                problems.append(f"{definition.name}: optional {param.name!r} has no default")
    assert not problems, problems


def test_find_files_without_a_path_searches_the_root(tmp_path: Path) -> None:
    import asyncio

    (tmp_path / "a.py").write_text("x = 1\n", encoding="utf-8")
    answer = asyncio.run(
        _dispatcher(tmp_path, "implementer").execute("find_files", {"pattern": "*.py"})
    )

    assert "error" not in answer, answer
    assert "a.py" in str(answer)
