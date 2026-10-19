# Copyright (c) 2026 sbula. All rights reserved.
# Licensed under the Apache License, Version 2.0. See LICENSE file in the project root.

"""Under worktree isolation, the merge keeps a block step's change when it stays inside its block.

Proves: C-EXEC-08 FR-3

Real git, real `bash` steps, the real runner. `README.md` stays human: only the block's own step,
changing only the block, gets through.

| Bucket | Case |
|---|---|
| Happy | the block step's new block lands, per step and in a session |
| Boundary | not applicable — marker shapes are proven by the unit tests |
| Degradation | a block file new on the branch is not block-only: proposed |
| Hostile | the block step's script also edits `README.md` outside the block → proposed; another step writing the block → proposed |
"""

from __future__ import annotations

import asyncio
import shutil
import subprocess
from typing import TYPE_CHECKING
from unittest.mock import MagicMock

import pytest

from specweaver.core.config.doc_policy import DocBlock, DocPolicy
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

if TYPE_CHECKING:
    from pathlib import Path

pytestmark = [
    pytest.mark.integration,
    pytest.mark.skipif(shutil.which("git") is None or shutil.which("bash") is None, reason="git"),
]

_START = "<!-- sw:block counts -->"
_END = "<!-- sw:end counts -->"
_README = f"# Project\n\n{_START}\nold\n{_END}\n\nHuman text.\n"
_FILLED = f"# Project\n\n{_START}\n42 tests\n{_END}\n\nHuman text.\n"
_POLICY = DocPolicy(block=[DocBlock(file="README.md", name="counts", step="update_counts")])


def _git(cwd: Path, *args: str) -> None:
    subprocess.run(["git", *args], cwd=cwd, check=True, capture_output=True)


def _project(root: Path, scripts: dict[str, str], *, readme: bool = True) -> Path:
    folder = root / ".specweaver" / "scripts"
    folder.mkdir(parents=True)
    for name, body in scripts.items():
        (folder / name).write_text(body, encoding="utf-8", newline="\n")
    if readme:
        (root / "README.md").write_text(_README, encoding="utf-8")
    _git(root, "init")
    _git(root, "config", "user.email", "t@t")
    _git(root, "config", "user.name", "t")
    _git(root, "add", "-A")
    _git(root, "commit", "-m", "init")
    return root


def _step(name: str, script: str, *, own_worktree: bool = True) -> PipelineStep:
    return PipelineStep(
        name=name,
        action=StepAction.BASH,
        target=StepTarget.SCRIPT,
        params={"script": script},
        use_worktree=True if own_worktree else None,
    )


def _run(root: Path, steps: list[PipelineStep], *, session: bool = False):
    context = RunContext(
        project_path=root, spec_path=root / "spec.md", model=ModelAccess(config=MagicMock())
    )
    context.isolation = context.isolation.model_copy(
        update={"session_isolation": session, "allowed_paths": ["src/**"], "doc_policy": _POLICY}
    )
    pipeline = PipelineDefinition(name="p", steps=steps)
    return asyncio.run(PipelineRunner(pipeline, context, registry=StepHandlerRegistry()).run())


def test_the_block_steps_block_lands(tmp_path: Path) -> None:
    root = _project(tmp_path, {"count.sh": 'echo "42 tests"\n'})

    run = _run(root, [_step("update_counts", "count.sh")])

    assert run.status == RunStatus.COMPLETED, run
    assert (root / "README.md").read_text(encoding="utf-8") == _FILLED
    assert not (root / "doc_updates.md").exists()


def test_in_a_session_the_block_lands(tmp_path: Path) -> None:
    root = _project(tmp_path, {"count.sh": 'echo "42 tests"\n'})

    run = _run(root, [_step("update_counts", "count.sh", own_worktree=False)], session=True)

    assert run.status == RunStatus.COMPLETED, run
    assert (root / "README.md").read_text(encoding="utf-8") == _FILLED


def test_a_script_that_also_edits_outside_the_block_is_proposed(tmp_path: Path) -> None:
    root = _project(
        tmp_path, {"count.sh": 'sed -i "s/Human text/Agent text/" README.md\necho "42 tests"\n'}
    )

    _run(root, [_step("update_counts", "count.sh")])

    assert (root / "README.md").read_text(encoding="utf-8") == _README
    assert "+Agent text." in (root / "doc_updates.md").read_text(encoding="utf-8")


def test_another_step_writing_the_block_is_proposed(tmp_path: Path) -> None:
    root = _project(tmp_path, {"write.sh": 'sed -i "s/^old$/forged/" README.md\n'})

    _run(root, [_step("other", "write.sh")])

    assert (root / "README.md").read_text(encoding="utf-8") == _README
    assert "+forged" in (root / "doc_updates.md").read_text(encoding="utf-8")


def test_a_block_file_new_on_the_branch_is_proposed(tmp_path: Path) -> None:
    script = f'printf "%s\\n" "{_START}" "{_END}" > README.md\n'
    root = _project(tmp_path, {"count.sh": script + 'echo "42 tests"\n'}, readme=False)

    _run(root, [_step("update_counts", "count.sh")])

    assert not (root / "README.md").exists()
    assert "README.md" in (root / "doc_updates.md").read_text(encoding="utf-8")
