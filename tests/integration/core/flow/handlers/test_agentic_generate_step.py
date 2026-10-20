# Copyright (c) 2026 sbula. All rights reserved.
# Licensed under the Apache License, Version 2.0. See LICENSE file in the project root.

"""An agentic generate step runs the coder with its tools, in a worktree, under its grant.

Proves: C-FLOW-11 FR-3
Proves: C-FLOW-11 FR-4
Proves: C-FLOW-11 FR-8
Proves: C-FLOW-11 NFR-4

The real runner, handler, dispatcher, grant, worktree and merge over a real git repo; only the
model is scripted, and it acts through the tools it is given.

| Bucket | Case |
|---|---|
| Happy | the coder writes `src/greeter.py` through its tools; it lands through the merge |
| Boundary | a DAL above the ceiling runs one-shot, and the result says why; a session run uses its own worktree |
| Degradation | the coder ends without its target → the step fails naming it; it hits `agent_turns` → the step fails naming it |
| Hostile | `README.md`, another module, and — from the tests step — the module are refused by the grant; a project that is not a git repo fails the step |
"""

from __future__ import annotations

import asyncio
import shutil
import subprocess
from typing import TYPE_CHECKING, Any
from unittest.mock import MagicMock

import pytest

from specweaver.commons.enums.dal import DALLevel
from specweaver.core.config.autonomy_policy import AutonomyPolicy
from specweaver.core.config.doc_policy import DocPolicy, DocRule
from specweaver.core.flow.engine.models import (
    PipelineDefinition,
    PipelineStep,
    StepAction,
    StepTarget,
)
from specweaver.core.flow.engine.runner import PipelineRunner
from specweaver.core.flow.engine.state import RunStatus
from specweaver.core.flow.handlers.registry import StepHandlerRegistry
from specweaver.core.flow.handlers.run_context import ModelAccess, RunContext
from specweaver.infrastructure.llm.errors import ToolRoundsExceededError
from specweaver.infrastructure.llm.models import LLMResponse
from tests.scripted_llm import FixedRouter

if TYPE_CHECKING:
    from pathlib import Path

pytestmark = [
    pytest.mark.integration,
    pytest.mark.skipif(shutil.which("git") is None, reason="git required"),
]

_CODE = "def greet() -> str:\n    return 'hi'\n"


class _Coder:
    """Writes the given paths through its tools, then answers; or keeps calling tools for ever."""

    provider_name = "scripted"

    def __init__(self, *paths: str, endless: bool = False) -> None:
        self._paths = paths
        self._endless = endless
        self.answers: dict[str, Any] = {}
        self.prompts: list[str] = []

    def available(self) -> bool:
        return True

    async def generate(self, messages: Any, config: Any = None, *_a: Any, **_k: Any) -> LLMResponse:
        return LLMResponse(text=_CODE, model="test-model")

    async def generate_with_tools(
        self, messages: Any, config: Any, tool_executor: Any, **_k: Any
    ) -> LLMResponse:
        self.prompts.append(str(messages[-1]["content"]))
        if self._endless:
            raise ToolRoundsExceededError.reached(config.max_tool_rounds)
        for path in self._paths:
            self.answers[path] = await tool_executor.execute(
                "create_module", {"path": path, "code": _CODE}
            )
        return LLMResponse(text="done", model="test-model")


def _git(cwd: Path, *args: str) -> None:
    subprocess.run(["git", *args], cwd=cwd, check=True, capture_output=True)


def _project(root: Path, *, git: bool = True) -> Path:
    (root / "specs").mkdir(parents=True)
    (root / "specs" / "greeter_spec.md").write_text("# Greeter\n## 1. Purpose\nGreets.\n")
    (root / "README.md").write_text("Greeter.\n", encoding="utf-8")
    if git:
        _git(root, "init")
        _git(root, "config", "user.email", "t@t")
        _git(root, "config", "user.name", "t")
        _git(root, "add", "-A")
        _git(root, "commit", "-m", "init")
    return root


def _step(target: StepTarget = StepTarget.CODE) -> PipelineStep:
    return PipelineStep(name="write", action=StepAction.GENERATE, target=target, mode="agentic")


def _run(
    root: Path,
    coder: _Coder,
    *,
    dal: DALLevel = DALLevel.DAL_E,
    step: PipelineStep | None = None,
    session: bool = False,
    doc_policy: DocPolicy | None = None,
):
    context = RunContext(
        project_path=root,
        spec_path=root / "specs" / "greeter_spec.md",
        model=ModelAccess(config=MagicMock(), llm_router=FixedRouter(coder)),
    )
    context.isolation = context.isolation.model_copy(
        update={
            "autonomy": AutonomyPolicy(agentic_max_dal=DALLevel.DAL_D),
            "doc_policy": doc_policy or DocPolicy(),
            "dal_level": dal,
            "session_isolation": session,
            "allowed_paths": ["src/greeter.py", "tests/test_greeter.py"] if session else [],
        }
    )
    pipeline = PipelineDefinition(name="p", steps=[step or _step()])
    return asyncio.run(PipelineRunner(pipeline, context, registry=StepHandlerRegistry()).run())


