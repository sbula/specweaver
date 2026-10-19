# Copyright (c) 2026 sbula. All rights reserved.
# Licensed under the Apache License, Version 2.0. See LICENSE file in the project root.

"""A `bash` step named by a `[[docs.block]]` fills that block with its output, and only it.

Proves: C-EXEC-08 FR-3
Proves: C-EXEC-08 NFR-3

Real scripts through the real runner, without worktree isolation.

| Bucket | Case |
|---|---|
| Happy | the block of `README.md` holds the script's output; the rest of the file is unchanged |
| Boundary | another `bash` step's output fills nothing |
| Degradation | a file without the markers fails the step naming them; a cut output fails the step and writes nothing |
| Hostile | a block whose step is a `generate` step refuses the run before any step; a block on `.env` refuses the run; a `README.md` that links out of the project fails the step |
"""

from __future__ import annotations

import asyncio
import shutil
from typing import TYPE_CHECKING
from unittest.mock import MagicMock, patch

import pytest

from specweaver.core.config.doc_policy import DocBlock, DocPolicy
from specweaver.core.flow.engine.models import (
    PipelineDefinition,
    PipelineStep,
    StepAction,
    StepTarget,
)
from specweaver.core.flow.engine.runner import PipelineRunner
from specweaver.core.flow.engine.state import RunStatus, StepStatus
from specweaver.core.flow.handlers.registry import StepHandlerRegistry
from specweaver.core.flow.handlers.run_context import ModelAccess, RunContext

if TYPE_CHECKING:
    from pathlib import Path

pytestmark = [
    pytest.mark.integration,
    pytest.mark.skipif(shutil.which("bash") is None, reason="bash required"),
]

_START = "<!-- sw:block counts -->"
_END = "<!-- sw:end counts -->"
_README = f"# Project\n\n{_START}\nold\n{_END}\n\nHuman text.\n"
_BLOCK = DocBlock(file="README.md", name="counts", step="update_counts")


def _project(root: Path, readme: str = _README) -> Path:
    scripts = root / ".specweaver" / "scripts"
    scripts.mkdir(parents=True)
    (scripts / "count.sh").write_text('echo "42 tests"\n', encoding="utf-8")
    (root / "README.md").write_text(readme, encoding="utf-8")
    return root


def _bash(name: str) -> PipelineStep:
    return PipelineStep(
        name=name, action=StepAction.BASH, target=StepTarget.SCRIPT, params={"script": "count.sh"}
    )


def _run(root: Path, steps: list[PipelineStep], block: DocBlock = _BLOCK):
    context = RunContext(
        project_path=root, spec_path=root / "spec.md", model=ModelAccess(config=MagicMock())
    )
    context.isolation = context.isolation.model_copy(
        update={"doc_policy": DocPolicy(block=[block])}
    )
    pipeline = PipelineDefinition(name="p", steps=steps)
    return asyncio.run(PipelineRunner(pipeline, context, registry=StepHandlerRegistry()).run())


def test_the_block_holds_the_output_and_the_rest_is_unchanged(tmp_path: Path) -> None:
    root = _project(tmp_path)

    run = _run(root, [_bash("update_counts")])

    assert run.status == RunStatus.COMPLETED, run
    assert (root / "README.md").read_text(encoding="utf-8") == (
        f"# Project\n\n{_START}\n42 tests\n{_END}\n\nHuman text.\n"
    )


def test_another_steps_output_fills_nothing(tmp_path: Path) -> None:
    root = _project(tmp_path)

    _run(root, [_bash("something_else")])

    assert (root / "README.md").read_text(encoding="utf-8") == _README


def test_a_file_without_the_markers_fails_the_step_naming_them(tmp_path: Path) -> None:
    root = _project(tmp_path, readme="# No markers\n")

    run = _run(root, [_bash("update_counts")])

    assert run.status == RunStatus.FAILED
    record = run.step_records[0].result
    assert record.status in {StepStatus.FAILED, StepStatus.ERROR}
    assert "README.md" in record.error_message
    assert "sw:block counts" in record.error_message
    assert (root / "README.md").read_text(encoding="utf-8") == "# No markers\n"


def test_a_cut_output_fails_the_step_and_writes_nothing(tmp_path: Path) -> None:
    root = _project(tmp_path)

    with patch("specweaver.sandbox.execution.core.atom._MAX_OUTPUT_BYTES", 4):
        run = _run(root, [_bash("update_counts")])

    assert run.status == RunStatus.FAILED
    assert "cut" in run.step_records[0].result.error_message
    assert (root / "README.md").read_text(encoding="utf-8") == _README


def test_a_readme_linking_out_of_the_project_fails_the_step(tmp_path: Path) -> None:
    outside = tmp_path / "outside.md"
    outside.write_text(_README, encoding="utf-8")
    root = tmp_path / "proj"
    root.mkdir()
    _project(root)
    (root / "README.md").unlink()
    (root / "README.md").symlink_to(outside)

    run = _run(root, [_bash("update_counts")])

    assert run.status == RunStatus.FAILED
    assert outside.read_text(encoding="utf-8") == _README


def test_a_block_whose_step_is_not_bash_refuses_the_run(tmp_path: Path) -> None:
    root = _project(tmp_path)
    generate = PipelineStep(
        name="update_counts", action=StepAction.GENERATE, target=StepTarget.CODE
    )

    with pytest.raises(ValueError, match="update_counts") as caught:
        _run(root, [_bash("first"), generate])

    assert "bash" in str(caught.value)
    assert (root / "README.md").read_text(encoding="utf-8") == _README


def test_a_block_on_a_protected_file_refuses_the_run(tmp_path: Path) -> None:
    root = _project(tmp_path)
    (root / ".env").write_text(f"{_START}\n{_END}\n", encoding="utf-8")
    block = DocBlock(file=".env", name="counts", step="update_counts")

    with pytest.raises(ValueError, match=r"\.env"):
        _run(root, [_bash("update_counts")], block=block)

    assert (root / ".env").read_text(encoding="utf-8") == f"{_START}\n{_END}\n"
