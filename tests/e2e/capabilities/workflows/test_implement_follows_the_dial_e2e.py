# Copyright (c) 2026 sbula. All rights reserved.
# Licensed under the Apache License, Version 2.0. See LICENSE file in the project root.

"""`sw implement` runs its generate steps agentic where the project's `[autonomy]` allows it.

Proves: C-FLOW-11 FR-10
Proves: C-FLOW-11 NFR-1

US-3 P-4. Only the model is doubled, as a coder that writes the file its prompt names through its
tools. Each agentic step runs in its own worktree, and its files land as merge commits on the
current branch `[agreed 2026-10-20]`.

| Bucket | Case |
|---|---|
| Happy | `mode = "agentic"`: the coder writes `src/greeter.py` and `tests/test_greeter.py`; both land as merge commits; the tests pass |
| Boundary | `mode = "oneshot"`: the model answers once, and nothing is committed (NFR-1) |
| Degradation | not applicable — a dirty working tree is proven by the integration tests |
| Hostile | not applicable — the grant's refusals are proven by the integration tests |
"""

from __future__ import annotations

import re
import subprocess
from typing import TYPE_CHECKING, Any

import pytest
from typer.testing import CliRunner

from specweaver.infrastructure.llm.models import LLMResponse
from specweaver.interfaces.cli.main import app
from tests.scripted_llm import doubled_llm

if TYPE_CHECKING:
    from pathlib import Path

runner = CliRunner()
pytestmark = pytest.mark.e2e

#: Valid as the module and as the test file: a QA run that collects nothing fails.
_CODE = "def greet():\n    pass\n\n\ndef test_greet_is_callable() -> None:\n    assert greet() is None\n"


class _Coder:
    """Writes the file its prompt names, through its tools; answers in text when asked once."""

    provider_name = "scripted"

    def __init__(self) -> None:
        self.tool_targets: list[str] = []
        self.one_shot_calls = 0

    def available(self) -> bool:
        return True

    async def generate(self, messages: Any, config: Any = None, *_a: Any, **_k: Any) -> LLMResponse:
        self.one_shot_calls += 1
        return LLMResponse(text=_CODE, model="test-model")

    async def generate_with_tools(
        self, messages: Any, config: Any, tool_executor: Any, **_k: Any
    ) -> LLMResponse:
        target = re.search(r"Write `([^`]+)` with your tools", str(messages[-1]["content"]))
        if target:
            self.tool_targets.append(target.group(1))
            await tool_executor.execute("create_module", {"path": target.group(1), "code": _CODE})
        return LLMResponse(text="done", model="test-model")


def _git(cwd: Path, *args: str) -> str:
    return subprocess.run(
        ["git", *args], cwd=cwd, check=True, capture_output=True, text=True
    ).stdout


def _project(tmp_path: Path, mode: str) -> Path:
    project = tmp_path / "proj"
    project.mkdir()
    assert runner.invoke(app, ["init", "dial", "--path", str(project)]).exit_code == 0
    (project / "specs" / "greeter_spec.md").write_text("# Greeter\n## 1. Purpose\nGreets.\n")
    (project / "specweaver.toml").write_text(
        f'[autonomy]\nmode = "{mode}"\nagentic_max_dal = "DAL_C"\n', encoding="utf-8"
    )
    _git(project, "init")
    _git(project, "config", "user.email", "t@t")
    _git(project, "config", "user.name", "t")
    _git(project, "add", "-A")
    _git(project, "commit", "-m", "init")
    return project


def _implement(project: Path, coder: _Coder) -> Any:
    with doubled_llm(coder):
        return runner.invoke(
            app,
            ["implement", str(project / "specs" / "greeter_spec.md"), "--project", str(project)],
        )


@pytest.mark.usefixtures("_mock_db")
def test_an_agentic_project_implements_through_the_coder(tmp_path: Path) -> None:
    project = _project(tmp_path, "agentic")
    coder = _Coder()

    result = _implement(project, coder)

    assert result.exit_code == 0, result.output
    assert coder.tool_targets[:2] == ["src/greeter.py", "tests/test_greeter.py"]
    assert coder.one_shot_calls == 0
    assert (project / "src" / "greeter.py").read_text(encoding="utf-8") == _CODE
    assert (project / "tests" / "test_greeter.py").read_text(encoding="utf-8") == _CODE
    assert "strip merge" in _git(project, "log", "--oneline")


@pytest.mark.usefixtures("_mock_db")
def test_a_oneshot_project_implements_as_before(tmp_path: Path) -> None:
    project = _project(tmp_path, "oneshot")
    coder = _Coder()

    result = _implement(project, coder)

    assert result.exit_code == 0, result.output
    assert coder.tool_targets == []
    assert coder.one_shot_calls >= 2
    assert len(_git(project, "log", "--oneline").splitlines()) == 1