def _result(run: Any) -> Any:
    return run.step_records[0].result


def test_the_coder_writes_its_target_and_it_lands(tmp_path: Path) -> None:
    root = _project(tmp_path)
    coder = _Coder("src/greeter.py")

    run = _run(root, coder)

    assert run.status == RunStatus.COMPLETED, _result(run)
    assert "error" not in coder.answers["src/greeter.py"]
    assert (root / "src" / "greeter.py").read_text(encoding="utf-8") == _CODE
    assert "src/greeter.py" in coder.prompts[0]


def test_in_a_session_the_coder_writes_and_it_lands(tmp_path: Path) -> None:
    root = _project(tmp_path)

    run = _run(root, _Coder("src/greeter.py"), session=True)

    assert run.status == RunStatus.COMPLETED, _result(run)
    assert (root / "src" / "greeter.py").exists()


@pytest.mark.parametrize("path", ["README.md", "src/other.py", "docs/notes.md"])
def test_a_write_outside_the_target_is_refused(tmp_path: Path, path: str) -> None:
    root = _project(tmp_path)
    coder = _Coder(path, "src/greeter.py")

    _run(root, coder)

    assert path in coder.answers[path]["error"]
    assert (root / "README.md").read_text(encoding="utf-8") == "Greeter.\n"
    assert not (root / "src" / "other.py").exists()


def test_the_tests_step_may_not_change_the_module(tmp_path: Path) -> None:
    root = _project(tmp_path)
    coder = _Coder("src/greeter.py", "tests/test_greeter.py")

    _run(root, coder, step=_step(StepTarget.TESTS))

    assert "src/greeter.py" in coder.answers["src/greeter.py"]["error"]
    assert not (root / "src" / "greeter.py").exists()
    assert (root / "tests" / "test_greeter.py").exists()


def test_a_coder_that_writes_nothing_fails_the_step_naming_the_file(tmp_path: Path) -> None:
    root = _project(tmp_path)

    run = _run(root, _Coder())

    assert run.status == RunStatus.FAILED
    assert "src/greeter.py" in (_result(run).error_message or "")


def test_reaching_the_turn_limit_fails_the_step_naming_it(tmp_path: Path) -> None:
    root = _project(tmp_path)

    run = _run(root, _Coder(endless=True))

    assert run.status == RunStatus.FAILED
    assert "agent_turns" in (_result(run).error_message or "")


def test_above_the_ceiling_the_step_runs_one_shot_and_says_why(tmp_path: Path) -> None:
    root = _project(tmp_path)
    coder = _Coder("src/greeter.py")

    run = _run(root, coder, dal=DALLevel.DAL_B)

    assert coder.prompts == []
    assert _result(run).output["agentic_refused"] == (
        "agentic refused: DAL_B is above the ceiling DAL_D"
    )


def test_a_project_without_git_fails_the_agentic_step(tmp_path: Path) -> None:
    root = _project(tmp_path, git=False)
    coder = _Coder("src/greeter.py")

    run = _run(root, coder)

    assert run.status == RunStatus.FAILED
    assert coder.prompts == []
    assert not (root / "src" / "greeter.py").exists()


def test_a_step_rule_for_this_step_lets_the_coder_write_its_doc(tmp_path: Path) -> None:
    """The coder's grant carries the project's `[docs]` rules and its own step name."""
    root = _project(tmp_path)
    coder = _Coder("docs/api/greeter.py", "src/greeter.py")
    rules = DocPolicy(rule=[DocRule(paths=["docs/api/**"], access="step", steps=["write"])])

    _run(root, coder, doc_policy=rules)

    assert "error" not in coder.answers["docs/api/greeter.py"], coder.answers
    assert (root / "docs" / "api" / "greeter.py").exists()


def test_a_dirty_working_tree_stops_the_run_and_keeps_the_changes(tmp_path: Path) -> None:
    """The coder's work lands through a merge, which needs a clean tree `[agreed 2026-10-20]`."""
    root = _project(tmp_path)
    (root / "src").mkdir()
    (root / "src" / "greeter.py").write_text("# mine, not committed\n", encoding="utf-8")
    _git(root, "add", "src/greeter.py")

    run = _run(root, _Coder("src/greeter.py"))

    assert run.status == RunStatus.FAILED
    assert "commit or stash" in (_result(run).error_message or "")
    assert (root / "src" / "greeter.py").read_text(encoding="utf-8") == "# mine, not committed\n"
