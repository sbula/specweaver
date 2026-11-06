# Copyright (c) 2026 sbula. All rights reserved.
# Licensed under the Apache License, Version 2.0. See LICENSE file in the project root.

"""A step that writes a project file names it in `files_touched`, relative to its project.

Proves: TECH-082 FR-8

The run's handover saves these names for the next agent. The scenario steps name nothing: task
memory reaches the next coder prompt, and a scenario file's name would tell the coder that a
scenario side exists (`B-FLOW-01`).

| Bucket | Case |
|---|---|
| Happy | the contract step names its contract file, relative to the project |
| Boundary | a file inside the project (a worktree, too) is relative; one outside is kept as given |
| Degradation | a failed contract step names no file |
| Hostile | a path that climbs out with `..` is not written as `../…` |
"""

from __future__ import annotations

import ast
from pathlib import Path
from unittest.mock import MagicMock

import pytest

from specweaver.core.flow.engine.state import StepStatus
from specweaver.core.flow.engine.step_outputs import FILES_TOUCHED, touched
from specweaver.core.flow.handlers.contract import GenerateContractHandler
from specweaver.core.flow.run_state.run_context import GraphContext, IsolationPolicy

_SPEC = """## 2. Contract

```python
class Greeter(Protocol):
    def greet(self, name: str) -> str:
        \"\"\"Return a greeting.\"\"\"
```
"""
_SCENARIO = Path(__file__).resolve().parents[5] / "src/specweaver/core/flow/handlers/scenario.py"


def _context(tmp_path: Path, spec: str) -> MagicMock:
    spec_file = tmp_path / "greeter_spec.md"
    spec_file.write_text(spec, encoding="utf-8")
    ctx = MagicMock()
    ctx.spec_path = spec_file
    ctx.project_path = tmp_path
    ctx.graph = GraphContext(api_contract_paths=None)
    ctx.isolation = IsolationPolicy()
    return ctx


async def test_the_contract_step_names_its_file(tmp_path: Path) -> None:
    result = await GenerateContractHandler().execute(MagicMock(), _context(tmp_path, _SPEC))

    assert result.status == StepStatus.PASSED
    assert result.output[FILES_TOUCHED] == ["contracts/greeter_contract.py"]


async def test_a_failed_contract_step_names_no_file(tmp_path: Path) -> None:
    result = await GenerateContractHandler().execute(
        MagicMock(), _context(tmp_path, "## 1. Purpose\n\nNo contract.\n")
    )

    assert result.status == StepStatus.ERROR
    assert FILES_TOUCHED not in result.output


def test_a_file_in_a_worktree_is_relative_to_that_worktree(tmp_path: Path) -> None:
    worktree = tmp_path / ".worktrees" / "session-1"

    assert touched(worktree / "src" / "a.py", worktree) == ["src/a.py"]


def test_a_file_outside_the_project_is_kept_as_given(tmp_path: Path) -> None:
    outside = tmp_path / "out" / "a.py"

    assert touched(outside, tmp_path / "project") == [str(outside)]


def test_a_path_that_climbs_out_is_not_written_relative(tmp_path: Path) -> None:
    project = tmp_path / "project"
    climbing = project / ".." / "elsewhere" / "a.py"

    assert touched(climbing, project) == [str(tmp_path / "elsewhere" / "a.py")]


def test_the_scenario_steps_name_no_file() -> None:
    tree = ast.parse(_SCENARIO.read_text(encoding="utf-8"))
    names = {n.id for n in ast.walk(tree) if isinstance(n, ast.Name)}

    assert "FILES_TOUCHED" not in names
    assert "touched" not in names


@pytest.fixture(autouse=True)
def _python_project(tmp_path: Path) -> None:
    """The project root is a Python project."""
    (tmp_path / "pyproject.toml").write_text('[project]\nname = "x"\n')
